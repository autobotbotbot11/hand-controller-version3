# Handoff Notes

This file is the fastest way for a future AI or collaborator to understand the rewrite without relying on old chat history.

## Project summary

This project is a clean rewrite of a hand-based mouse and keyboard controller using:
- MediaPipe for hand tracking
- an existing MLP model for a small set of high-level gestures
- rule-based logic for precise click behavior and keyboard behavior

The rewrite exists because the original project split into two codebases with conflicting designs:
- `C:\Users\acer\school\self-study\programming\projects\computer-vision-mouse-control\hand_controller`
  - organized architecture
  - good clicking
  - keyboard flow is better
  - mouse movement is unstable
- `C:\Users\acer\school\self-study\programming\projects\computer-vision-mouse-control\touch-v15`
  - smooth mouse movement
  - working MLP artifacts
  - messy runtime semantics and confusing code

The rewrite must not merge those repos blindly. It should reuse ideas from both in a controlled, incremental way.

## Frozen decisions

These decisions are intentional and should not be changed casually.

### Control toggle
- ML `toggle` uses the L-shape pose.
- It toggles `control_enabled` only.
- It must not stop camera capture, MediaPipe, or MLP inference.
- It should require a short sustained hold before toggling.
- Reason: the user must be able to turn control back on using the same gesture while the app is still running.

### Hold clutch / safety freeze
- ML `hold` uses the closed-fist pose.
- `hold` now means clutch/freeze.
- While held, it disables mouse movement and mouse clicks.
- On release, if the hand was repositioned, the cursor target is preserved by applying a temporary mouse-mapping offset.
- In two-hand keyboard use, trusted hands are checked for ML `hold` before final active-hand selection. The hand that starts `hold` remains the mouse/reposition owner until release, so the cursor does not jump to the other trusted hand.
- Thumb-pinky pinch clears that offset and instantly returns to direct thumb-index midpoint mapping.
- The keyboard overlay does not change this; closed fist is no longer a quick mouse-control bridge.
- Reason: mouse control remains active while the keyboard is visible, so a separate closed-fist bridge is no longer needed.

### Idle
- `idle` is a real MLP class.
- It means no command action.
- It is not equivalent to "no hand detected".
- It may include open palm and other non-command poses.

### Click ownership
- Final behavior for mouse clicks is rule-based.
- `left click` = quick thumb-index pinch-and-release
- `double click` = first left tap releases normally, then the second quick pinch emits an explicit OS double-click action on release
- `double_click_assist_window` limits how long the second-tap path stays eligible
- `right click` = thumb-middle pinch down
- `drag` = thumb-index pinch held long enough to trigger left-button hold, including second-tap hold after a first click
- Existing MLP labels `left_click` and `right_click` may still be predicted, but they must not drive behavior in the rewrite.

### Trusted hand ownership
- Raw MediaPipe hands are not automatically action-capable.
- A hand must be locked through the subtle center overlay guide before it can control mouse, keyboard, or ML commands.
- If no hand is detected and no hand is locked, the first-hand guide stays hidden except for a short no-hand grace window.
- One trusted hand is enough to start.
- Up to two trusted hands can be locked so keyboard typing can use both hands.
- Opening the keyboard with one trusted hand shows a short helper hint for adding the other hand.
- The optional second-hand guide remains hidden until an untrusted hand is placed in the center lock zone while the keyboard overlay is visible.
- Trusted hands use the normal cyan skeleton; untrusted detected hands are rendered dim gray instead of getting cursor-area markers.
- Brief hand loss is reacquired near the last trusted-hand position; longer loss expires the lock.
- If no trusted hands remain, control actions are blocked and the center guide returns.
- Reason: a person passing behind the user must not be able to steal cursor or keyboard control.

### Keyboard
- Keyboard logic should follow the better design from `hand_controller`.
- Keyboard visibility is toggled by a rule-based thumb-ring hold.
- Do not use the two-hand idle keyboard activation logic from `touch-v15`.
- Keyboard is an on-screen overlay tool layered on top of normal mouse control.
- Keyboard overlay includes:
  - keyboard pointer = midpoint between thumb tip and index tip
  - visible pointer guidance: thin line from thumb tip to index tip plus a midpoint dot
  - thumb-index pinch to type hovered key
  - thumb-middle pinch for backspace when hovering the keyboard
  - on-screen `SHIFT` key for one-shot Shift
  - outside-keyboard thumb-index pinch routes through the normal mouse left-click / drag path
  - outside-keyboard thumb-middle pinch routes through the normal mouse right-click path
- Mouse cursor movement continues while the keyboard overlay is visible.
- Hovered keyboard keys take priority over mouse clicks.
- The midpoint pointer is still an experiment, not a permanent final UX decision.

### Undo / Redo
- Keep both in the rewrite.
- `undo` = `Ctrl+Z`
- `redo` is temporarily disabled and emits no action.
- Reason: the current MLP can confuse `redo` with `undo`; re-enable it after the model is fixed.
- These are ML-owned commands.
- Recommended scope for v1: mouse control layer.

## Known physical MLP gesture poses

Based on user-provided labeled sample images:
- `hold` = closed fist
- `left_click` = thumb-index pinch
- `right_click` = thumb-middle pinch
- `toggle` = L-shape hand pose
- `undo` = side-oriented two-finger pose
- `redo` = front/upright two-finger pose
- `idle` = many non-command hand poses; it is a negative class, not absence of detection

## Why the rewrite is phased

The project should be built incrementally so every phase is testable before moving on.

The most important rule:
- do not add new complexity before the current layer is stable

Example:
- do not add clicking before mouse movement is stable
- do not add ML behavior before the base mouse controller is coherent
- do not add keyboard overlay behavior before mouse control is solid

## Dependency baseline

Target runtime:
- Python 3.11

Current install strategy:
- `requirements.txt`
  - consolidated app dependencies for tracking, UI, mouse control, and ML loading
- `mediapipe==0.10.21 --no-deps`
  - still installed separately in the tested setup flow
- `tuning.local.json`
  - optional repo-root JSON overrides that let the user tune click and movement behavior without editing Python code
- `tuning.recommended.json`
  - recommended preset for testing the current click/drag behavior without relying on whatever values are in `tuning.local.json`
- `tuning.testing.json`
  - shared tester baseline used by `run-tester.ps1`

Reason:
- this avoids pulling unnecessary heavy MediaPipe extras too early
- the MLP artifacts should still load later under `scikit-learn==1.7.2`

## Current status

Completed:
- Phase 0: project contract
- Phase 1: package skeleton
- Phase 2 baseline code: camera wrapper, MediaPipe tracker wrapper, structured hand extraction, and a vision smoke runner
- Phase 2 validated on the user's machine: left and right hands are detected correctly
- Phase 3 baseline code: stable primary-hand selection with hysteresis and palm-facing safety detection
- Phase 3 validated on the user's machine
- Phase 4 validated on the user's machine: stable mouse movement is smooth and usable
- Phase 5 click/drag refactor code: release-based left tap, easier double-click path, down-triggered right click, hold-to-drag, JSON tuning overrides, and updated `--mouse-smoke`
- Phase 6 baseline code: MLP predictor, action adapter, fallback artifact lookup to `touch-v15`, and integrated `toggle` / `hold` / `undo` in `--mouse-smoke`; `redo` is currently disabled as a no-op
- Phase 8 baseline code: rule-based thumb-ring keyboard overlay toggle, keyboard overlay, pinch-to-type keypresses, backspace gesture, one-shot Shift support, and integrated control smoke runner
- Phase K1 foundation code: `ui/main_window.py`, `ui/overlay_window.py`, `ui/signals.py`, typed overlay payloads, and `--ui-smoke` for validating the Qt overlay architecture
- Phase K2/K3 baseline code: `runtime/ui_live_control.py` and `--ui-live` now run the real CV worker through the Qt control panel + transparent overlay path
- Phase K4 baseline code: `controllers/keyboard_controller.py` now builds a data-driven full keyboard layout with a complete practical key set and configurable row/size/width settings
- Phase K6 cleanup code: `runtime/control_engine.py` now centralizes mouse control, keyboard overlay, ML updates, and transition cleanup so both `--control-smoke` and `--ui-live` share the same behavior
- Hardening baseline: local ML artifacts now exist in `artifacts/`, and `runtime/validation.py` provides a repo-local validation command
- Phase K7 config exposure: the Qt overlay now reads keyboard visual settings from `KeyboardConfig`, including selfie size, pointer radius, skeleton visibility, font sizes, and status panel sizing
- Keyboard redesign baseline: `controllers/keyboard_controller.py` now uses a 2-page model (`ABC` + `123/symbols`), fixes punctuation key output mappings, adds `Caps Lock`, and visibly changes alpha-page case for `Shift` / `Caps`
- Current Phase 6 behavior uses configurable ML settings under the `ml` section of the tuning JSON files.
- Main window designer adaptation: the current Qt control panel now follows the newer designer direction closely enough in both light and dark mode, with custom nav/buttons/toggles/sliders/combos/help badges and a depth-field dark background
- Theme behavior:
  - default theme is now `Dark`
  - `System Default` uses the real Windows app-theme registry value when available and falls back to the Qt palette heuristic otherwise
- Camera-source hardening:
  - camera source labels now use best-effort Windows device names when available
  - camera refresh is asynchronous
  - launch-time camera fallback/feedback exists
  - live camera switching while running is supported through a controlled restart path
  - Windows camera open now prefers `CAP_DSHOW` first because it is faster on the target machine
- Launch/startup hardening:
  - launch preflight now runs off the UI thread
  - the main window can minimize immediately while launch verification continues
  - the overlay placeholder can appear before the full worker is ready
  - UI-live startup now prewarms ML and MediaPipe in the background to reduce perceived launch delay
- Rule-based safety hardening:
  - all rule-based press-like gestures now share a hand-view safety gate to reduce side-view false positives
  - this covers left/right/double click, drag start, keyboard toggle, and keyboard typing pinches
  - movement is not fully blocked by this gate; it is only for press-like activations
- Trusted-hand ownership:
  - `vision/hand_ownership.py` filters raw detections into trusted hands before selection and action logic
  - the Qt overlay shows a subtle center guide for locking the first hand and adding a second keyboard hand
  - untrusted detected hands can still be drawn, but they cannot produce mouse, keyboard, or ML actions
- Control toggle polish:
  - if the keyboard overlay is visible and the user turns control off with the ML `toggle`, the keyboard overlay hides visually
  - turning control back on restores the keyboard overlay if it was previously visible
- Keyboard UX experiments:
  - the keyboard hover/click point currently uses the thumb-index midpoint instead of raw index tip
  - the overlay draws the thumb-index line and midpoint dot so the user can judge the behavior clearly
  - keyboard is now an overlay tool, not a separate user-facing mode
  - mouse movement remains active while the keyboard overlay is visible
  - outside-keyboard pinches can click, and hovered keyboard keys keep keyboard priority
- Mouse UX / click polish:
  - mouse control draws a split thumb-index line only, without a pointer dot, to avoid visually covering native desktop hover feedback near the cursor
  - explicit OS double-click uses a shorter click interval to reduce perceived lag during the second tap
  - mouse click pinches now use aim-lock instead of repeatedly resetting the motion filter while the pinch is held
  - second-tap thumb-index pinch now waits for release vs hold: quick release emits explicit double-click; hold past the drag threshold starts drag
  - closed-fist `hold` now works as a clutch for hand repositioning, and thumb-pinky pinch resets the mouse mapping back to direct control
- Selfie / quick-tools UX:
  - the selfie camera preview is now a separate frameless always-on-top `SelfieWindow`, not drawn inside the transparent keyboard overlay
  - the selfie preview is draggable, resizable from all four corners, keeps a 4:3 aspect ratio, has hover-only controls, and persists custom position/size through tuning updates
  - the quick toolbar is a separate dockable frameless window with controls for selfie visibility, skeleton visibility, and opening the main panel
  - the quick toolbar can dock to left, right, top, or bottom and persists its edge/offset
- Packaging hygiene:
  - generated installer `.exe` files under `release/installer/` should not be committed to git
  - large installers should be distributed through GitHub Releases or another release channel, not as normal repo files

Current repo-local source of truth:
- `docs/gesture-spec.md`
- `docs/architecture.md`
- `docs/phase-plan.md`
- `docs/packaging-portable.md`
- `docs/packaging-installer.md`
- `docs/group-testing.md`

Historical keyboard planning references:
- `docs/keyboard-v1-design.md`
- `docs/keyboard-v1-implementation-plan.md`

Current package files:
- `hand_controller/app.py`
- `hand_controller/config/settings.py`
- `hand_controller/runtime/state.py`
- `hand_controller/runtime/control_engine.py`
- `hand_controller/runtime/validation.py`
- `hand_controller/ml/labels.py`
- `hand_controller/vision/camera.py`
- `hand_controller/vision/hand_tracker.py`
- `hand_controller/vision/hand_ownership.py`
- `hand_controller/gestures/safety.py`
- `hand_controller/controllers/keyboard_controller.py`
- `hand_controller/controllers/mode_toggle.py`
- `hand_controller/gestures/hand_pinches.py`
- `hand_controller/gestures/mouse_clicks.py`
- `hand_controller/controllers/mouse_controller.py`
- `hand_controller/ui/main_window.py`
- `hand_controller/ui/overlay_window.py`
- `hand_controller/ui/selfie_window.py`
- `hand_controller/ui/quick_toolbar_window.py`
- `hand_controller/ui/payloads.py`
- `hand_controller/ui/signals.py`
- `hand_controller/runtime/ui_foundation_smoke.py`
- `hand_controller/runtime/ui_live_control.py`

Tester-friendly repo entrypoints:
- `requirements.txt`
- `tuning.testing.json`
- `setup-tester.ps1`
- `run-tester.ps1`
- `build-portable.ps1`
- `build-installer.ps1`
- `hand_controller_portable.spec`
- `hand_controller_installer.iss`
- `docs/group-testing.md`

Smoke tests already passed:
- `python -m compileall hand_controller`
- `python -m hand_controller`
- import-level smoke test for the vision modules

## Next exact phase

Current state:
- the rewrite is no longer in "build the baseline" mode
- the app is in stabilization, final UX hardening, and packaging-planning mode
- main window designer adaptation is effectively done enough
- recent work has focused on:
  - false-positive reduction
  - camera robustness
  - startup feel
  - final control-panel polish
  - selfie/quick-toolbar runtime UX
  - keyboard usability as an overlay on top of mouse control

Recommended next work, in order:
1. keyboard UX validation
   - validate trusted-hand lock on launch
   - validate that a passer/untrusted hand cannot move, click, type, or trigger ML commands
   - validate second-hand locking while keyboard is visible
   - test the thumb-index midpoint pointer on small keyboard sizes
   - test normal mouse movement while the keyboard overlay is visible
   - test outside-keyboard left/right click routing
   - test whether keyboard pointer visuals should appear only over keys or over the full screen
   - do not jump to hover latch, pointer freeze, or a keyboard rewrite unless this feedback proves it is needed
2. group testing / real-user validation
   - run `.\run-tester.ps1`
   - collect feedback using `docs/group-testing.md`
3. packaging / actual app distribution planning
   - portable packaged Windows app is already in place
   - preview installer path now exists on top of the portable build
   - next packaging work should focus on release polish, not first-time setup
4. remaining UX edge cases only if testers surface them
   - keyboard feel
   - camera switching edge cases
   - overlay/selfie behavior

If another AI continues from here, do not assume the next task is "Phase K8".
The baseline phases are already implemented. The likely next task is keyboard UX validation or tester-driven bug fixing, not a fresh phase restart.

## Important warnings for future work

- Stable mouse movement is the top priority of the rewrite.
- Movement should adapt the useful algorithmic ideas from `touch-v15` without copying its full architecture.
- The rewrite originally started synchronous and simple; selective background threading now exists only where profiling justified it.
- Prefer the rewrite repo's local `artifacts/` directory as the primary ML source.
- `hold` must not trigger Alt+Tab.
- `toggle` must not kill recognition.
- `idle` must not be used as the basis for movement semantics.
- Keyboard behavior should come from the cleaner `hand_controller` design.
- `undo` is a normal mouse-layer command; `redo` is temporarily disabled as a no-op until the MLP is fixed.
- `hold` is clutch/freeze; do not reintroduce a keyboard-only quick mouse bridge unless there is a strong UX reason.
- Clicking should stay rule-based even if the MLP predicts click labels.
- Mouse movement is now absolute screen-space movement from the thumb-index midpoint, not relative hand deltas.
- Do not remove the shared hand-view press-safety gate unless a better global safety replacement exists.
- Do not remove the Windows `CAP_DSHOW` preference casually; it materially improved startup on the target machine.
- Do not reintroduce form-style `Apply / Discard` UX into the main window; the app's current settings model is intentionally live-change oriented.

## If another AI continues this work

Start by reading:
1. `docs/handoff.md`
2. `docs/gesture-spec.md`
3. `docs/architecture.md`
4. `docs/phase-plan.md`

Then continue only with the next unfinished phase instead of jumping ahead.
