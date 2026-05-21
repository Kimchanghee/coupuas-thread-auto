#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{1E191169-A1B1-4E4F-8AB9-B2D048A76E8C}
AppName=Shorts Thread Maker
AppVersion={#MyAppVersion}
AppVerName=Shorts Thread Maker {#MyAppVersion}
AppPublisher=YM
AppPublisherURL=https://github.com/Kimchanghee/coupuas-thread-auto
AppSupportURL=https://github.com/Kimchanghee/coupuas-thread-auto/issues
AppUpdatesURL=https://github.com/Kimchanghee/coupuas-thread-auto/releases/latest
DefaultDirName={autopf}\CoupangThreadAuto
DefaultGroupName=Shorts Thread Maker
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=CoupangThreadAutoSetup
SetupIconFile=..\images\app_icon.ico
UninstallDisplayIcon={app}\CoupangThreadAuto.exe
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=YM
VersionInfoDescription=Shorts Thread Maker Windows Installer
VersionInfoProductName=Shorts Thread Maker
VersionInfoProductVersion={#MyAppVersion}
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
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\CoupangThreadAuto.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Shorts Thread Maker"; Filename: "{app}\CoupangThreadAuto.exe"
Name: "{group}\Uninstall Shorts Thread Maker"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Shorts Thread Maker"; Filename: "{app}\CoupangThreadAuto.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CoupangThreadAuto.exe"; Description: "Launch Shorts Thread Maker"; Flags: nowait postinstall skipifsilent

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
      'Existing installation detected. Setup will update the app and keep your current settings.';
  end;
end;
