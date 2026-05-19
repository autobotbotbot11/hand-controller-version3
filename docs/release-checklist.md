# Release Checklist

Use this before giving the app to testers or users.

## 1. Confirm The Source Build

From the repo root:

```powershell
.\.venv\Scripts\python.exe -m hand_controller --validate --tuning .\tuning.testing.json
```

Confirm:
- validation reports required imports as `ok`
- ML artifacts load from `artifacts\`
- `tuning.testing.json` contains the current known-good tuning

## 2. Build Portable Output

```powershell
.\build-portable.ps1
```

Expected output:

```text
dist\HandController\HandController.exe
```

The build script copies:

```text
tuning.testing.json -> dist\HandController\tuning.local.json
```

This `tuning.local.json` is the default tuning that packaged users receive.

## 3. Smoke Test The Portable App

Run:

```powershell
.\dist\HandController\HandController.exe
```

Check the important user-facing flows:
- app opens without a terminal
- camera opens
- first hand can lock
- trusted hand moves the cursor
- left click, double click, right click, and drag work
- closed-fist reposition works
- thumb-pinky reset works
- keyboard overlay can open and still allows mouse movement
- second trusted hand can be added only while keyboard is visible
- user manual opens if the release includes it

## 4. Build Installer

Installer builds require Inno Setup 6.

If `ISCC.exe` is missing, install it first:

```powershell
winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
```

Then build with an explicit version:

```powershell
.\build-installer.ps1 -Version "0.2.0-preview"
```

Expected output:

```text
release\installer\HandController-Setup.exe
```

## 5. Smoke Test The Installed App

Install the generated setup file, then launch from the Start Menu.

Check:
- app launches from the installed location
- camera and hand lock still work
- tuning changes can be saved normally
- uninstall entry exists in Windows Apps/Programs

## 6. Distribution Notes

Do not commit generated installer `.exe` files to git.

For now, share either:
- the zipped `dist\HandController` folder for portable testing
- `release\installer\HandController-Setup.exe` for installer testing

Until code signing is added, expect Windows unknown-publisher warnings on some machines.
