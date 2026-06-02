; =====================================================
; GET CLUB - Inno Setup Script
; Para compilar: abrir com Inno Setup Compiler e clicar Build
; =====================================================
#define MyAppName "GET CLUB"
#define MyAppVersion "1.0"
#define MyAppPublisher "GET CLUB"
#define MyAppURL "https://getclub.pt"
#define MyAppExeName "GETCLUB.exe"

[Setup]
AppId={{8F3A1B2C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\GETCLUB
DefaultGroupName={#MyAppName}
AllowNoIcons=no
OutputDir=.\installer_output
OutputBaseFilename=GETCLUB_Setup_v1.0
SetupIconFile=static\img\getclub-logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
WizardSmallImageFile=static\img\getclub-wizard-small.bmp
WizardImageFile=static\img\getclub-wizard-large.bmp
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho no Ambiente de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; Todos os ficheiros do executável compilado pelo PyInstaller
Source: "dist\GETCLUB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Recursos estáticos
Source: "templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lançar GET CLUB agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"