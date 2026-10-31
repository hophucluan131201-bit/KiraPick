; Inno Setup 6 script: per-user installer for KiraPick (no administrator rights needed).
;   ISCC.exe /DAppVersion=0.2.0b2 packaging\installer.iss
; Input : dist\KiraPick\ (PyInstaller folder + verified models\)
; Output: dist\installer\KiraPick-Setup-<version>.exe (a few MB) + KiraPick-Setup-<version>-1.bin (the data).
;   Split on purpose: Windows Defender / SmartScreen read the whole .exe before starting it, so a
;   400 MB setup.exe took a long time to open after a double-click. Keep both files in one folder.
; The uninstaller removes the program only. Photos are never touched; the user's
; sessions and learning data (%LOCALAPPDATA%\KiraPick) are kept.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef NumericVersion
  #define NumericVersion "0.0.0.0"
#endif
#ifndef SliceSize
  #define SliceSize "max"
#endif
#define SourceDir "..\dist\KiraPick"
; A development version (".dev", e.g. 3.0.0b1.dev1) is an INTERNAL TEST build: its own AppId, name, folder, shortcuts
; and uninstall entry, so it installs beside the official KiraPick and never replaces it; it does not start the app
; after installing (no session is opened, nothing is migrated by the installer).
#define InternalTest Pos(".dev", AppVersion) > 0
#if InternalTest
  #define AppName "KiraPick Internal Test"
  #define AppIdValue "{{3B7D2E91-6A4C-4F18-9E25-C81A0D6F4B72}"
  #define InstallDirName "KiraPick-InternalTest"
  #define OutputName "KiraPick-InternalTest-" + AppVersion + "-Setup"
#else
  #define AppName "KiraPick"
  #define AppIdValue "{{6F2C9B1E-4E57-4C3A-9D2B-5A8C1E7F3B10}"
  #define InstallDirName "KiraPick"
  #define OutputName "KiraPick-Setup-" + AppVersion
#endif

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=KiraPick
DefaultDirName={localappdata}\Programs\{#InstallDirName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename={#OutputName}
SetupIconFile=kirapick.ico
UninstallDisplayIcon={app}\KiraPick.exe
#if InternalTest
UninstallDisplayName={#AppName} {#AppVersion}
VersionInfoVersion={#NumericVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
#else
UninstallDisplayName={#AppName}
#endif
Compression=lzma2/max
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize={#SliceSize}
SlicesPerDisk=1
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

#if !InternalTest
[Run]
Filename: "{app}\KiraPick.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
#endif

#if InternalTest
; The script as compiled, kept beside the installer as evidence of the identity used (internal builds only).
#expr SaveToFile(AddBackslash(SourcePath) + "..\dist\installer\installer-identity.iss")
#endif
