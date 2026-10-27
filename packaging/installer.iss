; Inno Setup 6 script: per-user installer for KiraPick (no administrator rights needed).
;   ISCC.exe /DAppVersion=0.2.0b2 packaging\installer.iss
; Input : dist\KiraPick\ (PyInstaller folder + verified models\)
; Output: dist\installer\KiraPick-Setup-<version>.exe
; The uninstaller removes the program only. Photos are never touched; the user's
; sessions and learning data (%LOCALAPPDATA%\KiraPick) are kept.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "KiraPick"
#define SourceDir "..\dist\KiraPick"

[Setup]
AppId={{6F2C9B1E-4E57-4C3A-9D2B-5A8C1E7F3B10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=KiraPick
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=KiraPick-Setup-{#AppVersion}
SetupIconFile=kirapick.ico
UninstallDisplayIcon={app}\KiraPick.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
LicenseFile=..\dist\installer-notes\LICENSES.txt
InfoBeforeFile=..\dist\installer-notes\HUONG_DAN.txt

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#if FileExists(AddBackslash(CompilerPath) + "Languages\Vietnamese.isl")
Name: "vi"; MessagesFile: "compiler:Languages\Vietnamese.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\installer-notes\*"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\KiraPick.exe"
Name: "{autoprograms}\Hướng dẫn {#AppName}"; Filename: "{app}\docs\HUONG_DAN.txt"
Name: "{autoprograms}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\KiraPick.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KiraPick.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
