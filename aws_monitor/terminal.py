"""Embedded AWS CLI terminal (Tkinter).

Only `aws ...` commands run here, using the app's saved keys
(passed via environment variables, never shown on screen).
Requires the AWS CLI (`aws`) on PATH — otherwise a hint is shown.
"""
import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

HELP_TEXT = (
    "AWS CLI terminal — type any `aws` command, e.g.\n"
    "  aws sts get-caller-identity\n"
    "  aws ec2 describe-instances --region us-east-1 --query Reservations[].Instances[].InstanceId\n"
    "  aws s3 ls\n"
    "Built-ins:  help | clear | aws install  (downloads + installs AWS CLI v2)\n"
    "Keys are injected from your saved (locked) credentials for each command.\n"
)

AWSCLI_URL = "https://awscli.amazonaws.com/AWSCLIV2.msi"
AWSCLI_DIR = r"C:\Program Files\Amazon\AWSCLIV2"


class AWSTerminal(ttk.Frame):
    def __init__(self, parent, creds_provider):
        super().__init__(parent, padding=6)
        self.creds_provider = creds_provider  # () -> (access, secret) | None
        self.history: list[str] = []
        self.hist_idx = 0
        self._q: queue.Queue = queue.Queue()
        self._busy = False

        self.output = tk.Text(self, height=20, state="disabled",
                              bg="#101418", fg="#d7e3d7",
                              insertbackground="white",
                              font=("Consolas", 10))
        scr = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.output.yview)
        self.output.configure(yscrollcommand=scr.set)
        self.output.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scr.pack(side=tk.RIGHT, fill=tk.Y)

        row = ttk.Frame(self)
        row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(row, text="aws>", foreground="#2e7d32",
                  font=("Consolas", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.entry = ttk.Entry(row, font=("Consolas", 10))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", self._on_hist_up)
        self.entry.bind("<Down>", self._on_hist_down)
        ttk.Button(row, text="Run", command=self._on_enter).pack(side=tk.LEFT, padx=6)

        self._print(HELP_TEXT)
        if not shutil.which("aws"):
            self._print("WARNING: `aws` CLI not found on PATH.\n"
                        "Re-run the latest AWS Monitor Setup installer (it installs\n"
                        "AWS CLI v2 automatically), or get it from\n"
                        "https://aws.amazon.com/cli/ (Windows MSI),\n"
                        "then restart this app. Commands will fail until then.\n")
        self.after(120, self._poll)

    # ---------- ui helpers ----------
    def _print(self, text):
        self.output.config(state="normal")
        self.output.insert(tk.END, text if text.endswith("\n") else text + "\n")
        self.output.see(tk.END)
        self.output.config(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "line":
                    self._print(payload)
                elif kind == "done":
                    self._busy = False
                    self._print(payload)
        except queue.Empty:
            pass
        self.after(120, self._poll)

    # ---------- input ----------
    def _on_enter(self, _event=None):
        if self._busy:
            self._print("(still running — wait for the $ prompt)")
            return
        cmd = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if not cmd:
            return
        self.history.append(cmd)
        self.hist_idx = len(self.history)
        self._print(f"$ {cmd}")
        low = cmd.lower()
        if low == "clear":
            self.output.config(state="normal")
            self.output.delete(1.0, tk.END)
            self.output.config(state="disabled")
            return
        if low == "help":
            self._print(HELP_TEXT)
            return
        if low == "aws install":
            threading.Thread(target=self._install_awscli, daemon=True).start()
            return
        if low != "aws" and not low.startswith("aws "):
            self._print("Only `aws ...` commands are allowed here (plus help/clear).")
            return
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _on_hist_up(self, _event=None):
        if self.history and self.hist_idx > 0:
            self.hist_idx -= 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.history[self.hist_idx])

    def _on_hist_down(self, _event=None):
        if self.history and self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.history[self.hist_idx])

    # ---------- AWS CLI self-install ----------
    def _install_awscli(self):
        import tempfile
        import urllib.request

        self._busy = True
        try:
            if os.name != "nt":
                self._q.put(("done", "$ (auto-install supports Windows only — "
                                     "see https://aws.amazon.com/cli/)"))
                return
            existing = os.path.join(AWSCLI_DIR, "aws.exe")
            if os.path.exists(existing) and not shutil.which("aws"):
                # installed but PATH is stale in this process — just refresh it
                os.environ["PATH"] += os.pathsep + AWSCLI_DIR
                self._q.put(("line", "Found existing AWS CLI, refreshed PATH."))
            elif shutil.which("aws"):
                self._q.put(("done", "$ (AWS CLI is already installed)"))
                return
            else:
                dest = os.path.join(tempfile.gettempdir(), "AWSCLIV2.msi")
                self._q.put(("line", "Downloading AWS CLI v2 (official AWS build)…"))
                req = urllib.request.Request(AWSCLI_URL,
                                             headers={"User-Agent": "AWSMonitor"})
                with urllib.request.urlopen(req, timeout=60) as r, \
                        open(dest, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    done = 0
                    while True:
                        chunk = r.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total and done % (4 * 1024 * 1024) < 256 * 1024:
                            self._q.put(("line",
                                         f"  … {done // 1024 // 1024} / "
                                         f"{total // 1024 // 1024} MB"))
                self._q.put(("line", "Downloaded."))
                self._q.put(("line", ">>> Windows will now ask for administrator "
                                     "permission — click YES."))
                self._q.put(("line", ">>> An AWS CLI progress window will then appear."))
                import ctypes
                import time

                rc = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", "msiexec",
                    f'/i "{dest}" /qb /norestart', None, 1)
                if rc <= 32:
                    if rc == 1223:
                        self._q.put(("done", "$ (cancelled — run `aws install` "
                                            "again and click YES)"))
                    else:
                        self._q.put(("done", f"$ (could not start installer "
                                            f"(code {rc}) — right-click this app "
                                            "and 'Run as administrator', then retry)"))
                    return
                # runas returns immediately — wait until aws.exe shows up
                self._q.put(("line", "Installing… (progress window is showing)"))
                deadline = time.time() + 600
                while time.time() < deadline:
                    if os.path.exists(existing):
                        break
                    time.sleep(2)
                if not os.path.exists(existing):
                    self._q.put(("done", "$ (timed out waiting for the install — "
                                        "run `aws install` again)"))
                    return
                if AWSCLI_DIR not in os.environ["PATH"]:
                    os.environ["PATH"] += os.pathsep + AWSCLI_DIR
            # verify
            check = subprocess.run(["aws", "--version"], capture_output=True,
                                   text=True, timeout=60)
            out = (check.stdout or check.stderr or "").strip()
            self._q.put(("done", f"$ AWS CLI ready: {out}\n"
                                 "$ (restart the app if new shells still miss it)"))
        except Exception as e:
            self._q.put(("done", f"$ (install failed: {e})"))
        finally:
            self._busy = False

    # ---------- execution ----------
    def _run(self, cmd):
        self._busy = True
        if not shutil.which("aws"):
            self._q.put(("done", "$ (install the AWS CLI first — see warning above)"))
            return
        creds = self.creds_provider()
        if not creds:
            self._q.put(("done", "$ (cancelled — no credentials unlocked)"))
            return
        access, secret = creds
        env = dict(os.environ)
        env["AWS_ACCESS_KEY_ID"] = access
        env["AWS_SECRET_ACCESS_KEY"] = secret
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, env=env,
                text=True, errors="replace",
            )
        except Exception as e:
            self._q.put(("done", f"$ (failed to start: {e})"))
            return
        try:
            for line in proc.stdout:
                self._q.put(("line", line.rstrip("\n")))
            proc.wait()
            self._q.put(("done", f"$ (exit {proc.returncode})"))
        except Exception as e:
            self._q.put(("done", f"$ (error: {e})"))
