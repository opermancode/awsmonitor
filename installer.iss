; Inno Setup script for AWS Monitor
; Install Inno Setup 6, open this file, press Build -> Compile.
#define MyAppName "AWS Monitor"
#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif
#define MyAppPublisher "AWS Monitor"
#define MyAppExeName "AWSMonitor.exe"

[Setup]
AppId={{3A9B7E1A-4C2F-4D8B-9F10-AWSMONITOR10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\AWSMonitor
DefaultGroupName=AWS Monitor
OutputBaseFilename=Setup-AWSMonitor-{#MyAppVersion}
OutputDir=.
SetupIconFile=assets\leaf.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\wizard_small.bmp
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\\AWSMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion
; If you build one-folder mode, use this instead:
; Source: "dist\\AWSMonitor\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\AWS Monitor"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\AWS Monitor"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\AWSCLIV2.msi"" /qn /norestart"; StatusMsg: "Installing AWS CLI v2 (needed for the built-in terminal)..."; Flags: waituntilterminated; Check: AWSCLINeeded
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,AWS Monitor}"; Flags: nowait postinstall skipifsilent

[Code]
var
  AWSCLIDownloadPage: TDownloadWizardPage;

function AWSCLIInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{pf}\Amazon\AWSCLIV2\aws.exe'));
end;

function AWSCLINeeded: Boolean;
begin
  Result := (not AWSCLIInstalled) and FileExists(ExpandConstant('{tmp}\AWSCLIV2.msi'));
end;

procedure InitializeWizard;
begin
  AWSCLIDownloadPage := CreateDownloadPage(
    SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and (not AWSCLIInstalled) then
  begin
    AWSCLIDownloadPage.Clear;
    AWSCLIDownloadPage.Add('https://awscli.amazonaws.com/AWSCLIV2.msi',
      'AWSCLIV2.msi', '');
    AWSCLIDownloadPage.Show;
    try
      try
        AWSCLIDownloadPage.Download;
      except
        if MsgBox('AWS CLI v2 could not be downloaded.' + #13#10 +
          'The built-in AWS CLI terminal needs it to run commands.' + #13#10 +
          'Continue installing AWS Monitor without AWS CLI?',
          mbConfirmation, MB_YESNO) = IDNO then
          Result := False;
      end;
    finally
      AWSCLIDownloadPage.Hide;
    end;
  end;
end;
