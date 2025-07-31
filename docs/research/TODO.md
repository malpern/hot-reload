# macOS Mouse Input - Research Tasks

## Phase 1: Foundation Research (Week 1)

### CGEventTap Proof of Concept
- [ ] **Research CGEventTap APIs**
  - [ ] Review Apple documentation for `CGEventTapCreate`
  - [ ] Identify required event types for mouse capture
  - [ ] Understand permission requirements and error handling
  
- [ ] **Create minimal proof of concept**
  - [ ] Basic CGEventTap setup that captures mouse clicks
  - [ ] Convert `CGEvent` to printable information
  - [ ] Test system-wide capture vs app-specific
  
- [ ] **Test event capture**
  - [ ] Left/right mouse clicks
  - [ ] Mouse wheel events (vertical/horizontal)
  - [ ] Mouse movement events
  - [ ] Test with different mouse devices (trackpad, Magic Mouse, USB mouse)

### Technical Validation
- [ ] **Permission requirements**
  - [ ] Test what happens without accessibility permissions
  - [ ] Document permission grant process
  - [ ] Test permission checking APIs
  
- [ ] **Performance measurement**
  - [ ] Measure latency impact of event capture
  - [ ] CPU usage during normal/heavy mouse usage
  - [ ] Memory usage of event queuing
  
- [ ] **Integration feasibility**
  - [ ] Test CGEventTap alongside karabiner-driverkit
  - [ ] Verify no conflicts with keyboard input
  - [ ] Test event pass-through behavior

### Research Documentation
- [ ] **Document findings**
  - [ ] API usage patterns that work
  - [ ] Performance characteristics
  - [ ] Permission requirements and user flow
  - [ ] Limitations or edge cases discovered

## Phase 2: Core Integration (Week 2-3)

### Architecture Design
- [ ] **Event handling design**
  - [ ] Design InputEvent extensions for mouse events
  - [ ] Plan queue-based communication between mouse and keyboard
  - [ ] Design unified polling mechanism
  
- [ ] **Integration points**
  - [ ] Plan KbdIn refactor to MacOSInputManager
  - [ ] Design configuration options for mouse capture
  - [ ] Plan --list integration for mouse devices

### Implementation Tasks
- [ ] **MouseEventTap implementation**
  - [ ] Create MouseEventTap struct and methods
  - [ ] Implement CGEvent to InputEvent conversion
  - [ ] Add event queuing and thread safety
  
- [ ] **MacOSInputManager implementation**
  - [ ] Refactor KbdIn to support both keyboard and mouse
  - [ ] Implement unified read() method
  - [ ] Add configuration parsing for mouse options
  
- [ ] **Device listing integration**
  - [ ] Research mouse device enumeration on macOS
  - [ ] Extend --list to show mouse devices
  - [ ] Ensure consistent formatting with other platforms

## Phase 3: Polish & Testing (Week 4)

### Production Readiness
- [ ] **Permission handling**
  - [ ] Implement accessibility permission checking
  - [ ] Create user-friendly error messages and guidance
  - [ ] Handle permission revocation gracefully
  
- [ ] **Event filtering**
  - [ ] Implement filtering to avoid processing kanata's own mouse output
  - [ ] Test and verify no infinite loops
  - [ ] Handle edge cases in event filtering

- [ ] **Error handling & fallbacks**
  - [ ] Graceful degradation if mouse capture fails
  - [ ] Ensure keyboard functionality continues working
  - [ ] Handle system sleep/wake scenarios

### Testing & Validation
- [ ] **Functional testing**
  - [ ] Test with various mouse devices
  - [ ] Test all supported mouse events
  - [ ] Test configuration options
  - [ ] Test --list mouse device display
  
- [ ] **Performance testing**
  - [ ] Verify performance metrics meet requirements
  - [ ] Test under high mouse activity
  - [ ] Memory leak testing
  
- [ ] **Integration testing**
  - [ ] Test alongside existing keyboard functionality
  - [ ] Test with various kanata configurations
  - [ ] Test permission scenarios

## Coordination Tasks

### Communication
- [ ] **GitHub issue creation**
  - [ ] Create comprehensive issue for macOS mouse input support
  - [ ] Tag @jtroo for coordination with winmouse work
  - [ ] Document current state and proposed approach

- [ ] **Progress updates**
  - [ ] Regular updates on research findings
  - [ ] Coordinate with Windows winmouse timeline  
  - [ ] Share architectural decisions for cross-platform consistency

### Cross-platform Alignment
- [ ] **Monitor winmouse development**
  - [ ] Review Windows mouse input patterns as they develop
  - [ ] Identify reusable patterns and structures
  - [ ] Plan for consistent configuration options

- [ ] **Design coordination**
  - [ ] Ensure InputEvent structures are compatible
  - [ ] Align mouse device listing formats
  - [ ] Coordinate configuration option naming

---

**Next Action**: Start with CGEventTap API research and basic proof of concept
**Priority**: Phase 1 research tasks to validate technical approach
**Timeline**: Complete Phase 1 by end of week 1, then reassess based on findings