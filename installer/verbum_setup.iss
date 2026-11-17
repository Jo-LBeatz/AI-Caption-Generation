; verbum_setup.iss — Inno Setup script for Verbum — AI Caption Software
;
; Prerequisites:
;   1. Inno Setup installed: https://jrsoftware.org/isinfo.php
;   2. PyInstaller output exists at: ..\dist\Verbum\
;
; To compile this script:
;   - Open Inno Setup Compiler
;   - File -> Open -> select this file
;   - Build -> Compile
;   OR run from command line:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" verbum_setup.iss

#define AppName      "Verbum"
#define AppVersion   "2.0.0"
#define AppPublisher "Verbum Catholic AI"
#define AppExeName   "Verbum.exe"
#define AppURL       ""

[Setup]
AppId={{F4A2B3C1-7D8E-4F9A-B0C2-D3E4F5A6B7C8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\Verbum
DefaultGroupName={#AppName}
AllowNoIcons=yes
PrivilegesRequired=admin
OutputDir=..\installer_output
OutputBaseFilename=Verbum_Setup_v{#AppVersion}
SetupIconFile=..\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
MinVersion=10.0
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunch"; Description: "Pin to taskbar"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Verbum\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                 Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";            Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
