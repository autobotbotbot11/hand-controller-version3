# Portable Packaging Notes

This is the current packaging path for turning the app into a shareable Windows app.

## Goal

Build a **portable Windows app folder**:
- no Python install needed on the target machine
- no manual `pip install`
- user runs `HandController.exe`

This is intentionally **not** an installer-first flow.
The portable build remains the base packaging layer even now that a preview installer path exists.

## Current packaging style

- tool: PyInstaller
- output style: `onedir` / portable folder
- build spec: [hand_controller_portable.spec](../hand_controller_portable.spec)
- build script: [build-portable.ps1](../build-portable.ps1)

## Release baseline

Always rebuild the portable app from the current source before sharing it.

Do not reuse an old `dist\HandController` folder after source, assets, artifacts, or tuning files changed.

The generated portable app starts with `tuning.testing.json` copied to:

```text
dist\HandController\tuning.local.json
```

That means `tuning.testing.json` is the default tuning that real users receive. Before making a product build, confirm that this file contains the current known-good values.

## Why this is the first release format

Portable `onedir` is safer for this app than jumping straight to a single-file exe or installer because the project bundles:
- PyQt5
- OpenCV
- MediaPipe
- scikit-learn artifacts
- assets
- tuning files

`onedir` is easier to debug and usually starts faster than a `onefile` build.

## What gets bundled

The current spec bundles:
- app code
- local ML artifacts from `artifacts/`
- image assets from `assets/`
- `tuning.testing.json`
- `tuning.recommended.json`

After the build, the script also copies:
- `tuning.testing.json` -> `dist\HandController\tuning.local.json`

Reason:
- the portable build should start with a known-good tuning file by default

## Build command

From the repo root:

```powershell
.\build-portable.ps1
```

The script:
- uses repo `.venv`
- installs `PyInstaller 6.16.0` into `.venv` if missing
- builds the portable app
- copies a default `tuning.local.json` into the output folder

## Output

Expected output folder:

```text
dist\HandController\
```

Main executable:

```text
dist\HandController\HandController.exe
```

## Packaging-specific runtime behavior

Minimal source support was added so packaging does not require large app rewrites:
- bundled artifacts/assets resolve from the packaged app data root
- default editable tuning resolves from next to the executable

This was intentionally kept narrow so packaging does not distort the app's core behavior.

## Current limitations

- Windows only
- still a preview packaging flow
- installer path now exists separately in `docs/packaging-installer.md`
- no final code-signing or antivirus false-positive hardening yet

## Recommended release ladder

1. fresh portable build
2. test on the developer machine
3. test on another Windows machine without Python
4. build the installer only after the portable output works
5. test the installed app from the real install location

See [release-checklist.md](release-checklist.md) for the current release checklist.
