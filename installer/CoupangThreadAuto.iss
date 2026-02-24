#ifndef MyAppVersion
#define MyAppVersion "2.3.21"
#endif

[Setup]
AppId={{1E191169-A1B1-4E4F-8AB9-B2D048A76E8C}
AppName=?쇱툩?ㅻ젅?쒕찓?댁빱
AppVersion={#MyAppVersion}
AppPublisher=??댁뿞
DefaultDirName={autopf}\CoupangThreadAuto
DefaultGroupName=?쇱툩?ㅻ젅?쒕찓?댁빱
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
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
DirExistsWarning=no
CloseApplications=yes
CloseApplicationsFilter=CoupangThreadAuto.exe
RestartApplications=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\CoupangThreadAuto.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\?쇱툩?ㅻ젅?쒕찓?댁빱"; Filename: "{app}\CoupangThreadAuto.exe"
Name: "{group}\?쇱툩?ㅻ젅?쒕찓?댁빱 ?쒓굅"; Filename: "{uninstallexe}"
Name: "{autodesktop}\?쇱툩?ㅻ젅?쒕찓?댁빱"; Filename: "{app}\CoupangThreadAuto.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CoupangThreadAuto.exe"; Description: "?쇱툩?ㅻ젅?쒕찓?댁빱 ?ㅽ뻾"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallRegPath = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{1E191169-A1B1-4E4F-8AB9-B2D048A76E8C}_is1';

function TryGetInstalledVersion(var InstalledVersion: string): Boolean;
begin
  Result := False;
  if IsWin64 then
    Result := RegQueryStringValue(HKLM64, UninstallRegPath, 'DisplayVersion', InstalledVersion);
  if not Result then
    Result := RegQueryStringValue(HKLM, UninstallRegPath, 'DisplayVersion', InstalledVersion);
  if not Result then
    Result := RegQueryStringValue(HKCU, UninstallRegPath, 'DisplayVersion', InstalledVersion);
end;

procedure InitializeWizard();
var
  InstalledVersion: string;
begin
  if TryGetInstalledVersion(InstalledVersion) then
  begin
    Log(Format('Existing installation detected. InstalledVersion=%s, NewVersion=%s', [InstalledVersion, '{#MyAppVersion}']));
    WizardForm.WelcomeLabel2.Caption :=
      'Existing installation detected. Setup will continue in update mode and keep your current settings.';
  end;
end;
