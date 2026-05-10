# Architecture Contract v1

This rewrite keeps the code modular and intentionally separates perception, decision, and side effects.

## Module layout
- `hand_controller/app.py`
  - top-level entry point
- `hand_controller/config/`
  - frozen settings and tunable defaults
- `hand_controller/vision/`
  - camera access, MediaPipe hand tracking, trusted-hand ownership, stable active-hand selection
- `hand_controller/ml/`
  - model loading, label normalization, and MLP adapter
- `hand_controller/gestures/`
  - rule-based gesture utilities and pinch detectors
- `hand_controller/controllers/`
  - mouse controller, keyboard controller, and keyboard-overlay/control-state controllers
- `hand_controller/runtime/`
  - runtime state and the frame-by-frame orchestration loop
- `hand_controller/ui/`
  - control panel, overlay, selfie preview, quick toolbar, and preview windows

## Design boundaries
- Vision modules return structured hand data only.
- The MLP adapter returns labels and confidence only.
- Controllers decide what should happen.
- The action executor is the only layer allowed to call `pyautogui`.
- UI reads state and displays it; it does not own control logic.

## Rewrite principles
- Start from a frozen contract before adding behavior.
- Build one layer at a time.
- Test each phase before moving forward.
- Prefer simple synchronous runtime flow first.
- Add threading only if profiling shows it is needed later.

Current practical note:
- the app now uses a few targeted background threads where profiling justified them:
  - camera source refresh in the main window
  - launch-time camera preflight
  - UI-live prewarm for ML and MediaPipe cold start
- these are narrow UX/performance helpers, not a general multi-threaded rewrite.

## Mouse Movement Strategy
Mouse control now uses absolute screen-space movement instead of relative hand deltas.

Current movement model:
- stable active-hand selection with hysteresis
- cursor target = midpoint between thumb tip and index tip
- target maps directly to screen coordinates, matching the keyboard pointer mental model
- closed-fist `hold` acts as a clutch: it freezes the cursor, lets the user reposition the hand, then applies a temporary offset on release
- thumb-pinky pinch clears that temporary offset and restores direct mapping to the actual thumb-index midpoint
- light smoothing plus wake/sleep thresholds reduce small tracking jitter
- click pinches aim-lock to the current cursor target before release or drag start
- aim-lock preserves the motion filter anchor instead of repeatedly resetting it while the pinch is held
- drag resumes movement after the left-button hold starts
- active drag has a short tracking-loss grace so fast hand motion does not immediately emit a drop when MediaPipe briefly loses the hand
- second-tap thumb-index hold can become drag instead of double-click if it crosses the drag threshold
- fast action execution with no extra per-action pause

## Control Model
- `control_enabled` is toggled by the MLP `toggle` gesture.
- Recognition continues even when control is disabled.
- `HandOwnershipTracker` filters raw detected hands into trusted hands before selection, pinches, keyboard actions, and ML prediction.
- The first trusted hand is locked through a subtle center overlay guide; a second trusted hand can be added while the keyboard is visible.
- The first-hand guide is hidden while no hand is detected, with a short no-hand grace window to avoid MediaPipe flicker.
- Untrusted hands may still be visible in the overlay skeleton, but they render dim gray and cannot produce actions.
- `keyboard_visible` is toggled by a rule-based thumb-ring hold.
- The keyboard is an overlay tool; it does not replace mouse control.
- Mouse clicks remain rule-based.
- `hold` is mapped to clutch/freeze, not Alt+Tab.
- The engine checks trusted hands for ML `hold` before finalizing the active mouse hand, then latches the mouse/reposition owner so two-hand keyboard use cannot make the cursor jump to the other trusted hand.
- While the keyboard is visible, hovered keys have priority; outside-keyboard thumb-index and thumb-middle pinches route through the mouse click controller.

## Global Safety Model
- Ownership is the first action gate: if no trusted hand is active, mouse, keyboard, and ML command actions do not use raw detected hands.
- Mouse movement and rule-based press gestures are not treated the same.
- Movement still depends primarily on the palm-facing gate and existing mouse-state rules.
- Press-like rule-based actions now share an extra hand-view safety layer based on hand geometry.
- That shared safety layer blocks accidental side-view activations for:
  - left click
  - double click
  - right click
  - drag start
  - keyboard toggle
  - keyboard typing pinches
  - thumb-pinky mapping reset
- The shared gate is computed once per frame and reused across controllers.

## Camera and launch behavior
- Camera source selection is still index-based at runtime.
- The UI now uses best-effort Windows camera names when available, but indices remain the real source of truth.
- Camera source refresh is asynchronous.
- Launch uses an asynchronous preflight instead of blocking the UI thread.
- The main window can minimize immediately while camera verification continues in the background.
- The overlay placeholder can appear before the real worker loop is fully ready.
- On Windows, camera opening now prefers `CAP_DSHOW` first because profiling showed it is faster on the target setup.

## UI behavior notes
- Main window theme defaults to `Dark`.
- `System Default` resolves to the real Windows app-theme preference when available, and falls back to the Qt palette heuristic otherwise.
- The UI-live path prewarms ML model loading and MediaPipe startup in the background so launch feels faster without changing runtime semantics.
- The fullscreen transparent `OverlayWindow` renders keyboard keys, hand skeletons, keyboard pointers, and gesture command text.
- The camera selfie preview is a separate frameless always-on-top `SelfieWindow`, not part of the transparent overlay painter.
- `SelfieWindow` is draggable, resizable from all four corners, keeps a 4:3 aspect ratio, shows controls only on hover, and persists custom position/size through keyboard tuning updates.
- `QuickToolbarWindow` is a separate frameless quick-tools window for selfie visibility, skeleton visibility, and reopening the main panel.
- The quick toolbar can dock to left, right, top, or bottom and persists its edge/offset.
- The current keyboard pointer experiment uses a thumb-index midpoint, with a visible thumb-index line and midpoint dot.
- Mouse control draws a split thumb-index line only, without a pointer dot, to avoid visually covering native desktop hover feedback near the cursor.

## Initial scope
- Mouse control
- Keyboard overlay
- Control toggle
- Clutch
- Undo; redo is temporarily disabled until the MLP conflict is fixed
- Minimal UI with room for later tuning controls
