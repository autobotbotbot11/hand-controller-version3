# Gesture Spec v1

This document freezes the meaning of each gesture before implementation starts.

## System states
- `control_enabled`: when `False`, recognition still runs, but control actions are blocked.
- `mode`: `mouse` or `keyboard`.
- `movement_enabled`: mouse movement is allowed only when all required gates pass.
- `press_gestures_safe`: shared safety gate for rule-based press-like gestures.

## MLP classes

### `idle`
- Meaning: valid MLP class with no action.
- Purpose: separate command gestures from non-command poses.
- Important note: open palm and other normal poses may belong to this class.
- Runtime action: none.

### `hold`
- Physical pose: closed fist.
- Runtime meaning in mouse mode: safety freeze.
- Mouse-mode runtime action: mouse movement off and mouse clicking off.
- Runtime meaning in keyboard mode: quick mouse-control bridge while held.
- Keyboard-mode runtime action: mouse movement on while held, mouse clicking blocked while movement is active.
- Important note: this acts as a safety lock in mouse mode and a deliberate temporary mouse-movement bridge in keyboard mode.
- Removed meaning: this no longer triggers Alt+Tab.

### `toggle`
- Physical pose: L-shape hand pose.
- Runtime meaning: toggle `control_enabled`.
- Runtime action: turn control on or off.
- Important note: camera, MediaPipe, and MLP inference stay running even when control is off so the user can turn control back on with the same gesture.
- Safety note: the pose must be sustained for the configured hold time before toggling.

### `undo`
- Physical pose: two-finger pose from the original MLP dataset.
- Runtime action: `Ctrl+Z`.
- Scope for v1: mouse mode only.

### `redo`
- Physical pose: second two-finger pose from the original MLP dataset.
- Runtime action: `Ctrl+Y`.
- Scope for v1: mouse mode only.

### Ignored MLP labels
- `left_click`
- `right_click`

These labels may still be predicted by the existing model, but they will not drive behavior in the rewrite because clicking is rule-based.

## Rule-based gestures

### Palm facing
- Used as a safety gate for mouse control.
- If palm is not facing the camera, mouse movement is disabled.

### Mouse pointer
- Mouse mode uses the midpoint between thumb tip and index tip as the cursor target.
- The target maps directly to screen coordinates, matching the keyboard pointer behavior.
- Mouse mode draws a thin split thumb-index line for visual aiming, with a clear gap around the cursor midpoint and no midpoint dot.
- Movement can still be smoothed and gated to reduce tiny tracking jitter.

### Press safety gate
- Rule-based press gestures must also pass a shared hand-view safety check.
- The check uses:
  - thumb/pinky palm-facing ordering
  - palm width vs palm length ratio
  - palm-side depth skew as a supporting signal
- Purpose: block accidental press-like actions when the hand is too side-view or visually compressed.
- This gate applies to:
  - left click
  - double click
  - right click
  - drag start
  - keyboard toggle
  - keyboard tap / backspace / shift-related pinches
- It does not automatically cancel an already active drag.
- It is intentionally a safety layer only; it does not replace the existing click/toggle logic.

### Left click
- Physical pose: thumb-index pinch.
- Runtime action: quick pinch-and-release = single left click.

### Double click
- Meaning: two quick left tap cycles within the configured interval.
- Runtime action: first click happens on the first release, and the second quick pinch emits an explicit OS double-click action.

### Right click
- Physical pose: thumb-middle pinch.
- Runtime action: pinch down = single right click.

### Drag
- Physical pose: thumb-index pinch held longer than the drag threshold.
- Runtime action: start left-button hold and allow drag movement.
- Release action: releasing the pinch ends the drag.

### Keyboard toggle
- Physical pose: thumb-ring hold.
- Runtime action: toggle `mode` between `mouse` and `keyboard`.
- This replaces the two-hand keyboard activation logic from codebase 2.
- Safety note: it must pass both the palm-facing rule and the shared press-safety gate.

### Keyboard input
- Keyboard mode uses the cleaner codebase 1 behavior:
  - pointer hovers over a key
  - current pointer experiment uses the midpoint between thumb tip and index tip
  - thumb-index pinch confirms a key press
  - thumb-middle pinch sends backspace when hovering the keyboard
  - thumb-pinky pinch arms one-shot shift for the next letter key press
- The overlay renders a thin thumb-index line and a midpoint dot; the midpoint dot is the actual keyboard pointer.
- Safety note: these pinches are blocked when `press_gestures_safe` fails.

## Mouse mode rules
- Mouse mode only produces actions when `control_enabled` is `True`.
- Mouse movement requires:
  - `control_enabled == True`
  - `mode == mouse`
  - palm-facing gate passes
  - `hold` is not active
- Cursor target is absolute screen position from the thumb-index midpoint.
- Rule-based click/drag-start gestures also require `press_gestures_safe == True`.
- Clicking is blocked while `hold` is active.
- During a left pinch, movement aim-locks to the current cursor target until release or drag start.
- During a right pinch, movement aim-locks to the current cursor target until the pinch is released.
- Aim-lock preserves the motion filter anchor instead of repeatedly resetting it while the pinch is held.
- `undo` and `redo` are ML-owned one-shot commands in mouse mode.

## Keyboard mode rules
- Keyboard toggle is rule-based.
- Keyboard interaction logic comes from the codebase 1 design, not from the codebase 2 two-hand idle logic.
- Closed-fist `hold` has a narrow special meaning in keyboard mode: it enables quick mouse movement while held.
- While keyboard-mode hold movement is active:
  - keyboard keys visually dim
  - mouse clicking is blocked
  - the existing mouse movement controller handles cursor movement
- When not holding closed fist, outside-keyboard thumb-index pinch routes through the existing mouse left-click / drag path.
- When not holding closed fist, outside-keyboard thumb-middle pinch routes through the existing mouse right-click path.
- If the pointer is hovering a keyboard key, keyboard actions take priority over outside-keyboard mouse clicks.
- `undo` and `redo` are ignored in keyboard mode for v1.
- If `control_enabled` becomes `False` while keyboard mode was active, the keyboard overlay hides immediately.
- Re-enabling control restores the previous mode instead of forcibly switching back to mouse mode.

## Removed or rejected behaviors
- No Alt+Tab action from `hold`.
- No two-hand idle keyboard activation.
- No ML-owned click behavior.
- No dependency on `idle` for movement semantics.
