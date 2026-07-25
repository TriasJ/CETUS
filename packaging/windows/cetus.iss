; Inno Setup script for CETUS (Windows installer).
; Build the one-file exe first (pyinstaller cravingcrave.spec -> dist\CETUS.exe),
; then compile this:  iscc /DAppVersion=0.4.0 packaging\windows\cetus.iss
; Produces:  packaging\windows\Output\CETUS-Setup-<version>.exe
;
; Data note: the installed app writes patient data/media to %APPDATA%\CETUS
; (see cravingcrave/paths.py), NOT under Program Files, so a standard user can run it.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C0E2C7E-CE7A-4C6B-9E2E-CE7A5CET0401}
AppName=CETUS
AppVersion={#AppVersion}
AppPublisher=CETUS
DefaultDirName={autopf}\CETUS
DefaultGroupName=CETUS
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\CETUS.exe
OutputBaseFilename=CETUS-Setup-{#AppVersion}
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\..\cravingcrave\resources\icons\cetus.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\CETUS.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CETUS"; Filename: "{app}\CETUS.exe"
Name: "{group}\{cm:UninstallProgram,CETUS}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CETUS"; Filename: "{app}\CETUS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CETUS.exe"; Description: "{cm:LaunchProgram,CETUS}"; Flags: nowait postinstall skipifsilent
