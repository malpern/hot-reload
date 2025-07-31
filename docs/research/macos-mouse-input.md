# macOS Mouse Input Support - Research & Planning

**Status**: 🔬 Research Phase  
**Branch**: `feat/macos-mouse-input`  
**Target**: Complete mouse input capture for macOS platform

## Executive Summary

Currently, macOS is the only platform lacking mouse input capture in kanata, making it incomplete compared to Linux (full mouse support) and Windows (expanding with winmouse branch). This document outlines the research and implementation plan to add comprehensive mouse input support to macOS.

## Current State Analysis

### What Works Today
- ✅ **Mouse Output**: Complete via Core Graphics (`CGEvent::new_mouse_event`)
- ✅ **Keyboard Input**: Full via karabiner-driverkit integration
- ✅ **Architecture**: Well-established `KbdIn`/`KbdOut` pattern

### What's Missing
- ❌ **Mouse Input**: No mouse event capture/interception
- ❌ **Mouse Device Listing**: No mouse devices in `--list` output
- ❌ **Unified Input**: Only keyboard events flow through kanata processing

### Impact
- Users can't remap mouse buttons or mouse wheel
- macOS users have significantly less functionality than Linux/Windows users
- Inconsistent cross-platform experience

## Technical Research

### API Options Analysis

#### Option 1: Core Graphics Event Taps (RECOMMENDED)
**API**: `CGEventTapCreate()` with `kCGEventTapOptionDefault`

**Pros**:
- System-wide mouse capture
- Comprehensive event types (clicks, movement, scroll)
- Already using Core Graphics for output
- Well-documented Apple API
- Can filter specific event types

**Cons**:
- Requires accessibility permissions
- Potential performance impact
- More complex than keyboard-only approach

**Implementation Pattern**:
```rust
let event_tap = CGEventTapCreate(
    kCGHIDEventTap,                    // Tap location
    kCGHeadInsertEventTap,            // Placement
    kCGEventTapOptionDefault,         // Options
    event_mask,                       // Event types to capture
    mouse_event_callback,             // Callback function
    user_data,                        // User data
);
```

#### Option 2: IOKit HID Integration
**API**: IOKit HID APIs for direct mouse device access

**Pros**:
- Lower-level control
- Device-specific targeting
- No accessibility permissions needed

**Cons**:
- Much more complex implementation
- Requires deep IOKit knowledge  
- May conflict with system mouse handling
- Device enumeration complexity

#### Option 3: NSEvent Global Monitoring
**API**: `NSEvent.addGlobalMonitorForEventsMatchingMask`

**Pros**:
- Higher-level Cocoa API
- Easier to implement

**Cons**:
- App-specific (not system-wide)
- Limited event access
- May not work for all mouse events

### Recommended Approach: Core Graphics Event Taps

**Rationale**: 
- Aligns with existing Core Graphics output usage
- Comprehensive system-wide capture
- Battle-tested API used by other input remapping tools
- Clear permission model

## Architecture Planning

### Current Structure
```
KbdIn::read() -> InputEvent (keyboard only)
   ↓
kanata processing
   ↓  
KbdOut::write() -> System output (keyboard + mouse)
```

### Proposed Structure
```
MacOSInputManager::read() -> InputEvent (keyboard + mouse)
   ├── KeyboardInput (existing karabiner-driverkit)
   └── MouseInput (new CGEventTap)
      ↓
kanata processing (unchanged)
      ↓
KbdOut::write() -> System output (unchanged)
```

### Key Components

#### 1. MouseEventTap
```rust
pub struct MouseEventTap {
    event_tap: CGEventTap,
    run_loop_source: CFRunLoopSource,
    event_queue: Arc<Mutex<VecDeque<InputEvent>>>,
}
```

#### 2. MacOSInputManager  
```rust
pub struct MacOSInputManager {
    keyboard_input: KbdIn,               // Existing
    mouse_tap: Option<MouseEventTap>,    // New
    config: MouseInputConfig,            // New
}
```

#### 3. Event Processing Pipeline
```rust
extern "C" fn mouse_event_callback(
    _proxy: CGEventTapProxy,
    event_type: CGEventType, 
    event: CGEventRef,
    user_info: *mut c_void,
) -> CGEventRef {
    // Convert CGEvent -> InputEvent
    // Queue for processing
    // Return original event (pass-through)
}
```

## Implementation Phases

### Phase 1: Foundation Research (Week 1)
**Goals**: Validate technical approach
**Tasks**:
- [ ] Create minimal CGEventTap proof of concept
- [ ] Test mouse event capture and conversion
- [ ] Verify accessibility permission requirements
- [ ] Measure performance impact
- [ ] Document API usage patterns

**Deliverables**:
- Working mouse event capture demo
- Performance benchmarks
- Permission flow documentation

### Phase 2: Core Integration (Week 2-3)
**Goals**: Integrate with existing kanata architecture
**Tasks**:
- [ ] Extend `InputEvent` for mouse events (if needed)
- [ ] Create `MouseEventTap` implementation
- [ ] Refactor `KbdIn` to `MacOSInputManager`
- [ ] Implement unified event polling
- [ ] Add configuration options

**Deliverables**:
- Mouse events flowing through kanata processing
- Configuration parsing for mouse options
- Updated `--list` with mouse devices

### Phase 3: Polish & Testing (Week 4)
**Goals**: Production readiness
**Tasks**:
- [ ] Permission handling & user guidance  
- [ ] Event filtering (avoid processing own output)
- [ ] Error handling & fallbacks
- [ ] Performance optimization
- [ ] Comprehensive testing

**Deliverables**:
- Production-ready mouse input support
- User documentation
- Test coverage

## Configuration Design

### New defcfg Options
```lisp
(defcfg
  ;; Existing options...
  
  ;; Mouse input support
  macos-enable-mouse-capture true
  
  ;; Device filtering (future enhancement)
  macos-mouse-device-names-include (
    "Magic Mouse"
    "Logitech MX Master"
  )
  
  ;; Performance tuning (advanced)
  macos-mouse-capture-events (
    left-click right-click middle-click
    scroll-wheel mouse-movement
  )
)
```

### Backward Compatibility
- Mouse capture **disabled by default** initially
- Existing keyboard functionality unaffected
- Graceful degradation if permissions denied

## Risk Assessment & Mitigation

### High Risk: Accessibility Permissions
**Risk**: Users may not understand or grant accessibility permissions
**Mitigation**: 
- Clear error messages with instructions
- Optional mouse support (keyboard continues working)
- Documentation with screenshots

### Medium Risk: Performance Impact
**Risk**: System-wide mouse capture could slow down system
**Mitigation**:
- Efficient callback implementation (minimal processing)
- Optional feature (disabled by default initially)
- Performance monitoring and optimization

### Medium Risk: Event Loop Complexity
**Risk**: Mixing blocking keyboard read with async mouse events
**Mitigation**:
- Threaded approach for mouse events
- Queue-based communication
- Timeout-based unified polling

### Low Risk: Conflicts with Windows Work
**Risk**: Changes might conflict with jtroo's winmouse branch  
**Mitigation**:
- Communication with jtroo
- Focus on macOS-specific implementation
- Flexible interfaces that adapt to Windows patterns

## Success Metrics

### Functional Requirements
- [ ] Mouse clicks captured and processed by kanata
- [ ] Mouse wheel events work with kanata actions
- [ ] Mouse movement events available (if configured)
- [ ] `--list` shows mouse devices
- [ ] Configuration options work as expected

### Performance Requirements  
- [ ] <1ms additional latency for mouse events
- [ ] <5% CPU impact during normal usage
- [ ] No system-wide mouse lag observable

### User Experience Requirements
- [ ] Clear permission instructions
- [ ] Graceful fallback if mouse capture fails
- [ ] Backward compatibility maintained
- [ ] Documentation covers common scenarios

## Research Questions

### Technical Questions
1. Can CGEventTap and karabiner-driverkit coexist safely?
2. What's the optimal event queue size for mouse events?
3. How to filter out kanata's own mouse output events?
4. What mouse events should be captured by default?

### User Experience Questions  
1. Should mouse capture be enabled by default?
2. What permission guidance is most effective?
3. How to handle mouse devices with unusual capabilities?
4. What configuration options are most valuable?

### Integration Questions
1. How does this align with Windows winmouse implementation?
2. Should InputEvent struct be modified for mouse events?
3. How to extend --list for mouse devices consistently?
4. What configuration format works across platforms?

## Next Steps

### Immediate Actions (This Week)
1. **Create GitHub issue** for macOS mouse input support  
2. **Start Phase 1 research** with CGEventTap proof of concept
3. **Set up development environment** with accessibility permissions
4. **Monitor winmouse branch** for implementation patterns

### Short-term Goals (Next 2 Weeks)
1. **Complete technical validation** of CGEventTap approach
2. **Begin core integration** work
3. **Coordinate with jtroo** on cross-platform consistency
4. **Document findings** and update this research doc

### Long-term Vision (Month 2)
1. **Complete implementation** with full mouse input support
2. **Align with Windows patterns** from completed winmouse work
3. **Submit PR** for macOS mouse input support
4. **Achieve cross-platform mouse parity** across all platforms

---

**Research Lead**: Claude Code  
**Created**: 2025-07-31  
**Last Updated**: 2025-07-31  
**Status**: 🔬 Research Phase Started