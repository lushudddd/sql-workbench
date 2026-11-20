[Setup]
AppId=SQLWorkbench.Desktop
AppName=SQL 工作台
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\SQLWorkbench
DefaultGroupName=SQL 工作台
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=SQLWorkbench-Setup-x64
UninstallDisplayIcon={app}\SQLWorkbench.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "dist\SQLWorkbench\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\SQL 工作台"; Filename: "{app}\SQLWorkbench.exe"; WorkingDir: "{app}"
Name: "{group}\SQL 工作台"; Filename: "{app}\SQLWorkbench.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\SQLWorkbench.exe"; Description: "打开 SQL 工作台"; Flags: nowait postinstall skipifsilent
