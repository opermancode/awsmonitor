<div align="center">
  <img src="assets/leaf.png" width="128" alt="AWS Monitor logo">
  <h1>AWS Monitor — Bill Saver</h1>
  <p>A Windows desktop app that scans your AWS account for forgotten, still-billable resources — so surprise bills stop happening.</p>
  <p>
    <a href="https://github.com/opermancode/awsmonitor/releases">Download installer</a>
    •
    <a href="#usage">Usage</a>
    •
    <a href="#contributing">Contributing</a>
  </p>
</div>

## Why this exists

It's easy to spin up an EC2 instance, RDS database, NAT gateway or load balancer for a quick test — and forget to delete it. AWS keeps billing you. AWS Monitor scans **all regions and all the small services** in one click and shows exactly what is still running.

## Features

- 🔍 **Full-account scan** — EC2, EBS, Elastic IPs, NAT gateways, ELB/ELBv2, Auto Scaling, RDS (+clusters), ElastiCache, Lambda, ECS, DynamoDB, SNS, SQS, CloudFormation, CloudWatch alarms, EFS, S3, IAM, Route 53
- 🌍 **All regions** (or pick one) with live progress, log and Stop button — the UI never freezes
- 🔒 **Locked credentials** — AWS keys are stored encrypted (`%APPDATA%\AWSMonitor`). Viewing or changing them always requires re-entering your app password. No screen lock, no plaintext.
- 🔎 **Search, service filter and per-service summary** of everything found
- 💻 **Built-in AWS CLI terminal** — run any `aws ...` command with your saved keys (requires [AWS CLI](https://aws.amazon.com/cli/) installed)
- ⬆️ **In-app updates** — an Update button appears only when a newer release exists; one click downloads and installs it

> 🧭 **New here?** Follow the plain-language **[Setup Guide](SETUP.md)** —
> install → helper tool → password → keys → first scan.

## Install

**Recommended:** download `Setup-AWSMonitor-vX.Y.exe` from the
[Releases page](https://github.com/opermancode/awsmonitor/releases) and run it.
The installer automatically downloads and installs **AWS CLI v2** too
(if missing), since the built-in terminal needs it.
(Windows will show one UAC prompt for the AWS CLI part.)

Or use the portable `AWSMonitor.exe` (no install needed) — but then install
[AWS CLI](https://aws.amazon.com/cli/) yourself for the terminal tab.

> Windows SmartScreen may warn about the download since the app isn't code-signed yet — click *More info → Run anyway*.

## Usage

1. Open **Settings → Set / change app password** and create an app password.
2. Open **Settings → View / update AWS keys** (enter the app password) and save your AWS Access Key ID + Secret Access Key.
   Keys need read-only permissions (`ReadOnlyAccess` managed policy is enough).
3. Click **▶ Scan now** (pick ALL regions or one region).
4. Review the results — anything `running` / `active` / `available` can cost money. Stop or delete what you don't need.
5. Use the **AWS CLI** tab for follow-up commands, e.g. `aws ec2 stop-instances --instance-ids i-123...`.

## Run from source

Requires Python 3.10+.

```powershell
pip install -r requirements.txt
python -m aws_monitor        # or: python run.py
```

## How releases work (maintainers)

1. Bump `__version__` in `aws_monitor/__init__.py` (and `MyAppVersion` in `installer.iss` for local builds).
2. Commit and push to `main`.
3. Tag and push the tag: `git tag vX.Y.Z; git push origin vX.Y.Z`
4. GitHub Actions builds `AWSMonitor.exe` + `Setup-AWSMonitor-vX.Y.exe` and attaches both to the release.
5. Installed apps detect the new release and show the ⬆ Update button.

## Project layout

```
run.py                # exe entry point
aws_monitor/
  main.py             # Tkinter desktop app
  scanner.py          # multi-region, multi-service AWS scanner (boto3)
  terminal.py         # embedded AWS CLI terminal
  updater.py          # self-update via GitHub Releases
  auth.py             # app-password hashing (PBKDF2)
  secure_store.py     # encrypted credential storage (Fernet)
  config.py           # %APPDATA% paths
assets/               # leaf logo (png/ico) + installer wizard images
AWSMonitor.spec       # PyInstaller build
installer.iss         # Inno Setup installer script
build.bat             # local exe build
```

## Contributing

Pull requests are welcome! For big changes, please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-idea`)
3. Commit, push, open a PR against `main`

## Security

AWS keys are encrypted at rest with a key derived from your app password (PBKDF2 + Fernet) and only ever decrypted in memory. If you find a security issue, please open a GitHub issue (do not post real credentials anywhere).

## License

[MIT](LICENSE) © opermancode
