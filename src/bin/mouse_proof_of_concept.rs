// Standalone binary to test macOS mouse input capture proof of concept
//
// This creates a simple demo that shows CGEventTap mouse capture working.
// Run with: cargo run --bin mouse_proof_of_concept

use anyhow::Result;

#[cfg(target_os = "macos")]
fn main() -> Result<()> {
    use kanata_state_machine::proof_of_concept::run_proof_of_concept_demo;
    
    println!("🚀 Starting macOS Mouse Input Proof of Concept...");
    println!();
    
    match run_proof_of_concept_demo() {
        Ok(()) => {
            println!("✅ Proof of concept completed successfully!");
            Ok(())
        }
        Err(e) => {
            println!("❌ Proof of concept failed: {}", e);
            println!();
            println!("💡 Troubleshooting:");
            println!("   1. Make sure you've granted Accessibility permissions");
            println!("   2. Try running from Terminal with full disk access");
            println!("   3. Check that you're not running in a sandboxed environment");
            std::process::exit(1);
        }
    }
}

#[cfg(not(target_os = "macos"))]
fn main() {
    println!("❌ This proof of concept is only available on macOS");
    println!("   The mouse input capture using CGEventTap is macOS-specific.");
    std::process::exit(1);
}