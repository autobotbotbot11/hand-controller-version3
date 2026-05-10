# Group Testing Quick Guide

Use this guide if you only need to test the app and give feedback.

## Setup

Open PowerShell in the repo root and run:

```powershell
.\setup-tester.ps1
```

This will:
- create `.venv` if needed
- install the current app dependencies from `requirements.txt`
- install `mediapipe==0.10.21` with the repo's tested setup

## Run the app

```powershell
.\run-tester.ps1
```

This starts the current live app path:
- control panel window
- transparent overlay
- mouse control
- keyboard overlay
- ML `toggle`, `hold`, `undo`; `redo` temporarily disabled
- async camera refresh and launch preflight
- dark mode by default

It uses:
- `tuning.testing.json`

## What to test

- app start and stop
- trusted-hand lock
  - on launch, place hand in the subtle center guide until `Hand Locked`
  - locked hands should keep the normal cyan skeleton
  - untrusted detected hands should appear dim gray
  - another person's hand should not move/click/type unless it is also locked
- mouse movement smoothness and whether the cursor lines up with the thumb-index midpoint
- left click
- right click
- double click
- drag and drop
- ML `toggle` on/off
- ML `hold` clutch/reposition
  - with two trusted hands visible, closing one hand for hold should not make the cursor jump to the other hand
- thumb-pinky cursor reset
- `undo`
- side-view safety
  - rule-based clicks and keyboard pinches should not fire easily when the hand is too side-view
- keyboard overlay show/hide
- second-hand keyboard lock
  - opening the keyboard with one trusted hand should briefly show a helper hint for adding the other hand
  - with keyboard visible, the second-hand guide should stay hidden until the other hand is in the center zone
  - place the other hand in the center zone until it locks
  - both trusted hands should be able to type
- mouse movement while the keyboard overlay is visible
- typing on the `ABC` page
- switching to the `123/symbols` page
- `Shift`
- `Caps Lock`
- `Backspace`
- `Space`
- `Enter`
- `ESC`
- `TAB`
- `Camera Source`
  - `Refresh`
  - switching sources if another camera is connected
- launch feel
  - `LAUNCH` should minimize quickly
  - overlay/selfie box should appear quickly after launch

## Feedback format

Use simple notes like this:

- mouse movement / pointer alignment: good / bad
- trusted-hand lock: good / bad
- second-hand keyboard lock: good / bad
- left click: good / bad
- right click: good / bad
- double click: good / bad
- drag and drop: good / bad
- ML toggle: good / bad
- ML hold clutch/reposition: good / bad
- thumb-pinky reset: good / bad
- ML undo: good / bad
- side-view safety: good / bad
- keyboard typing: good / bad
- camera source / refresh: good / bad
- launch speed / startup feel: good / bad
- keys with no output: list them
- confusing behavior: describe it briefly

## If setup fails

- make sure Python 3.11 is installed
- close other apps using the camera
- run `python -m hand_controller --validate` inside `.venv` if needed
