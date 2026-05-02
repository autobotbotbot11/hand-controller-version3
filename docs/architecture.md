# Architecture Contract v1

This rewrite keeps the code modular and intentionally separates perception, decision, and side effects.

## Module layout
- `hand_controller/app.py`
  - top-level entry point
- `hand_controller/config/`
  - frozen settings and tunable defaults
- `hand_controller/vision/`
  - camera access, MediaPipe hand tracking, stable active-hand selection
- `hand_controller/ml/`
  - model loading, label normalization, and MLP adapter
- `hand_controller/gestures/`
  - rule-based gesture utilities and pinch detectors
- `hand_controller/controllers/`
  - mouse controller, keyboard controller, and mode/control-state controllers
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

## Mouse movement strategy
Mouse mode now uses absolute screen-space movement instead of relative hand deltas.

Current movement model:
- stable active-hand selection with hysteresis
- cursor target = midpoint between thumb tip and index tip
- target maps directly to screen coordinates, matching the keyboard pointer mental model
- light smoothing plus wake/sleep thresholds reduce small tracking jitter
- click pinches aim-lock to the current cursor target before release or drag start
- aim-lock preserves the motion filter anchor instead of repeatedly resetting it while the pinch is held
- drag resumes movement after the left-button hold starts
- fast action execution with no extra per-action pause

## Control model
- `control_enabled` is toggled by the MLP `toggle` gesture.
- Recognition continues even when control is disabled.
- `mode` is toggled by a rule-based thumb-ring hold.
- Mouse clicks remain rule-based.
- `hold` is mapped to mouse-mode safety freeze, not Alt+Tab.
- Keyboard mode has one narrow `hold` exception: closed fist enables quick mouse movement while held.
- Keyboard mode is toggled by a rule-based thumb-ring hold and typed with rule-based pinch events.
- In keyboard mode, hovered keys have priority; outside-keyboard thumb-index and thumb-middle pinches can route through the mouse click controller.

## Global safety model
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
- The overlay payload includes a keyboard dim state used when keyboard-mode quick mouse movement is active.
- The current keyboard pointer experiment uses a thumb-index midpoint, with a visible thumb-index line and midpoint dot.
- Mouse mode draws a split thumb-index line only, without a pointer dot, to avoid visually covering native desktop hover feedback near the cursor.

## Initial scope
- Mouse mode
- Keyboard mode
- Control toggle
- Clutch
- Undo / redo
- Minimal UI with room for later tuning controls
