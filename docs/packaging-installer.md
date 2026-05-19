# Installer Packaging Notes

This is the preview installer path for turning the app into a more formal Windows desktop app.

## Goal

Build a real Windows installer that:
- installs the packaged app to a normal app directory
- creates Start Menu and optional desktop shortcuts
- adds uninstall support
- still keeps packaging separate from the app's core logic

This is still a packaging layer around the current portable build, not a signal that the app is already feature-complete.

## Current installer style

- tool: Inno Setup 6
- installer script: [hand_controller_installer.iss](../hand_controller_installer.iss)
- build script: [build-installer.ps1](../build-installer.ps1)

## Build order

The installer build depends on the portable build first.

`build-installer.ps1` does this:
1. runs [build-portable.ps1](../build-portable.ps1)
2. locates the Inno Setup compiler
3. builds a `Setup.exe` from the current `dist\HandController` output

## Build command

From the repo root:

```powershell
.\build-installer.ps1
```

Optional version override:

```powershell
.\build-installer.ps1 -Version "0.2.0-preview"
```

Use a new version value for each installer that will be shared with testers or users. This avoids confusion with older installers.

## Tool requirement

The compiler is:
- Inno Setup 6

If it is missing, install it with:

```powershell
winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
```

## Output

Expected installer output folder:

```text
release\installer\
```

Expected installer file:

```text
release\installer\HandController-Setup.exe
```

## Current installer behavior

The preview installer currently:
- installs per-user by default to `LocalAppData\Programs\Hand Controller`
- creates a Start Menu shortcut
- optionally creates a desktop shortcut
- adds uninstall support
- can launch the app immediately after install

## Current limitations

- still a preview installer flow
- no code signing yet
- no final product versioning policy yet
- no final corporate metadata or publisher identity yet
- the app itself is still under active development
- Windows may show unknown-publisher or SmartScreen warnings until code signing is added

## Packaging intent

The installer exists to prove the rewrite can be packaged like a formal desktop app.

It should not drive product decisions backward into the source code unless a packaging fix is clearly justified.

See [release-checklist.md](release-checklist.md) before sharing a new installer.
