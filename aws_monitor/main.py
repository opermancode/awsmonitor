"""AWS Monitor desktop app — creds locked behind app password, no screen lock."""
import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, simpledialog, ttk

from . import auth, scanner, secure_store, updater
from .terminal import AWSTerminal


class PasswordDialog(simpledialog.Dialog):
    def __init__(self, parent, title="App password", prompt="Enter app password:"):
        self.prompt = prompt
        self.value = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text=self.prompt).pack(padx=10, pady=5)
        self.entry = tk.Entry(master, show="*", width=30)
        self.entry.pack(padx=10, pady=5)
        return self.entry

    def apply(self):
        self.value = self.entry.get()


def ask_password(parent, prompt="Enter app password:"):
    d = PasswordDialog(parent, prompt=prompt)
    return d.value


def asset_path(name: str) -> str:
    """Locate a bundled asset (works from source and from the PyInstaller exe)."""
    import os
    import sys
    from pathlib import Path

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, "assets", name)
    return str(Path(__file__).resolve().parent.parent / "assets" / name)


class AWMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"AWS Monitor — Bill Saver v{updater.get_current_version()}")
        self.root.geometry("1060x760")
        try:
            self.root.iconbitmap(default=asset_path("leaf.ico"))
        except Exception:
            pass

        self.q: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.scanning = False
        self.total_tasks = 1
        self.done_tasks = 0
        self._pending_update = None
        self._all_rows: list = []
        self._services: set = set()

        try:
            style = ttk.Style()
            if "clam" in style.theme_names():
                style.theme_use("clam")
            style.configure("Accent.TButton", background="#2e7d32", foreground="white",
                            font=("Segoe UI", 9, "bold"))
            style.map("Accent.TButton",
                      background=[("active", "#43a047"), ("disabled", "#9e9e9e")])
        except Exception:
            pass

        self._build_menu()
        self._build_layout()
        self._refresh_cred_status()
        self.root.after(120, self._poll_queue)
        threading.Thread(target=self._startup_update_check, daemon=True).start()

    # ---------- layout ----------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        settings = tk.Menu(menubar, tearoff=0)
        settings.add_command(label="Set / change app password…", command=self.on_set_password)
        settings.add_command(label="View / update AWS keys… (needs password)", command=self.on_edit_creds)
        settings.add_command(label="Clear saved AWS keys…", command=self.on_clear_creds)
        settings.add_separator()
        settings.add_command(label="Check for updates…", command=self.on_check_updates)
        settings.add_separator()
        settings.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="Settings", menu=settings)
        self.root.config(menu=menubar)

    def _build_layout(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        try:
            self.logo_img = tk.PhotoImage(file=asset_path("leaf.png")).subsample(8, 8)
            ttk.Label(top, image=self.logo_img).pack(side=tk.LEFT, padx=(0, 6))
        except Exception:
            pass
        ttk.Label(top, text="AWS Monitor", font=("Segoe UI", 13, "bold")).pack(
            side=tk.LEFT, padx=(0, 10))

        self.cred_status = ttk.Label(top, text="AWS keys: …")
        self.cred_status.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(top, text="Unlock / Edit keys", command=self.on_edit_creds).pack(side=tk.LEFT)
        ttk.Button(top, text="Settings: app password", command=self.on_set_password).pack(side=tk.LEFT, padx=6)

        # visible ONLY when a newer release exists (hidden otherwise)
        self.update_btn = ttk.Button(top, text="Update", command=self.on_update_button,
                                     style="Accent.TButton")

        ctrl = ttk.LabelFrame(self.root, text="Scan", padding=8)
        ctrl.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(ctrl, text="Region:").grid(row=0, column=0, sticky=tk.W)
        self.region_var = tk.StringVar(value="ALL regions")
        regions = ["ALL regions"] + scanner.REGIONS
        self.region_box = ttk.Combobox(ctrl, textvariable=self.region_var, values=regions,
                                       width=22, state="readonly")
        self.region_box.grid(row=0, column=1, padx=6)

        self.scan_btn = ttk.Button(ctrl, text="▶ Scan now", command=self.start_scan,
                                   style="Accent.TButton")
        self.scan_btn.grid(row=0, column=2, padx=6)
        self.stop_btn = ttk.Button(ctrl, text="Stop", command=self.stop_scan, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=3, padx=6)

        self.progress = ttk.Progressbar(ctrl, mode="determinate", length=400)
        self.progress.grid(row=0, column=4, padx=10, sticky=tk.EW)
        ctrl.columnconfigure(4, weight=1)

        self.status = ttk.Label(ctrl, text="Ready. Keys stay saved & locked behind your app password.")
        self.status.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=8)
        res_tab = ttk.Frame(self.tabs, padding=4)
        self.tabs.add(res_tab, text="📦 Resources")
        cli_tab = ttk.Frame(self.tabs, padding=4)
        self.tabs.add(cli_tab, text="💻 AWS CLI")

        filt = ttk.Frame(res_tab)
        filt.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(filt, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        s_entry = ttk.Entry(filt, textvariable=self.search_var, width=28)
        s_entry.pack(side=tk.LEFT, padx=6)
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Label(filt, text="Service:").pack(side=tk.LEFT)
        self.svc_var = tk.StringVar(value="All services")
        self.svc_box = ttk.Combobox(filt, textvariable=self.svc_var, width=18,
                                    state="readonly", values=["All services"])
        self.svc_box.pack(side=tk.LEFT, padx=6)
        self.svc_box.bind("<<ComboboxSelected>>", lambda _e: self._apply_filter())
        self.count_label = ttk.Label(filt, text="0/0 shown")
        self.count_label.pack(side=tk.RIGHT)

        mid = ttk.Frame(res_tab)
        mid.pack(fill=tk.BOTH, expand=True)
        cols = ("service", "resource", "detail", "state", "region")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        for c, h, w in [("service", "Service", 110), ("resource", "Resource", 260),
                        ("detail", "Detail", 200), ("state", "State", 110),
                        ("region", "Region", 110)]:
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w)
        sb = ttk.Scrollbar(mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary = ttk.Label(res_tab, text="Run a scan to list billable resources.",
                                 anchor=tk.W)
        self.summary.pack(fill=tk.X, pady=(4, 0))

        self.terminal = AWSTerminal(cli_tab, creds_provider=self._get_scan_creds)
        self.terminal.pack(fill=tk.BOTH, expand=True)

        logf = ttk.LabelFrame(self.root, text="Log", padding=4)
        logf.pack(fill=tk.X, padx=8, pady=6)
        self.log_text = tk.Text(logf, height=5, state="disabled")
        self.log_text.pack(fill=tk.X)

    # ---------- cred lock ----------
    def _refresh_cred_status(self):
        if secure_store.has_saved_creds():
            self.cred_status.config(text="AWS keys: ✅ saved (locked)")
        else:
            self.cred_status.config(text="AWS keys: ❌ not saved — use Settings to add")

    def _require_password(self):
        """Every view/change of creds must re-enter the app password."""
        if not auth.has_password():
            messagebox.showinfo("No app password yet",
                                "Set an app password first (Settings → Set / change app password).")
            return None
        pw = ask_password(self.root, "Re-enter app password to view / change AWS keys:")
        if not pw:
            return None
        if not auth.verify_password(pw):
            messagebox.showerror("Denied", "Incorrect app password.")
            return None
        return pw

    def on_set_password(self):
        if auth.has_password():
            cur = ask_password(self.root, "Enter current app password:")
            if not cur or not auth.verify_password(cur):
                messagebox.showerror("Denied", "Incorrect current password.")
                return
            new1 = ask_password(self.root, "Enter NEW app password (min 4 chars):")
            if not new1:
                return
            new2 = ask_password(self.root, "Confirm NEW app password:")
            if new1 != new2:
                messagebox.showerror("Mismatch", "Passwords do not match.")
                return
            try:
                auth.change_password(cur, new1)
                messagebox.showinfo("Done", "App password changed. Saved keys were re-encrypted.")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
        else:
            p1 = ask_password(self.root, "Create app password (min 4 chars):")
            if not p1:
                return
            p2 = ask_password(self.root, "Confirm app password:")
            if p1 != p2:
                messagebox.showerror("Mismatch", "Passwords do not match.")
                return
            try:
                auth.set_password(p1)
                messagebox.showinfo("Done", "App password set. Now add your AWS keys via Settings.")
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def on_edit_creds(self):
        pw = self._require_password()
        if pw is None:
            return
        # password OK → show current (decrypted only in memory) and allow update
        cur_a, cur_s = "", ""
        if secure_store.has_saved_creds():
            try:
                cur_a, cur_s = secure_store.load_creds(pw)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
        win = tk.Toplevel(self.root)
        win.title("AWS keys (unlocked this window only)")
        win.geometry("480x220")
        tk.Label(win, text="Access Key ID:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        a_entry = tk.Entry(win, width=55)
        a_entry.pack(padx=10)
        a_entry.insert(0, cur_a)
        tk.Label(win, text="Secret Access Key:").pack(anchor=tk.W, padx=10)
        s_entry = tk.Entry(win, width=55, show="*")
        s_entry.pack(padx=10)
        s_entry.insert(0, cur_s)

        def save():
            a, s = a_entry.get().strip(), s_entry.get().strip()
            if not a or not s:
                messagebox.showwarning("Missing", "Both fields are required.")
                return
            secure_store.save_creds(pw, a, s)
            self._refresh_cred_status()
            self.log(f"AWS keys saved (encrypted).")
            win.destroy()
            messagebox.showinfo("Saved", "AWS keys saved encrypted. Window closed & locked again.")

        ttk.Button(win, text="Save encrypted", command=save).pack(pady=12)
        win.transient(self.root)
        win.grab_set()

    def on_clear_creds(self):
        pw = self._require_password()
        if pw is None:
            return
        if messagebox.askyesno("Confirm", "Delete saved AWS keys from this PC?"):
            secure_store.clear_creds()
            self._refresh_cred_status()
            self.log("Saved AWS keys cleared.")

    def _get_scan_creds(self):
        """Scanning uses saved creds WITHOUT showing them."""
        if not auth.has_password() or not secure_store.has_saved_creds():
            messagebox.showinfo("Keys needed",
                                "No saved AWS keys. Go to Settings → View / update AWS keys…")
            return None
        # quick unlock: ask password each scan? No — use cached unlock per session?
        # Spec: change/view needs password, scanning should just work.
        # So we try: if a session unlock exists, reuse; else ask once per app run.
        if getattr(self, "_session_pw", None) and auth.verify_password(self._session_pw):
            try:
                return secure_store.load_creds(self._session_pw)
            except ValueError:
                pass
        pw = ask_password(self.root, "Enter app password once to unlock this scan:")
        if not pw or not auth.verify_password(pw):
            if pw:
                messagebox.showerror("Denied", "Incorrect app password.")
            return None
        try:
            creds = secure_store.load_creds(pw)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return None
        self._session_pw = pw  # keep in memory only, never written to disk
        return creds

    # ---------- results filter + summary ----------
    def _row_matches(self, row):
        q = self.search_var.get().lower()
        svc = self.svc_var.get()
        if svc != "All services" and row[0] != svc:
            return False
        return not q or q in " ".join(row).lower()

    def _apply_filter(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in self._all_rows:
            if self._row_matches(row):
                self.tree.insert("", tk.END, values=row)
        self.count_label.config(
            text=f"{len(self.tree.get_children())}/{len(self._all_rows)} shown")

    def _update_summary(self):
        from collections import Counter

        c = Counter(r[0] for r in self._all_rows)
        if not c:
            self.summary.config(text="No billable resources found in scanned scope.")
            return
        self.summary.config(text="  •  ".join(f"{s}: {n}" for s, n in sorted(c.items()))
                            + f"  •  Total: {len(self._all_rows)}")

    # ---------- self-update ----------
    def _offer_update(self, pending):
        """Show the update button (only called when a newer release exists)."""
        self._pending_update = pending
        self.update_btn.config(text=f"\u2b06 Update to {pending['tag']}")
        self.update_btn.pack(side=tk.RIGHT, padx=6)
        self.status.config(text=f"Update available: {pending['tag']} — click the Update button.")

    def _hide_update_button(self):
        """Hide the update button — we are on the latest version."""
        self._pending_update = None
        self.update_btn.pack_forget()

    def on_update_button(self):
        if self._pending_update:
            p = self._pending_update
            self._show_update_dialog(p["tag"], p["notes"], p["asset"])
        else:
            self.on_check_updates()

    def _startup_update_check(self):
        """Quiet check at launch — update button appears only if an update exists."""
        try:
            latest = updater.fetch_latest()
        except Exception:
            return
        tag = latest.get("tag", "")
        asset = updater.pick_installer(latest.get("assets", []))
        if tag and asset and updater.is_newer(updater.get_current_version(), tag):
            pending = {"tag": tag, "notes": latest.get("notes", ""), "asset": asset}
            self.root.after(0, lambda: self._offer_update(pending))
        else:
            self.root.after(0, self._hide_update_button)

    def on_check_updates(self):
        self.status.config(text="Checking for updates…")
        threading.Thread(target=self._check_updates_worker, daemon=True).start()

    def _check_updates_worker(self):
        try:
            latest = updater.fetch_latest()
        except RuntimeError as e:
            self.root.after(0, lambda: messagebox.showerror("Update check", str(e)))
            self.root.after(0, lambda: self.status.config(text="Update check failed."))
            return
        self.root.after(0, lambda: self._handle_latest(latest))

    def _handle_latest(self, latest):
        cur = updater.get_current_version()
        tag = latest.get("tag", "")
        self.status.config(text="Ready.")
        if not tag:
            self._hide_update_button()
            messagebox.showinfo("Updates", "No releases found on GitHub yet.")
            return
        if not updater.is_newer(cur, tag):
            self._hide_update_button()
            messagebox.showinfo("Updates", f"You are on the latest version (v{cur}).")
            return
        asset = updater.pick_installer(latest.get("assets", []))
        if not asset:
            self._hide_update_button()
            messagebox.showwarning(
                "Updates",
                f"Version {tag} is available but has no downloadable installer.\n"
                "Get it from the GitHub Releases page.",
            )
            return
        self._offer_update({"tag": tag, "notes": latest.get("notes", ""), "asset": asset})
        self._show_update_dialog(tag, latest.get("notes", ""), asset)

    def _show_update_dialog(self, tag, notes, asset):
        win = tk.Toplevel(self.root)
        win.title(f"Update available — {tag}")
        win.geometry("520x420")
        tk.Label(win, text=f"A new version is available: {tag}",
                 font=("Segoe UI", 11, "bold")).pack(padx=12, pady=(12, 4))
        tk.Label(win, text=f"File: {asset['name']}\n"
                           "The installer will upgrade your current install.\n"
                           "The app will close when installation starts.").pack(padx=12)
        box = tk.Text(win, height=10, wrap=tk.WORD)
        box.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        box.insert(tk.END, notes or "(no release notes)")
        box.config(state="disabled")

        prog = ttk.Progressbar(win, mode="determinate", length=400)
        prog.pack(padx=12, pady=4, fill=tk.X)
        status = ttk.Label(win, text="")
        status.pack(padx=12)

        btn_row = ttk.Frame(win)
        btn_row.pack(pady=8)

        def set_status(msg):
            status.config(text=msg)

        def do_download():
            import os
            import subprocess
            import tempfile

            for w in btn_row.winfo_children():
                w.config(state=tk.DISABLED)
            set_status("Downloading…")

            dest = os.path.join(tempfile.gettempdir(), asset["name"])

            def on_progress(done, total):
                def tick():
                    if total:
                        prog["maximum"] = total
                        prog["value"] = min(done, total)
                    set_status(f"Downloading… {done // 1024} KB"
                               + (f" / {total // 1024} KB" if total else ""))
                self.root.after(0, tick)

            def worker():
                try:
                    updater.download(asset["url"], dest, progress=on_progress)
                except Exception as e:
                    self.root.after(0, lambda: set_status(f"Download failed: {e}"))
                    self.root.after(0, lambda: messagebox.showerror(
                        "Update", f"Download failed:\n{e}"))
                    self.root.after(0, lambda: [w.config(state=tk.NORMAL)
                                                for w in btn_row.winfo_children()])
                    return

                def launch():
                    is_setup = os.path.basename(dest).lower().startswith("setup-")
                    if is_setup:
                        set_status("Starting installer…")
                        try:
                            subprocess.Popen([dest])
                        except Exception:
                            os.startfile(dest)  # noqa: windows-only fallback
                        self.root.quit()
                    else:
                        # portable exe can't replace itself while running
                        set_status(f"Saved to {dest}")
                        self._hide_update_button()
                        self.status.config(
                            text=f"Update {tag} downloaded — swap the exe to apply it.")
                        messagebox.showinfo(
                            "Update downloaded",
                            f"New version saved to:\n{dest}\n\n"
                            "Close this app, then replace your old exe with it.")
                        try:
                            subprocess.Popen(["explorer", "/select,", dest])
                        except Exception:
                            pass

                self.root.after(0, launch)

            threading.Thread(target=worker, daemon=True).start()

        ttk.Button(btn_row, text="Download & Install", command=do_download).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Later", command=win.destroy).pack(side=tk.LEFT, padx=6)
        win.transient(self.root)
        win.grab_set()

    # ---------- scan (non-blocking) ----------
    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def start_scan(self):
        if self.scanning:
            return
        creds = self._get_scan_creds()
        if not creds:
            return
        access, secret = creds
        # validate fast before threading
        try:
            self.status.config(text="Checking keys…")
            self.root.update_idletasks()
            acct = scanner.check_creds(access, secret)
            self.log(f"Keys OK. Account: {acct}")
        except Exception as e:
            messagebox.showerror("AWS auth failed",
                                 f"Keys rejected by AWS:\n{e}\n\nUpdate keys in Settings.")
            self.status.config(text="Auth failed.")
            return

        for i in self.tree.get_children():
            self.tree.delete(i)
        self._all_rows = []
        self._services = set()
        self.svc_box.config(values=["All services"])
        self.svc_var.set("All services")
        self.count_label.config(text="0/0 shown")
        self.summary.config(text="Scanning…")
        self.stop_event.clear()
        self.scanning = True
        self.scan_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.done_tasks = 0

        target = self.region_var.get()
        regions = scanner.REGIONS if target == "ALL regions" else [target]
        # +3 global jobs
        self.total_tasks = len(regions) + 3
        self.progress["maximum"] = self.total_tasks
        self.progress["value"] = 0
        self.status.config(text=f"Scanning {len(regions)} region(s) + global services…")

        t = threading.Thread(target=self._scan_worker,
                             args=(regions, access, secret), daemon=True)
        t.start()

    def stop_scan(self):
        self.stop_event.set()
        self.log("Stopping after current calls finish…")

    def _scan_worker(self, regions, access, secret):
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(self._wrap_region, r, access, secret) for r in regions]
            futs.append(ex.submit(self._wrap_global, "s3", access, secret))
            futs.append(ex.submit(self._wrap_global, "iam", access, secret))
            futs.append(ex.submit(self._wrap_global, "route53", access, secret))
            for f in futs:
                if self.stop_event.is_set():
                    break
                try:
                    f.result()
                except Exception:
                    pass
        self.q.put(("__done__", None))

    def _wrap_region(self, region, access, secret):
        if self.stop_event.is_set():
            self.q.put(("__progress__", region))
            return
        try:
            rows = scanner.scan_region(region, access, secret)
            for row in rows:
                self.q.put(("__row__", row))
        except Exception as e:
            self.q.put(("__log__", f"{region}: {e}"))
        finally:
            self.q.put(("__progress__", region))

    def _wrap_global(self, kind, access, secret):
        try:
            if kind == "s3":
                rows = scanner.scan_s3_global(access, secret)
            elif kind == "iam":
                rows = scanner.scan_iam_global(access, secret)
            else:
                rows = scanner.scan_route53_global(access, secret)
            for row in rows:
                self.q.put(("__row__", row))
        except Exception:
            pass
        finally:
            self.q.put(("__progress__", kind))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "__row__":
                    self._all_rows.append(payload)
                    if payload[0] not in self._services:
                        self._services.add(payload[0])
                        self.svc_box.config(values=["All services"] + sorted(self._services))
                    if self._row_matches(payload):
                        self.tree.insert("", tk.END, values=payload)
                    self.count_label.config(
                        text=f"{len(self.tree.get_children())}/{len(self._all_rows)} shown")
                elif kind == "__progress__":
                    self.done_tasks += 1
                    self.progress["value"] = self.done_tasks
                    self.status.config(
                        text=f"Scanning… {self.done_tasks}/{self.total_tasks} "
                             f"({len(self._all_rows)} resources found)")
                elif kind == "__log__":
                    self.log(payload)
                elif kind == "__done__":
                    self.scanning = False
                    self.scan_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    n = len(self._all_rows)
                    self._update_summary()
                    self.status.config(text=f"Done — {n} billable resources found. Stop/delete what you don't need.")
                    self.log(f"Scan finished: {n} resources.")
                    if n == 0:
                        messagebox.showinfo("Clean", "No billable resources found in scanned scope.")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)


def main():
    root = tk.Tk()
    AWMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
