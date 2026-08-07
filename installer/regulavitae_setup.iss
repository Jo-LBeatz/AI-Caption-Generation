; regulavitae_setup.iss — Inno Setup script for Captions by RegulaVitae
;
; Prerequisites:
;   1. Inno Setup installed: https://jrsoftware.org/isinfo.php
;   2. PyInstaller output exists at: ..\dist\RegulaVitae_Captions\
;
; To compile this script:
;   - Open Inno Setup Compiler
;   - File → Open → select this file
;   - Build → Compile
;   OR run from command line:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" regulavitae_setup.iss

#define AppName      "Captions by RegulaVitae"
#define AppVersion   "1.0.0"
#define AppPublisher "RegulaVitae"
#define AppExeName   "RegulaVitae_Captions.exe"
#define AppURL       ""

[Setup]
AppId={{F4A2B3C1-7D8E-4F9A-B0C2-D3E4F5A6B7C8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\RegulaVitae Captions
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Require admin rights so the app installs to Program Files
PrivilegesRequired=admin
OutputDir=..\installer_output
OutputBaseFilename=RegulaVitae_Captions_Setup_v{#AppVersion}
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
; Windows 10 or later required
MinVersion=10.0
WizardStyle=modern
; Uninstall settings
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunch"; Description: "Pin to taskbar"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Copy the entire PyInstaller output folder
Source: "..\dist\RegulaVitae_Captions\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start menu shortcut
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Optional desktop shortcut (only if user selected the task above)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch immediately after install
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the SQLite database and uploads folder created at runtime
Type: filesandordirs; Name: "{app}\regulavitae.db"
Type: filesandordirs; Name: "{app}\uploads"
