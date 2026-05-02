# Keyboard V1 Design Contract

Historical note:
- this file is a keyboard planning/design reference
- it is not the main current source of truth for the whole app anymore
- some original V1 assumptions below have been superseded by later UX experiments, especially the keyboard-mode quick mouse bridge
- for the current app state and latest behaviors, prefer:
  - `docs/handoff.md`
  - `docs/gesture-spec.md`
  - `docs/architecture.md`
  - `docs/phase-plan.md`

Superseded behavior note:
- this file still records the original "pure rule-based keyboard" direction
- current app behavior now allows a narrow MLP `hold` use in keyboard mode for quick mouse movement only
- current app behavior also allows outside-keyboard pinches to route through mouse clicking while keyboard mode remains active

This document freezes the intended keyboard design before the rewrite moves further.

The goal is not just to make the keyboard work.
The goal is to make it:
- stable
- fast enough for demo use
- maintainable
- configurable
- cleaner than codebase 1

## Source of truth

Keyboard V1 should preserve the strong UX direction of codebase 1:
- fullscreen transparent overlay
- separate control panel window
- worker-thread CV loop
- UI-thread-only Qt rendering
- keyboard rendered in screen space
- visible skeleton lines and finger pointers

Keyboard V1 should not copy codebase 1 blindly.
It should improve:
- architecture
- state clarity
- configurability
- handoff quality

## Non-negotiable principles

### 1. Keyboard is mostly rule-based
- Original V1 assumption: keyboard interactions should not depend on the MLP.
- Current app exception: MLP `hold` can enable keyboard-mode quick mouse movement while held.
- MLP labels such as `undo` and `redo` must not drive keyboard actions.
- Keyboard typing behavior must remain understandable from geometry and pinch rules only.

### 2. Overlay architecture is required
- The final keyboard UI must not live only in an OpenCV preview window.
- The final keyboard UI must use a real transparent Qt overlay.
- The overlay must be always-on-top and transparent to mouse events.

### 3. Keyboard must be one-hand usable
- The user must be able to enter keyboard mode and type with one hand.
- Two-hand support is allowed, but it is optional enhancement, not a requirement.

### 4. Keyboard must be configurable
- Key sizes
- key spacing
- keyboard height
- keyboard width / margins
- layout content
- gesture thresholds
- toggle timing
- overlay options

These should be config-driven, not hard-coded inside random modules.

## Preserve from codebase 1

### Transparent overlay model
- Separate `MainWindow` control panel
- Separate `OverlayWindow` fullscreen transparent renderer
- Separate signal bus from worker thread to UI thread

### Visual feedback
- keyboard rectangles
- highlighted hovered keys
- finger pointers
- hand skeleton lines
- status text
- optional selfie preview

### Interaction model
- rule-based mode toggle for keyboard
- pointer hover over keys
- pinch-to-type
- keyboard interaction rendered in screen space, not camera-frame-only space

## Improve beyond codebase 1

### Better configuration model
Avoid app-level globals for keyboard behavior.

Keyboard config should live under a typed config section and optional JSON tuning:
- layout
- overlay
- pinch thresholds
- toggle timing
- pointer visuals

### Better state model
Keyboard behavior should fit the rewrite state model cleanly:
- `control_enabled`
- `mode`
- `active_hand_label`
- `palm_facing`
- `hold_active`
- `movement_frozen`

Additional keyboard-specific runtime state should be explicit:
- `shift_one_shot`
- `keyboard_visible`
- `hovered_keys`
- `mode_toggle_in_progress`

### Better lifecycle
- clean start
- clean stop
- clean overlay close
- no unsafe worker-thread widget updates

### Better layout abstraction
The layout must be a real configurable object, not a hard-coded QWERTY-only assumption.

## Final keyboard scope for V1

Keyboard V1 must include:
- transparent fullscreen overlay
- keyboard mode toggle
- complete keyboard layout
- hover highlighting
- pinch-to-type
- backspace
- one-shot shift
- status text
- finger pointers
- skeleton lines

Optional but not required for V1:
- selfie preview
- second-hand pointer support
- layout themes
- multiple keyboard profiles

Not included in V1:
- autocomplete
- prediction
- caps lock state machine
- symbol layers with advanced shortcuts
- fancy animations

## Complete key set

Codebase 1 only showed a simplified QWERTY set.
Keyboard V1 should support a more complete practical layout.

Minimum complete set for V1:
- letters `A-Z`
- digits `0-9`
- `SPACE`
- `BACKSPACE`
- `ENTER`
- `SHIFT`
- `TAB`
- `ESC`
- punctuation:
  - `.`
  - `,`
  - `?`
  - `!`
  - `-`
  - `_`
  - `'`
  - `"`
  - `:`
  - `;`
  - `/`
  - `\\`
  - `(`
  - `)`

Important note:
- V1 does not need to look like a full physical keyboard.
- But the key set must be complete enough for realistic demo input.

## Recommended layout model

The layout should be data-driven.

Suggested model:
- rows of key definitions
- each key has:
  - `label`
  - `action`
  - `width_units`
  - optional shifted display label

Example actions:
- `keypress:a`
- `keypress:1`
- `special:space`
- `special:backspace`
- `special:enter`
- `special:tab`
- `special:esc`

This allows:
- adjustable size
- adjustable spacing
- future layout changes without controller rewrites

## Final rule-based keyboard gestures

### Keyboard mode toggle
- Gesture: thumb-ring pinch hold
- Scope: active hand only
- Safety:
  - must be held for configured duration
  - should preferably require palm-facing
  - must not fire while thumb-index pinch is active

### Key press
- Gesture: thumb-index pinch down
- Behavior:
  - pointer hovers over a key
  - pinch confirms that key

### Backspace
- Gesture: thumb-middle pinch down
- Scope: keyboard mode only

### One-shot shift
- Gesture: thumb-pinky pinch down
- Scope: keyboard mode only
- Behavior:
  - arms shift for next key press only
  - auto-resets after one typed key

## Keyboard mode rules

- Keyboard actions only work when `control_enabled == True`
- `mode` must be `keyboard`
- Original V1 assumption: MLP `hold` is ignored in keyboard mode
- Current app exception: MLP `hold` enables quick mouse movement while held
- MLP `undo` and `redo` are ignored in keyboard mode
- Original V1 assumption: mouse movement and mouse click actions are disabled in keyboard mode
- Current app exception: outside-keyboard pinches may route through mouse clicking when quick mouse movement is not active

## Overlay behavior contract

The overlay should render:
- keyboard layout
- highlighted hovered keys
- pointer circles with hand labels
- skeleton lines
- mode label
- control status
- keyboard status
- optional selfie frame

The overlay must not:
- own gesture recognition logic
- call `pyautogui`
- decide controller behavior

It is a renderer only.

## MainWindow behavior contract

The control panel window should own:
- Start / Stop
- tuning controls
- overlay options
- future settings panel

It should not own:
- CV loop logic
- gesture interpretation
- action execution

## Runtime architecture contract

### Worker thread
Owns:
- camera frame capture
- MediaPipe tracking
- rule-based gesture extraction
- MLP inference
- controller updates
- overlay payload creation

### UI thread
Owns:
- Qt windows
- overlay rendering
- control panel rendering
- signal handling

### Signal bus
Owns:
- safe delivery of overlay payloads from worker thread to UI thread

## Performance contract

Keyboard V1 is acceptable only if:
- overlay feels responsive
- mode switch does not visibly freeze the app
- typing does not require excessive lag compensation
- overlay rendering does not break mouse mode responsiveness

Preferred approach:
- keep the runtime simple first
- add more threading only if measurement proves it is needed

## Config contract

Keyboard V1 config should eventually include at least:

### `keyboard.layout`
- rows
- width units
- side margin
- top/bottom margin
- key gap
- row gap
- keyboard height ratio

### `keyboard.gestures`
- index pinch threshold
- middle pinch threshold
- ring pinch threshold
- pinky pinch threshold
- press/release multipliers
- mode toggle hold seconds
- mode toggle cooldown
- palm-facing requirement

### `keyboard.overlay`
- show skeleton
- show pointers
- show selfie
- selfie position
- selfie scale
- font sizes
- pointer radius

V1 may keep these flattened in one `keyboard` section for simplicity, but the intended design direction is clear.

## What to avoid

- keyboard UI only inside OpenCV preview
- keyboard logic coupled to MLP outputs
- hard-coded QWERTY-only assumption forever
- globals in `app.py` controlling everything
- worker thread directly touching Qt widgets
- mixing renderer code with controller decisions
- adding prediction/autocomplete before the base keyboard is solid

## Acceptance criteria

Keyboard V1 is considered complete when:
- real transparent overlay exists
- keyboard mode is visibly different from mouse mode
- full practical key set exists
- thumb-ring reliably toggles keyboard mode
- thumb-index types hovered keys
- thumb-middle backspaces
- thumb-pinky shifts next key only
- config can adjust layout size and gesture thresholds
- architecture remains clean and documented

## Immediate implementation implication

The current OpenCV-based keyboard smoke path is not the final keyboard implementation.

It can still be used as:
- a controller smoke test
- a gesture tuning environment

But the next real keyboard implementation step must move toward:
- `MainWindow`
- `OverlayWindow`
- `OverlaySignalBus`
- worker-thread overlay payload updates
