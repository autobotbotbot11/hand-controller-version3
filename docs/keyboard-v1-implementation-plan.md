# Keyboard V1 Implementation Plan

Historical note:
- this file is a keyboard implementation-planning reference
- it may still mention old phase wording and older intermediate assumptions
- some original V1 assumptions below have been superseded by later UX experiments, especially the keyboard-mode quick mouse bridge
- for the current app state and latest behaviors, prefer:
  - `docs/handoff.md`
  - `docs/gesture-spec.md`
  - `docs/architecture.md`
  - `docs/phase-plan.md`

Superseded behavior note:
- current app behavior now allows a narrow MLP `hold` use in keyboard mode for quick mouse movement only
- current app behavior also allows outside-keyboard pinches to route through mouse clicking while keyboard mode remains active

This document turns the keyboard design contract into a practical implementation sequence.

The goal is to implement Keyboard V1 without destabilizing the already-working mouse path.

## Working assumptions

Unless changed later, Keyboard V1 will assume:
- original plan: keyboard remains pure rule-based
- current app exception: MLP `hold` can enable keyboard-mode quick mouse movement while held
- the current OpenCV keyboard smoke path is temporary only
- the final keyboard UI must move to a real Qt transparent overlay
- the keyboard must support a practical complete key set
- existing mouse behavior must remain testable while keyboard work progresses

## Recommended V1 key set

This is the default practical set we should target first.

### Row 1
- `ESC`
- `1`
- `2`
- `3`
- `4`
- `5`
- `6`
- `7`
- `8`
- `9`
- `0`
- `BACKSPACE`

### Row 2
- `TAB`
- `Q`
- `W`
- `E`
- `R`
- `T`
- `Y`
- `U`
- `I`
- `O`
- `P`

### Row 3
- `A`
- `S`
- `D`
- `F`
- `G`
- `H`
- `J`
- `K`
- `L`
- `;`
- `'`
- `ENTER`

### Row 4
- `SHIFT`
- `Z`
- `X`
- `C`
- `V`
- `B`
- `N`
- `M`
- `,`
- `.`
- `/`

### Row 5
- `SPACE`
- `-`
- `_`
- `?`
- `!`
- `(`
- `)`

This does not have to look exactly like a physical keyboard.
It only needs to be:
- complete enough for realistic demo typing
- visually clear
- easy to hover and press

## Implementation strategy

The safest sequence is:

1. Keep the current control smoke runner as a temporary integration environment.
2. Build the real Qt UI architecture beside it.
3. Move keyboard rendering to the overlay first.
4. Keep keyboard action logic reusable and independent of the renderer.
5. Only after overlay rendering is stable, connect the full complete key set.

## Phases

### Phase K1: UI foundation

Goal:
- introduce the real UI architecture from codebase 1 into the rewrite

Deliverables:
- `ui/signals.py`
- `ui/overlay_window.py`
- `ui/main_window.py`
- integration path from app entry to control panel window

Rules:
- overlay is renderer-only
- worker thread does not touch widgets directly
- signal bus carries overlay payloads

Exit criteria:
- app launches a control panel window
- Start/Stop works
- a transparent overlay window can open and close cleanly

### Phase K2: Overlay payload model

Goal:
- define the stable payload sent from runtime to overlay

Payload should include:
- mode
- control_enabled
- keyboard_visible
- highlight labels
- finger pointers
- skeleton lines
- keyboard layout rectangles
- status text
- optional selfie frame

Rules:
- payload must be explicit and documented
- rendering details must not leak back into controller logic

Exit criteria:
- overlay can render static mock payloads without the CV loop

### Phase K3: Keyboard overlay rendering

Goal:
- render the keyboard in the transparent overlay instead of the OpenCV window

Deliverables:
- key rectangles
- hovered highlights
- pointer circles
- skeleton lines
- keyboard/mode status text

Rules:
- preserve codebase 1 strengths
- improve code cleanliness and configurability

Exit criteria:
- overlay visually shows keyboard mode correctly on the desktop

### Phase K4: Data-driven keyboard layout

Goal:
- replace simplified layout assumptions with a complete configurable key model

Deliverables:
- layout config structure
- complete practical key set
- width-unit based sizing
- adjustable margins and spacing

Rules:
- layout must be data-driven
- adding/removing keys should not require controller rewrites

Exit criteria:
- the full V1 key set appears correctly on overlay
- layout changes can be done through config

### Phase K5: Keyboard controller integration

Goal:
- connect the existing rule-based keyboard actions to the overlay-rendered layout

Behavior:
- hover key with pointer
- thumb-index pinch = key press
- thumb-middle pinch = backspace
- thumb-pinky pinch = one-shot shift

Rules:
- keep keyboard pure rule-based
- keep keyboard behavior separate from MLP behavior

Exit criteria:
- actual typing works against the overlay layout

### Phase K6: Mode integration cleanup

Goal:
- make keyboard mode and mouse mode transitions clean

Rules:
- thumb-ring toggle remains rule-based
- original plan: keyboard mode disables mouse movement/click behavior
- current app exception: closed fist enables quick mouse movement while held, and outside-keyboard pinches may route through mouse clicking
- MLP `undo` and `redo` remain ignored in keyboard mode

Exit criteria:
- switching mouse <-> keyboard is stable and predictable

### Phase K7: Config exposure

Goal:
- make keyboard layout and gesture feel user-configurable

Config should cover:
- layout rows
- width units
- side margins
- row gaps
- key gaps
- font sizes
- pointer radius
- gesture thresholds
- mode toggle hold/cooldown
- overlay show/hide options

Exit criteria:
- tuning the keyboard does not require editing controller logic

### Phase K8: Validation and polish

Goal:
- validate real typing behavior and clean up UX issues

Checklist:
- overlay opens and closes cleanly
- keyboard mode toggle is reliable
- pointer hover is accurate
- key presses are easy enough to trigger
- backspace works
- one-shot shift works
- keyboard does not visually flicker
- mouse mode still feels unchanged

Exit criteria:
- keyboard is demo-ready for V1

## What should be reused

Reuse from current rewrite:
- runtime state model
- active hand selection
- palm-facing detection
- hand pinch detectors
- current keyboard controller logic where useful
- tuning/config direction

Reuse from codebase 1:
- transparent overlay architecture
- signal bus pattern
- control panel + overlay separation
- screen-space keyboard rendering concept

Do not reuse directly:
- app-level globals everywhere
- simplified hard-coded QWERTY-only keyboard forever
- UI code mixed into controller logic

## Immediate next implementation step

The next actual implementation step should be:

### Start with Phase K1
- create the Qt UI foundation in the rewrite
- control panel window
- transparent overlay window
- signal bus

Reason:
- this is the real missing piece that blocks the final keyboard implementation
- everything else depends on having the correct rendering architecture first

## Ready-to-implement condition

We are ready to implement when:
- the design contract is accepted
- the implementation order is accepted
- the assumed V1 key set is acceptable enough as the starting layout

At this point, the next coding task should be:
- `Phase K1: UI foundation`
