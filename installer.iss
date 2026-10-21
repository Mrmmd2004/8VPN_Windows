; Inno Setup script - built by the GitHub workflow
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8F1B6C2E-5A47-4D0B-9E31-0A8B0C0D0E01}
AppName=8 VPN
AppVersion={#AppVersion}
AppPublisher=Clubapp8
DefaultDirName={autopf}\8VPN
DefaultGroupName=8 VPN
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=8VPN-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\8VPN.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\8VPN\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\8 VPN"; Filename: "{app}\8VPN.exe"
Name: "{autodesktop}\8 VPN"; Filename: "{app}\8VPN.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\8VPN.exe"; Description: "Launch 8 VPN"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "schtasks"; Parameters: "/Delete /TN 8VPN /F"; Flags: runhidden; RunOnceId: "DelTask"
Filename: "taskkill"; Parameters: "/F /IM aether.exe"; Flags: runhidden; RunOnceId: "KillAether"
Filename: "taskkill"; Parameters: "/F /IM sing-box.exe"; Flags: runhidden; RunOnceId: "KillSingbox"
Filename: "taskkill"; Parameters: "/F /IM 8VPN.exe"; Flags: runhidden; RunOnceId: "KillApp"
