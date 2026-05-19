# Hand Controller

Hand-tracking mouse and keyboard controller ito na gumagamit ng:
- MediaPipe for hand tracking
- rule-based mouse at keyboard interaction
- MLP para sa high-level commands (`toggle`, `hold`, `undo`; `redo` temporarily disabled)

## Ano Ang Gumagana Ngayon
- mouse movement
- left click, right click, double click
- drag and drop
- ML `toggle`, `hold`, `undo`; `redo` temporarily disabled
- on-screen keyboard overlay
- 2-page keyboard (`ABC` + `123/symbols`)
- `Shift`, `Caps Lock`, `Backspace`, `Space`, `Enter`, `ESC`, `TAB`
- trusted-hand lock para hindi basta makontrol ng ibang taong nadaanan ng camera
- side-view safety para sa rule-based press gestures
- camera source refresh, fallback, at live camera switching
- dark mode by default

## Quick Start Para Sa Testers
Kung ite-test mo lang ang current app, ito lang ang gawin:

```powershell
.\setup-tester.ps1
.\run-tester.ps1
```

Ito ang gagamitin ng tester flow:
- [requirements.txt](requirements.txt)
- [tuning.testing.json](tuning.testing.json)

Tester guide:
- [group-testing.md](docs/group-testing.md)

## Manual Setup
Python 3.11 ang gamitin.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
pip install mediapipe==0.10.21 --no-deps
```

## Recommended Run
```powershell
python -m hand_controller --validate
python -m hand_controller --ui-live --tuning .\tuning.testing.json
```

`--ui-live` ang main app path:
- control panel window
- transparent overlay
- mouse control
- keyboard overlay
- live hand tracking

## Main Controls

### Trusted Hands
- on launch: ilagay ang hand sa subtle center guide, then hold still until `Hand Locked`
- only trusted hands can move, click, type, or trigger ML commands
- first-hand lock guide stays hidden when no hand is detected, then appears when a hand enters the camera view
- kapag keyboard is visible, puwedeng idagdag ang second trusted hand by moving it into the center guide zone
- kapag keyboard opens with one trusted hand, a short helper hint tells the user how to add the second hand
- trusted hands use the normal cyan skeleton; untrusted detected hands are dim gray
- if all trusted hands are lost too long, the center guide returns and control actions are blocked until a hand is locked again

### Mouse Control
- move: thumb-index midpoint follows the screen position directly, palm facing sa camera
- left click: thumb + index pinch
- right click: thumb + middle pinch
- double click: two quick left-click pinches
- drag: hold the left pinch; brief hand-tracking dropouts during drag are buffered before dropping
- ML `hold`: clutch/freeze; hold closed fist to freeze, reposition your hand, then release to keep the cursor in place with a temporary offset
- reset cursor: thumb + pinky pinch; ibabalik ang cursor sa current hand position
- ML `toggle`: on/off ng control without stopping recognition
- ML `undo`: `Ctrl+Z`
- ML `redo`: temporarily disabled; no action muna
- note: kapag masyadong side-view ang kamay, binablock ang accidental rule-based press gestures for safety

### Keyboard Overlay
- show/hide keyboard: hold thumb + ring pinch
- mouse cursor still follows the hand while the keyboard is visible
- press key: i-hover ang key, then thumb + index pinch
- backspace: thumb + middle pinch
- `ABC` / `123`: lipat ng keyboard page
- `Shift` and `Caps Lock`: on-screen keys; makikita ang state nila sa overlay

## Tuning Files
- [tuning.testing.json](tuning.testing.json)
  Shared baseline para sa group testing
- [tuning.local.json](tuning.local.json)
  Personal local adjustments
- [tuning.recommended.json](tuning.recommended.json)
  Optional reference preset

## Camera Source Notes
- `Camera Source` uses real camera indices internally.
- Kapag available sa Windows, best-effort na lumalabas ang hardware names sa UI.
- `Refresh` re-scans available cameras without restarting the app.
- while running, changing `Camera Source` does a controlled live switch instead of waiting for the next launch.
- if the saved camera disappears, the app can fall back to another usable source.

## Ibang Useful Commands
```powershell
python -m hand_controller --ui-smoke
python -m hand_controller --control-smoke --tuning .\tuning.local.json
python -m hand_controller --vision-smoke
python -m hand_controller --validate
```

## Project Docs
- [group-testing.md](docs/group-testing.md)
- [handoff.md](docs/handoff.md)
- [architecture.md](docs/architecture.md)
- [gesture-spec.md](docs/gesture-spec.md)
- [packaging-portable.md](docs/packaging-portable.md)
- [packaging-installer.md](docs/packaging-installer.md)
- [release-checklist.md](docs/release-checklist.md)
