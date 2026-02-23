#ifndef MyAppVersion
#define MyAppVersion "2.3.18"
#endif

[Setup]
AppId={{1E191169-A1B1-4E4F-8AB9-B2D048A76E8C}
AppName=쇼츠스레드메이커
AppVersion={#MyAppVersion}
AppPublisher=와이엠
DefaultDirName={autopf}\CoupangThreadAuto
DefaultGroupName=쇼츠스레드메이커
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=CoupangThreadAutoSetup
SetupIconFile=..\images\app_icon.ico
UninstallDisplayIcon={app}\CoupangThreadAuto.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 아이콘 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "..\dist\CoupangThreadAuto.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\쇼츠스레드메이커"; Filename: "{app}\CoupangThreadAuto.exe"
Name: "{group}\쇼츠스레드메이커 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\쇼츠스레드메이커"; Filename: "{app}\CoupangThreadAuto.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CoupangThreadAuto.exe"; Description: "쇼츠스레드메이커 실행"; Flags: nowait postinstall skipifsilent
