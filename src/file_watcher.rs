//! File watching for configuration hot-reload.
//!
//! Replaces the basic file watcher with comprehensive support for include files
//! and dynamic watcher restart when include files change during reload.

use crate::kanata::Kanata;
use anyhow::Result;
use notify_debouncer_mini::{DebounceEventResult, new_debouncer, notify::RecursiveMode};
use parking_lot::Mutex;
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

/// Discover include files by parsing config files for (include "path") statements.
/// This is a simple parser that looks for include statements without full parsing.
pub fn discover_include_files(cfg_paths: &[PathBuf]) -> Vec<PathBuf> {
    let mut include_files = Vec::new();

    for cfg_path in cfg_paths {
        if let Ok(content) = fs::read_to_string(cfg_path) {
            // Simple regex-like parsing for include statements
            for line in content.lines() {
                let trimmed = line.trim();
                if trimmed.starts_with("(include") && trimmed.contains('"') {
                    // Extract the path between quotes
                    if let Some(start) = trimmed.find('"') {
                        if let Some(end) = trimmed[start + 1..].find('"') {
                            let include_path = &trimmed[start + 1..start + 1 + end];
                            let mut path = PathBuf::from(include_path);

                            // If path is relative, make it relative to the config file directory
                            if !path.is_absolute() {
                                if let Some(parent) = cfg_path.parent() {
                                    path = parent.join(path);
                                }
                            }

                            if path.exists() {
                                include_files.push(path);
                                log::debug!(
                                    "Discovered include file: {}",
                                    include_files.last().unwrap().display()
                                );
                            }
                        }
                    }
                }
            }
        }
    }

    include_files
}

/// Start comprehensive file watching for configuration files and included files.
/// This replaces the basic file watcher with full include file support and dynamic restart.
pub fn start_file_watcher(kanata_arc: Arc<Mutex<Kanata>>) -> Result<()> {
    // Get paths from kanata
    let cfg_paths = {
        let k = kanata_arc.lock();
        k.cfg_paths.clone()
    };

    log::info!(
        "Starting file watcher for {} config file(s)",
        cfg_paths.len()
    );
    for (i, path) in cfg_paths.iter().enumerate() {
        log::info!("  Config file {}: {}", i + 1, path.display());
    }

    // Discover include files and update kanata
    let included_files = discover_include_files(&cfg_paths);
    if !included_files.is_empty() {
        log::info!("Found {} include file(s) to watch", included_files.len());
        for (i, path) in included_files.iter().enumerate() {
            log::info!("  Include file {}: {}", i + 1, path.display());
        }
    }

    {
        let mut k = kanata_arc.lock();
        k.included_files = included_files.clone();
    }

    // Create the watcher and store it in the Kanata struct
    let debouncer = create_debouncer(kanata_arc.clone(), &cfg_paths, &included_files)?;

    // Store the debouncer in the Kanata struct
    {
        let mut k = kanata_arc.lock();
        k.file_watcher = Some(debouncer);
    }

    log::info!("File watcher initialized successfully");
    Ok(())
}

/// Create a new file watcher debouncer with the given file lists.
/// This is used both for initial setup and for restarting the watcher when included files change.
pub fn create_debouncer(
    kanata_arc: Arc<Mutex<Kanata>>,
    cfg_paths: &[PathBuf],
    included_files: &[PathBuf],
) -> Result<notify_debouncer_mini::Debouncer<notify_debouncer_mini::notify::RecommendedWatcher>> {
    // Create list of all files to watch
    let all_watched_files: Vec<PathBuf> = cfg_paths
        .iter()
        .chain(included_files.iter())
        .cloned()
        .collect();

    // Create debouncer with platform-appropriate timeout and event handling closure
    // Use longer timeout on macOS to handle atomic save bursts from editors
    let debounce_timeout = if cfg!(target_os = "macos") {
        Duration::from_millis(750)
    } else {
        Duration::from_millis(500)
    };
    let kanata_arc_clone = kanata_arc.clone();
    let mut debouncer = new_debouncer(debounce_timeout, move |result: DebounceEventResult| {
        match result {
            Ok(events) => {
                for event in events {
                    log::debug!(
                        "File watcher event received: {:?} for path: {}",
                        event.kind,
                        event.path.display()
                    );

                    // Check if the changed file is one of our watched files
                    // Use multiple path comparison strategies to handle different cases
                    let is_watched_file = all_watched_files.iter().any(|watched_path| {
                        // Try exact path match first
                        if event.path == *watched_path {
                            return true;
                        }

                        // Try canonicalized paths (handles symlinks and relative paths)
                        if let (Ok(event_canonical), Ok(watched_canonical)) =
                            (event.path.canonicalize(), watched_path.canonicalize())
                        {
                            if event_canonical == watched_canonical {
                                return true;
                            }
                        }

                        // Try path comparison after converting to absolute paths as fallback
                        let event_absolute = event
                            .path
                            .canonicalize()
                            .or_else(|_| std::env::current_dir().map(|pwd| pwd.join(&event.path)));
                        let watched_absolute = watched_path
                            .canonicalize()
                            .or_else(|_| std::env::current_dir().map(|pwd| pwd.join(watched_path)));

                        if let (Ok(event_abs), Ok(watched_abs)) = (event_absolute, watched_absolute)
                        {
                            return event_abs == watched_abs;
                        }

                        false
                    });

                    if is_watched_file {
                        log::info!(
                            "Config file changed: {} (event: {:?}), triggering reload",
                            event.path.display(),
                            event.kind
                        );

                        // Set the live_reload_requested flag
                        if let Some(mut kanata) = kanata_arc_clone.try_lock() {
                            kanata.request_live_reload();
                        } else {
                            log::warn!("Could not acquire lock to set live_reload_requested");
                        }
                    } else {
                        // Fallback: handle macOS directory-level events and atomic replace edge cases.
                        // If the event is in the same parent directory and the basename matches one of the watched files,
                        // also trigger reload. This helps when the rename event uses a temp file path.
                        let mut parent_dir_match = false;
                        if let Some(event_parent) = event.path.parent() {
                            parent_dir_match = all_watched_files.iter().any(|wf| {
                                wf.parent() == Some(event_parent)
                                    && wf.file_name().is_some()
                                    && event.path.file_name().is_some()
                                    && wf.file_name() == event.path.file_name()
                            });
                        }

                        if parent_dir_match {
                            log::info!(
                                "Directory-level change for watched file: {} (event: {:?}), triggering reload",
                                event.path.display(),
                                event.kind
                            );
                            if let Some(mut kanata) = kanata_arc_clone.try_lock() {
                                kanata.request_live_reload();
                            } else {
                                log::warn!("Could not acquire lock to set live_reload_requested");
                            }
                        } else {
                            // Handle directory-only events (common on macOS due to FSEvents coalescing)
                            // If the event is for a directory that is the parent of any watched file, trigger reload
                            let dir_is_parent_of_watched = event.path.is_dir()
                                && all_watched_files.iter().any(|wf| {
                                    wf.parent().map(|p| p == event.path).unwrap_or(false)
                                });

                            if dir_is_parent_of_watched {
                                log::info!(
                                    "Directory-level change for parent of watched files: {} (event: {:?}), triggering reload",
                                    event.path.display(),
                                    event.kind
                                );
                                if let Some(mut kanata) = kanata_arc_clone.try_lock() {
                                    kanata.request_live_reload();
                                } else {
                                    log::warn!(
                                        "Could not acquire lock to set live_reload_requested"
                                    );
                                }
                            } else {
                                log::trace!(
                                    "Ignoring event for non-watched file or directory: {}",
                                    event.path.display()
                                );
                            }
                        }
                    }
                }
            }
            Err(e) => {
                log::error!("File watcher error: {:?}", e);
            }
        }
    })?;

    // Watch all config files
    for path in cfg_paths {
        match debouncer.watcher().watch(path, RecursiveMode::NonRecursive) {
            Ok(()) => {
                log::info!("Successfully watching config file: {}", path.display());
            }
            Err(e) => {
                log::error!("Failed to watch config file {}: {}", path.display(), e);
                return Err(e.into());
            }
        }
    }

    // Watch included files
    for path in included_files {
        match debouncer.watcher().watch(path, RecursiveMode::NonRecursive) {
            Ok(()) => {
                log::info!("Successfully watching included file: {}", path.display());
            }
            Err(e) => {
                log::error!("Failed to watch included file {}: {}", path.display(), e);
                return Err(e.into());
            }
        }
    }

    Ok(debouncer)
}

pub fn restart_watcher(k_locked: &mut parking_lot::MutexGuard<Kanata>, k_ref: Arc<Mutex<Kanata>>) {
    log::info!("Restarting file watcher due to changes in included files");

    // Drop the old watcher. This is critical to stop its background thread
    // and release the file handles on the previously watched files.
    k_locked.file_watcher = None;

    // Create a new watcher with the updated file list
    let new_debouncer = match create_debouncer(k_ref, &k_locked.cfg_paths, &k_locked.included_files)
    {
        Ok(debouncer) => {
            log::info!("File watcher successfully restarted");
            Some(debouncer)
        }
        Err(e) => {
            log::error!("Failed to restart file watcher: {}", e);
            None
        }
    };

    k_locked.file_watcher = new_debouncer;
    k_locked.file_watcher_restart_requested = false;
}
