#define AppName "影速视频下载器"
#define AppVersion "1.1.0"
#define AppExe "YingSuVideo.exe"

[Setup]
AppId={{AEAB6539-6F94-4A3C-9BB7-31483B89EE12}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\YingSuVideo
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=YingSuVideo-Setup-v1.1
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExe}

[Files]
Source: "..\dist\YingSuVideo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动影速视频下载器"; Flags: nowait postinstall skipifsilent
