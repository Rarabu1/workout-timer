# Focus Timer Mode Documentation

## Overview

**Focus Timer Mode** is a distraction-free, landscape-oriented interface that automatically activates when your device is rotated horizontally during a workout. It provides a minimalist, high-contrast view focused on the most critical metric: **time remaining in the current interval**.

## When It Triggers

Focus Mode activates automatically when:
- ✅ Device is in **landscape orientation** (horizontal)
- ✅ A workout with intervals is **loaded**
- ✅ Works on iOS Safari, Android Chrome, and desktop browsers

Focus Mode exits when:
- ❌ Device returns to **portrait orientation** (vertical)
- ❌ User presses **Exit button** (top-right ✕)
- ❌ User presses **Escape key**

## UX Rationale

### One-Metric Focus
When running on a treadmill, glancing at your phone should be instant and effortless. Focus Mode emphasizes:
1. **Primary**: Large countdown clock showing seconds remaining in current interval
2. **Secondary**: Speed, incline, interval number, and total time left
3. **Ambient**: Background color that changes based on intensity level

This hierarchy ensures you can see what matters most (time left) at a glance, while still having access to supporting metrics.

### Automatic Activation
No manual mode switching required. Simply:
1. Start your workout in portrait mode
2. Place phone in landscape holder on treadmill
3. Focus Mode activates automatically
4. Rotate back to portrait when done

## Features

### ⏱️ Main Clock
- **Font size**: Responsive (72px–160px)
- **Animation**: Subtle "breathing" effect (respects `prefers-reduced-motion`)
- **Format**: MM:SS with monospaced numerals
- **Updates**: Real-time countdown

### 📊 Secondary Metrics
Four equal-width cards displaying:
1. **Speed**: MPH or KPH (tap to toggle)
2. **Incline**: Percentage (0-15%)
3. **Interval**: Current/Total (e.g., "3/10")
4. **Total Left**: Total workout time remaining

### 🎨 Intensity Color Mapping

Background color automatically adjusts based on speed intensity:

| Level | Intensity | Speed Range | Color | Hex |
|-------|-----------|-------------|-------|-----|
| 1 | Recovery | < 4.5 mph | Green | `#16A34A` |
| 2 | Easy | 4.5–5.5 mph | Light Green | `#22C55E` |
| 3 | Moderate | 5.5–6.5 mph | Orange | `#F59E0B` |
| 4 | Hard | 6.5–7.5 mph | Dark Orange | `#F97316` |
| 5 | Max | > 7.5 mph | Red | `#EF4444` |

All colors meet **WCAG AA contrast** requirements (≥ 4.5:1 ratio) for text readability.

### 🎮 Controls

**Top-right buttons**:
- **Pause/Resume** (⏸/▶️): Space bar or tap
- **Exit** (✕): Escape key or tap

**Touch targets**: Minimum 44×44px for accessibility

### 📈 Progress Bars

Two progress indicators at the bottom:
1. **Segment Progress**: Current interval completion
2. **Total Progress**: Overall workout completion

### 🔔 Haptics

If device supports vibration:
- **Last 5 seconds** of each interval: Short vibration pulse
- **Workout complete**: Long vibration pattern

### 🔋 Wake Lock

Prevents screen from dimming during workout (requires user gesture on first use).

### ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Pause/Resume |
| Escape | Exit Focus Mode |

### ♿ Accessibility

- **WCAG AA compliant** contrast ratios
- **Reduced motion** support (disables animations)
- **Large touch targets** (44×44px minimum)
- **Keyboard navigation** fully supported
- **Screen reader friendly** (semantic HTML)

## Technical Implementation

### Data Flow

```
Orientation Change → Focus Mode Activated
    ↓
Load intervals into FocusTimer
    ↓
Start precise timing loop (performance.now)
    ↓
Update UI every frame (requestAnimationFrame)
    ↓
Calculate intensity → Get colors → Update background
```

### Modules

#### `orientation.js`
Detects device orientation using multiple methods:
1. Screen Orientation API (primary)
2. window.orientation (iOS fallback)
3. window dimensions (final fallback)

Debounced resize events (150ms) prevent excessive triggers.

#### `intensity-colors.js`
Maps intensity levels (1-5) to color schemes:
- Calculates relative luminance
- Ensures WCAG AA contrast (4.5:1)
- Automatically chooses black or white text
- Generates subtle variants for cards/buttons

#### `focus-timer.js`
Precise interval timer with state machine:
- **States**: idle, running, paused, segment_done, complete
- **Timing**: Uses `performance.now()` for accuracy
- **Progress**: Tracks segment and total workout completion
- **Features**: Wake Lock, haptics, unit conversion (mph/kph)

### Props/Data Shape

```javascript
// FocusTimer state
{
  state: 'running' | 'paused' | 'idle' | 'segment_done' | 'complete',
  currentIntervalIndex: 2,
  totalIntervals: 10,
  segmentRemainingSec: 137.5,
  runRemainingSec: 892.3,
  progressSegment: 54.2,  // percentage
  progressRun: 31.8,      // percentage
  speed: '6.5',           // string (current unit)
  incline: 2,             // percentage
  unitSystem: 'mph' | 'kph',
  colors: {
    name: 'Moderate',
    level: 3,
    bg: '#F59E0B',
    fg: '#000000',
    accent: '#D97706',
    subtle: 'rgba(245, 158, 11, 0.3)',
    contrast: 5.23        // actual ratio
  },
  interval: {
    duration_min: 3,
    duration_sec: 180,
    speed_mph: 6.5,
    incline: 2,
    intensity: 3,
    description: 'Tempo run'
  }
}
```

## Orientation Behavior

### Detection Methods

1. **Modern browsers**: `window.screen.orientation.type`
   - Returns: `portrait-primary`, `landscape-primary`, etc.
   - Most reliable on Android Chrome

2. **iOS Safari fallback**: `window.orientation`
   - Returns: 0 (portrait), 90/-90 (landscape), 180 (upside-down)

3. **Universal fallback**: `window.innerWidth > window.innerHeight`
   - Works everywhere but less precise

### Event Listeners

Listens to multiple events for maximum compatibility:
- `orientationchange` (mobile)
- `resize` (all platforms)
- `screen.orientation.change` (modern API)

Debounced to 150ms to avoid rapid firing.

## Recent Fixes (v2.0)

### Fixed: Random Workout Generation
- Added **🎲 Random Workout** button - no typing required!
- Generates sensible workouts with proper warm-up, intervals, and cool-down
- 5 workout types: Tempo Run, Progressive Run, Interval Training, Endurance Base, Hill Workout
- Durations: 20-45 minutes randomly selected

### Fixed: Unified Timer State
- Portrait and landscape modes now share single timer state
- Seamless handoff when rotating device
- No more timer desyncs or duplicate countdowns
- Timer continues exactly where it left off when switching orientations

### Fixed: Landscape Start Button
- Start/Pause button now fully functional in Focus Mode
- Countdown overlay doesn't block button clicks (`pointer-events: none`)
- Proper state icons: ▶️ (start/resume) vs ⏸ (pause)

### Fixed: Focus Mode Re-entry
- Rotating to landscape always activates Focus Mode
- Rotating back to portrait exits cleanly
- Rotating to landscape again re-enters seamlessly
- No page refresh needed

## Known Limitations

### 1. Wake Lock Requires User Gesture
First activation needs a user tap/click. This is a browser security feature.

**Workaround**: Automatically requested when timer starts.

### 2. Haptics Not Available in PWA
Some iOS PWA contexts don't support `navigator.vibrate()`.

**Workaround**: Feature detection with graceful degradation.

### 3. Portrait → Landscape Delay
Some devices have a 100-200ms delay detecting orientation change.

**Workaround**: Multiple detection methods and debouncing.

### 4. Safari Private Mode
Wake Lock API may be blocked in private browsing.

**Workaround**: Silent failure with console warning.

### 5. Background Tab Throttling
Browsers throttle timers in background tabs.

**Workaround**: Using `requestAnimationFrame` instead of `setInterval`.

## Browser Support

| Browser | Orientation | Wake Lock | Haptics | Overall |
|---------|-------------|-----------|---------|---------|
| iOS Safari 14+ | ✅ | ✅ | ⚠️ | ✅ |
| Android Chrome 80+ | ✅ | ✅ | ✅ | ✅ |
| Firefox Mobile | ✅ | ⚠️ | ✅ | ✅ |
| Desktop Chrome | ✅ | ✅ | ❌ | ✅ |
| Desktop Safari | ✅ | ⚠️ | ❌ | ✅ |

✅ Full support | ⚠️ Partial support | ❌ Not applicable

## Usage Example

```javascript
// Manual activation (for testing)
if (intervals.length > 0) {
  window.enterFocusMode();
}

// Manual exit
window.exitFocusMode();

// Toggle unit system
window.focusTimer.toggleUnitSystem();

// Access current state
const state = window.focusTimer.getState();
console.log(`Time left: ${state.segmentRemainingSec}s`);
```

## Screenshots

### Recovery Intensity (Level 1)
- Background: Green (#16A34A)
- Text: White
- Use: Warm-up, cool-down, easy pace

### Moderate Intensity (Level 3)
- Background: Orange (#F59E0B)
- Text: Black
- Use: Steady state, tempo runs

### Max Intensity (Level 5)
- Background: Red (#EF4444)
- Text: White
- Use: Sprint intervals, max effort

## Performance Considerations

### Rendering Optimization
- CSS transitions: 300ms (smooth but not laggy)
- RAF loop: Updates only when running
- Backdrop filter: Used sparingly (mobile GPU intensive)

### Battery Impact
- Wake Lock: Moderate (prevents sleep)
- RAF loop: Low (pauses when not focused)
- Haptics: Minimal (5s warning only)

**Recommendation**: Keep phone plugged in during long workouts.

## Future Enhancements

### Implemented ✅
- Automatic landscape detection
- Intensity-based colors
- WCAG AA contrast
- Wake Lock
- Haptics
- Keyboard controls
- Reduced motion support

### Planned 🔮
- **3-2-1 Countdown**: Visual countdown when starting new intervals
- **Voice Cues**: Audio announcements (with mute toggle)
- **Pinnable Metric**: Allow user to choose which metric to enlarge
- **Analytics**: Track focus mode usage patterns
- **Custom Colors**: User-defined intensity color schemes
- **Heart Rate Integration**: Show live HR data if connected

## Troubleshooting

### Focus Mode doesn't activate
1. Check that a workout is loaded
2. Verify device is actually in landscape (try different angle)
3. Check browser console for errors
4. Try refreshing the page

### Background color doesn't change
1. Verify intervals have valid speed values
2. Check browser developer tools for CSP errors
3. Try hard refresh (Cmd+Shift+R / Ctrl+F5)

### Haptics not working
1. Check device supports vibration
2. Verify browser permissions
3. Try toggling system-level haptics settings

### Timer appears frozen
1. Check if browser tab is active
2. Verify workout hasn't completed
3. Try pausing and resuming

## Contributing

To extend Focus Mode:

1. **Add new intensity levels**: Edit `INTENSITY_COLORS` in `intensity-colors.js`
2. **Modify detection logic**: Update `orientation.js`
3. **Add new metrics**: Extend `focus-timer.js` state
4. **Style changes**: Edit Focus Mode CSS in `index.html`

Always maintain WCAG AA contrast when changing colors.

## License

Same license as parent project.

