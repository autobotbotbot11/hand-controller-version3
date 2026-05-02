#define RepoRoot SourcePath
#define MyAppName "Hand Controller"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0-preview"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "Hand Controller Project"
#endif
#define MyAppExeName "HandController.exe"
#define MyAppDistDir AddBackslash(RepoRoot) + "dist\\HandController"
#define MyAppIcon AddBackslash(RepoRoot) + "assets\\logo.ico"

[Setup]
AppId={{D2F2C92A-1B1A-4F64-A5D9-3D6A6F4A1A73}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir={#RepoRoot}\release\installer
OutputBaseFilename=HandController-Setup
ChangesAssociations=no
CloseApplications=no
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#MyAppDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
