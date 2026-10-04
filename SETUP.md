# Setting Up AWS Monitor (Step-by-Step Guide)

This guide is for **normal users** — no technical knowledge needed.
Just follow the steps in order.

## Step 1: Install the app

1. Open this page in your browser:
   **https://github.com/opermancode/awsmonitor/releases**
2. Click the newest version number at the top.
3. Download the file that looks like this:
   **Setup-AWSMonitor-v1.9.exe** (the version number will be different).
   Do NOT download the file named only `AWSMonitor.exe`.
4. Double-click the downloaded file and click **Next** until it finishes.
5. If Windows shows a blue warning (*"Windows protected your PC"*),
   don't worry — click **More info**, then click **Run anyway**.
   (This appears because the app is new and not yet registered with Microsoft.)

## Step 2: Let it install its helper tool (automatic)

The app needs a small free helper tool from Amazon called **AWS CLI**
to run commands. You don't have to do anything:

- During installation, the app checks if you already have it.
- If not, it downloads and installs it by itself.
- Windows will ask **"Do you want to allow this app to make changes?"** —
  click **YES**. That's the helper tool installing.

If something went wrong and the helper tool is missing, open the app,
go to the **AWS CLI** tab, type the following and press Enter:

```
aws install
```

Click **YES** when Windows asks permission, wait for it to finish,
and you're done.

## Step 3: Create your app password (one time)

1. Open the app.
2. At the top, click **Settings → Set / change app password**.
3. Type a password you will remember (minimum 4 letters/numbers) and confirm it.

This password protects your Amazon keys. You will type it again
whenever you want to see or change those keys. Nothing else in the
app is locked — only the keys.

## Step 4: Add your Amazon keys (one time)

You need two secret codes from your Amazon (AWS) account.
If you don't have them yet, ask the person who manages your AWS account
for an **Access Key ID** and a **Secret Access Key**
(read-only permission is enough — the app never changes anything by itself).

1. In the app, click **Settings → View / update AWS keys**.
2. Type your app password (from Step 3).
3. Paste the two Amazon codes and click **Save**.

Your codes are stored scrambled (encrypted) on your own computer.
The app never shows them to anyone.

When done, the top of the app shows:
**AWS keys: ✅ saved (locked)** — that means you're ready.

## Step 5: Run your first scan

1. Leave the dropdown on **ALL regions**.
2. Click the green **▶ Scan now** button.
3. Wait while it checks everything. You can watch the progress bar.
   You can press **Stop** anytime — the app won't freeze.
4. When finished, you'll see a table of everything still running
   in your Amazon account (servers, databases, storage, etc.),
   plus a summary line like: `EC2: 3 • S3: 5 • Total: 8`.
5. Use the **Search** box to find things quickly.

**Anything shown as running/active/available may be costing you money.**
If you don't need it anymore, delete it in your AWS account
to stop the charges. That's the whole point of this app. 🙂

## Step 6: Keep the app updated

- When a new version comes out, a green button appears at the top right:
  **⬆ Update to vX.Y**. Click it, then click **Download & Install**.
- The installer updates your app. When it's done, the green button
  goes away — that means you're on the latest version.
- No green button = nothing to do, you're already latest.

## If something goes wrong

**"Windows protected your PC" during install**
→ Click *More info → Run anyway* (see Step 1).

**App says AWS CLI is missing**
→ In the **AWS CLI** tab, type `aws install` and press Enter (see Step 2).

**App says keys are wrong / scan shows an error**
→ Your Amazon codes may be mistyped or expired.
Go to **Settings → View / update AWS keys** and save them again.

**App won't start and mentions `python312.dll`**
→ Your antivirus probably deleted a file while installing.
Open *Windows Security → Protection history*, restore the file,
and re-install. If that doesn't help, install
*Microsoft Visual C++ Redistributable 2015–2022 (64-bit)* from
Microsoft's website and restart your computer.

**Update button never appears / says you're latest**
→ You're already on the newest version. Nothing to do.

## Removing the app

Go to Windows **Settings → Apps → AWS Monitor → Uninstall**.
Your saved (scrambled) keys stay in a folder called `AWSMonitor`
inside your computer's AppData — delete that folder too
if you want everything gone.
