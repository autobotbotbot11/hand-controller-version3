# Gesture Spec v1

This document freezes the meaning of each gesture before implementation starts.

## System states
- `control_enabled`: when `False`, recognition still runs, but control actions are blocked.
- `keyboard_visible`: when `True`, the on-screen keyboard is shown as an overlay on top of the normal mouse controller.
- `trusted_hands`: hands locked through the center overlay guide; untrusted hands are ignored for control actions.
- `movement_enabled`: mouse movement is allowed only when all required gates pass.
- `press_gestures_safe`: shared safety gate for rule-based press-like gestures.

## Trusted hand ownership
- The app starts without an action-capable hand until a hand is locked.
- The transparent overlay shows a subtle center guide: `Place hand here`, then `Hold still`.
- If no hand is detected and no hand is locked, the first-hand guide stays hidden except for a short no-hand grace window to avoid flicker.
- Holding a press-safe hand in the guide for the configured time locks it as trusted and shows `Hand Locked`.
- Mouse, keyboard, and ML command behavior only use trusted hands.
- Up to two trusted hands can be locked so the keyboard can still support two-hand typing.
- One trusted hand is enough to start; a second hand can be added later while the keyboard overlay is visible.
- When the keyboard opens with one trusted hand, a short helper hint explains that the other hand can be moved to center to add it.
- The optional second-hand guide stays hidden until an untrusted hand is placed inside the lock zone.
- Trusted hands use the normal cyan skeleton; untrusted detected hands render as dim gray so ownership is visible without adding cursor-area UI.
- If a trusted hand disappears briefly, the app tries to reacquire it near its last position.
- If trusted hands are lost too long, their locks expire. When no trusted hands remain, control actions are blocked and the center guide returns.

## MLP classes

### `idle`
- Meaning: valid MLP class with no action.
- Purpose: separate command gestures from non-command poses.
- Important note: open palm and other normal poses may belong to this class.
- Runtime action: none.

### `hold`
- Physical pose: closed fist.
- Runtime meaning: clutch/freeze for hand repositioning.
- Runtime action: mouse movement and mouse clicking are frozen while held.
- Release action: if the hand moved while held, the cursor position is preserved and mouse mapping switches to a temporary offset.
- Important note: the keyboard overlay does not change this; closed fist is no longer required to move the mouse while the keyboard is visible.
- Two-hand note: trusted hands are checked for `hold` before the final active mouse hand is chosen. While `hold` is active, the hand that started the hold remains the mouse/reposition owner; the cursor should not jump to the other trusted hand.
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
- Scope for v1: active when control is enabled.

### `redo`
- Physical pose: second two-finger pose from the original MLP dataset.
- Runtime action: temporarily disabled; no action is emitted.
- Reason: the current MLP can confuse `redo` with `undo`, so `redo` is filtered out until the model is fixed.

### Ignored MLP labels
- `left_click`
- `right_click`

These labels may still be predicted by the existing model, but they will not drive behavior in the rewrite because clicking is rule-based.

## Rule-based gestures

### Palm facing
- Used as a safety gate for mouse control.
- If palm is not facing the camera, mouse movement is disabled.

### Mouse pointer
- Mouse control uses the midpoint between thumb tip and index tip as the cursor target.
- The target maps directly to screen coordinates, matching the keyboard pointer behavior.
- Closed-fist `hold` can temporarily offset this mapping so the user can reposition the hand without moving the cursor.
- Thumb-pinky pinch resets the mapping back to direct thumb-index midpoint control.
- Mouse control draws a thin split thumb-index line for visual aiming, with a clear gap around the cursor midpoint and no midpoint dot.
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
  - keyboard tap / backspace pinches
  - mapping reset
- It does not automatically cancel an already active drag.
- It is intentionally a safety layer only; it does not replace the existing click/toggle logic.

### Left click
- Physical pose: thumb-index pinch.
- Runtime action: quick pinch-and-release = single left click.

### Double click
- Meaning: two quick left tap cycles within the configured interval.
- Runtime action: first click happens on the first release, and a second quick pinch emits an explicit OS double-click action on release.
- If the second pinch is held past the drag threshold, it becomes drag instead of double-click.

### Right click
- Physical pose: thumb-middle pinch.
- Runtime action: pinch down = single right click.

### Drag
- Physical pose: thumb-index pinch held longer than the drag threshold.
- Runtime action: start left-button hold and allow drag movement.
- Release action: releasing the pinch ends the drag.
- Tracking-loss note: if the hand disappears briefly while a drag is already active, the left button remains held for the configured grace window before dropping.
- After a first left tap, holding the second thumb-index pinch past the same drag threshold starts drag instead of double-click.

### Keyboard toggle
- Physical pose: thumb-ring hold.
- Runtime action: toggle `keyboard_visible`.
- This replaces the two-hand keyboard activation logic from codebase 2.
- Safety note: it must pass both the palm-facing rule and the shared press-safety gate.

### Keyboard overlay input
- The keyboard is an on-screen tool layered on top of normal mouse control:
  - pointer hovers over a key
  - current pointer experiment uses the midpoint between thumb tip and index tip
  - thumb-index pinch confirms a key press
  - thumb-middle pinch sends backspace when hovering the keyboard
- `SHIFT` is an on-screen key; activating it arms one-shot shift for the next letter key press
- The overlay renders a thin thumb-index line and a midpoint dot; the midpoint dot is the actual keyboard pointer.
- Safety note: these pinches are blocked when `press_gestures_safe` fails.

## Mouse control rules
- Mouse control only produces actions when `control_enabled` is `True`.
- Mouse movement requires:
  - `control_enabled == True`
  - an active trusted hand exists
  - palm-facing gate passes
  - `hold` is not active
- Cursor target is absolute screen position from the thumb-index midpoint.
- If a closed-fist `hold` starts, the controller freezes the cursor at its current target.
- Releasing `hold` after repositioning preserves the cursor target by applying a temporary mapping offset.
- Thumb-pinky pinch clears that offset and instantly returns to direct thumb-index midpoint mapping.
- Rule-based click/drag-start gestures also require `press_gestures_safe == True`.
- Clicking is blocked while `hold` is active.
- During a left pinch, movement aim-locks to the current cursor target until release or drag start.
- During a right pinch, movement aim-locks to the current cursor target until the pinch is released.
- Aim-lock preserves the motion filter anchor instead of repeatedly resetting it while the pinch is held.
- `undo` is an ML-owned one-shot command; `redo` is temporarily filtered out.

## Keyboard overlay rules
- Keyboard visibility is toggled by the rule-based thumb-ring gesture.
- The mouse controller remains active while the keyboard is visible.
- Keyboard typing only accepts trusted hands.
- A second trusted hand can be added while the keyboard is visible for faster two-hand typing.
- No closed-fist bridge is required to move the mouse while the keyboard is visible.
- If the active pointer is hovering a keyboard key, keyboard actions take priority and mouse clicks are blocked for that frame.
- Outside the keyboard, thumb-index and thumb-middle pinches route through the normal mouse click / drag path.
- If `control_enabled` becomes `False` while the keyboard was visible, the overlay hides visually.
- Re-enabling control restores the keyboard overlay if it was visible before control was turned off.

## Removed or rejected behaviors
- No Alt+Tab action from `hold`.
- No two-hand idle keyboard activation.
- No ML-owned click behavior.
- No dependency on `idle` for movement semantics.
