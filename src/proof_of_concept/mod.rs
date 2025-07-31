// Proof of Concept modules for testing new features
// 
// This module contains experimental implementations that validate
// technical approaches before integration into the main codebase.

#[cfg(target_os = "macos")]
pub mod macos_mouse_tap;

#[cfg(target_os = "macos")]
pub use macos_mouse_tap::*;