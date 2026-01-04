#!/usr/bin/env python3
"""
WGT YouTube Patcher - GUI Version
==================================
Downloads the latest Jellyfin Tizen WGT and patches it to fix YouTube Error 153.

Two patching methods available:
1. Patrick's Method: Adds origin/host parameters to YouTube player config
2. Webserver Proxy Method: Redirects YouTube embeds through a proxy server
"""

import os
import sys
import json
import shutil
import zipfile
import re
import threading
import webbrowser
import time
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from typing import Optional
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Constants - Use same repo as Samsung-Jellyfin-Installer
GITHUB_API_URL = "https://api.github.com/repos/jeppevinkel/jellyfin-tizen-builds/releases"
USER_AGENT = "SamsungJellyfinInstaller/1.0"

# Folder structure
SCRIPT_DIR = Path(__file__).parent
DOWNLOADS_DIR = SCRIPT_DIR / "downloads"
ORIGINAL_DIR = DOWNLOADS_DIR / "original"
PATCHED_PATRICK_DIR = DOWNLOADS_DIR / "patched_patrick"
PATCHED_WEBSERVER_DIR = DOWNLOADS_DIR / "patched_webserver"
PATCHED_COMBINED_DIR = DOWNLOADS_DIR / "patched_combined"
PATCHED_NOCOOKIE_DIR = DOWNLOADS_DIR / "patched_nocookie"
PATCHED_REFERRER_DIR = DOWNLOADS_DIR / "patched_referrer"
PATCHED_ALLINONE_DIR = DOWNLOADS_DIR / "patched_allinone"


class WGTPatcherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WGT YouTube Patcher")
        self.root.geometry("750x1100")
        self.root.minsize(700, 1000)

        # Configure style
        self.style = ttk.Style()
        self.style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        self.style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        self.style.configure("Info.TLabel", font=("Segoe UI", 9))
        self.style.configure("Success.TLabel", foreground="green")
        self.style.configure("Error.TLabel", foreground="red")
        self.style.configure("Big.TButton", font=("Segoe UI", 10), padding=10)

        # Variables
        self.patch_method = tk.StringVar(value="patrick")
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.latest_version = tk.StringVar(value="Unknown")
        self.wgt_filename = tk.StringVar(value="")
        self.selected_wgt = tk.StringVar(value="")
        self.is_working = False
        self._available_wgts = {}  # name -> url mapping
        self._cancel_download = False  # Flag to cancel download
        self._current_process = None  # Current download process

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Ensure directories exist
        self._ensure_directories()

        # Build UI
        self._build_ui()

        # Auto-fetch release info and scan local files
        self.root.after(500, self._fetch_release_info_async)
        self.root.after(600, self._scan_local_wgts)

        # Update button text when local selection changes
        self.local_wgt_var.trace_add("write", self._update_button_text)

    def _on_close(self):
        """Handle window close - cancel downloads and exit"""
        self._cancel_download = True
        if self._current_process:
            try:
                self._current_process.kill()
            except:
                pass
        self.root.destroy()
        os._exit(0)  # Force exit all threads

    def _update_button_text(self, *args):
        """Update button text based on local WGT selection"""
        local_wgt = self.local_wgt_var.get()
        if local_wgt:
            self.download_btn.config(text="Patch Local WGT")
            self.download_only_btn.config(state=tk.DISABLED)  # No download needed for local
        else:
            self.download_btn.config(text="Download & Patch")
            self.download_only_btn.config(state=tk.NORMAL)

    def _ensure_directories(self):
        """Create required directories"""
        for dir_path in [ORIGINAL_DIR, PATCHED_PATRICK_DIR, PATCHED_WEBSERVER_DIR, PATCHED_COMBINED_DIR,
                         PATCHED_NOCOOKIE_DIR, PATCHED_REFERRER_DIR, PATCHED_ALLINONE_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _build_ui(self):
        """Build the main UI"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="WGT YouTube Patcher",
            style="Title.TLabel"
        )
        title_label.pack(pady=(0, 5))

        # Subtitle
        subtitle = ttk.Label(
            main_frame,
            text="Fix YouTube Error 153 on Samsung Tizen TVs",
            style="Info.TLabel"
        )
        subtitle.pack(pady=(0, 20))

        # Release info frame
        release_frame = ttk.LabelFrame(main_frame, text="Latest Release", padding="10")
        release_frame.pack(fill=tk.X, pady=(0, 15))

        release_info = ttk.Frame(release_frame)
        release_info.pack(fill=tk.X)

        ttk.Label(release_info, text="Build:", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(release_info, textvariable=self.latest_version).pack(side=tk.LEFT, padx=(10, 20))

        refresh_btn = ttk.Button(release_info, text="Refresh", command=self._fetch_release_info_async, width=10)
        refresh_btn.pack(side=tk.RIGHT)

        # WGT selection dropdown
        wgt_select_frame = ttk.Frame(release_frame)
        wgt_select_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(wgt_select_frame, text="Select WGT:", style="Header.TLabel").pack(side=tk.LEFT)
        self.wgt_combo = ttk.Combobox(
            wgt_select_frame,
            textvariable=self.selected_wgt,
            state="readonly",
            width=50
        )
        self.wgt_combo.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)

        # Local WGT selection
        local_frame = ttk.Frame(release_frame)
        local_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(local_frame, text="Or use local:", style="Header.TLabel").pack(side=tk.LEFT)
        self.local_wgt_var = tk.StringVar(value="")
        self.local_combo = ttk.Combobox(
            local_frame,
            textvariable=self.local_wgt_var,
            state="readonly",
            width=40
        )
        self.local_combo.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)

        browse_btn = ttk.Button(local_frame, text="Browse", command=self._browse_local_wgt, width=8)
        browse_btn.pack(side=tk.LEFT, padx=(5, 0))

        refresh_local_btn = ttk.Button(local_frame, text="Scan", command=self._scan_local_wgts, width=6)
        refresh_local_btn.pack(side=tk.LEFT, padx=(5, 0))

        clear_local_btn = ttk.Button(local_frame, text="X", command=lambda: self.local_wgt_var.set(""), width=3)
        clear_local_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Patch method selection
        method_frame = ttk.LabelFrame(main_frame, text="Patch Method", padding="15")
        method_frame.pack(fill=tk.X, pady=(0, 15))

        # Patrick's Method
        patrick_frame = ttk.Frame(method_frame)
        patrick_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Radiobutton(
            patrick_frame,
            text="Patrick's Method (Recommended)",
            variable=self.patch_method,
            value="patrick"
        ).pack(anchor=tk.W)

        patrick_desc = ttk.Label(
            patrick_frame,
            text="Adds 'origin' and 'host' parameters to YouTube playerVars.\n"
                 "Simple and direct fix targeting the iframe API configuration.",
            style="Info.TLabel",
            foreground="gray"
        )
        patrick_desc.pack(anchor=tk.W, padx=(25, 0))

        # Webserver Method
        webserver_frame = ttk.Frame(method_frame)
        webserver_frame.pack(fill=tk.X, pady=(10, 10))

        ttk.Radiobutton(
            webserver_frame,
            text="Webserver/Proxy Method",
            variable=self.patch_method,
            value="webserver"
        ).pack(anchor=tk.W)

        webserver_desc = ttk.Label(
            webserver_frame,
            text="Injects a wrapper that intercepts YouTube API calls.\n"
                 "Also adds referrer meta tag and creates a proxy server script.",
            style="Info.TLabel",
            foreground="gray"
        )
        webserver_desc.pack(anchor=tk.W, padx=(25, 0))

        # Combined Method
        combined_frame = ttk.Frame(method_frame)
        combined_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Radiobutton(
            combined_frame,
            text="Patrick + Webserver Combined",
            variable=self.patch_method,
            value="combined"
        ).pack(anchor=tk.W)

        combined_desc = ttk.Label(
            combined_frame,
            text="Applies Patrick's + Webserver patches together.",
            style="Info.TLabel",
            foreground="gray"
        )
        combined_desc.pack(anchor=tk.W, padx=(25, 0))

        # NoCookie Method
        nocookie_frame = ttk.Frame(method_frame)
        nocookie_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Radiobutton(
            nocookie_frame,
            text="YouTube NoCookie Domain",
            variable=self.patch_method,
            value="nocookie"
        ).pack(anchor=tk.W)

        nocookie_desc = ttk.Label(
            nocookie_frame,
            text="Replaces youtube.com with youtube-nocookie.com.\n"
                 "Privacy-focused domain with different header requirements.",
            style="Info.TLabel",
            foreground="gray"
        )
        nocookie_desc.pack(anchor=tk.W, padx=(25, 0))

        # Referrer Policy Method
        referrer_frame = ttk.Frame(method_frame)
        referrer_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Radiobutton(
            referrer_frame,
            text="Referrer Policy Fix",
            variable=self.patch_method,
            value="referrer"
        ).pack(anchor=tk.W)

        referrer_desc = ttk.Label(
            referrer_frame,
            text="Adds strict-origin-when-cross-origin referrer policy.\n"
                 "Patches all iframes and adds CSP headers.",
            style="Info.TLabel",
            foreground="gray"
        )
        referrer_desc.pack(anchor=tk.W, padx=(25, 0))

        # All-in-One Method
        allinone_frame = ttk.Frame(method_frame)
        allinone_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Radiobutton(
            allinone_frame,
            text="ALL-IN-ONE (All Methods)",
            variable=self.patch_method,
            value="allinone"
        ).pack(anchor=tk.W)

        allinone_desc = ttk.Label(
            allinone_frame,
            text="Applies ALL patches: Patrick + Webserver + NoCookie + Referrer.\n"
                 "Maximum compatibility - try this if nothing else works!",
            style="Info.TLabel",
            foreground="green"
        )
        allinone_desc.pack(anchor=tk.W, padx=(25, 0))

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 15))

        self.download_btn = ttk.Button(
            button_frame,
            text="Download & Patch",
            command=self._start_download_and_patch,
            style="Big.TButton"
        )
        self.download_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        self.download_only_btn = ttk.Button(
            button_frame,
            text="Download Only",
            command=self._start_download_only,
            style="Big.TButton"
        )
        self.download_only_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 5))

        self.open_folder_btn = ttk.Button(
            button_frame,
            text="Open Folder",
            command=self._open_downloads_folder,
            style="Big.TButton"
        )
        self.open_folder_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Progress
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X)

        # Status
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X)

        ttk.Label(status_frame, text="Status:", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        # Log text with scrollbar
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_frame,
            height=10,
            font=("Consolas", 9),
            yscrollcommand=log_scroll.set,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)

        # Configure log tags
        self.log_text.tag_configure("info", foreground="blue")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("error", foreground="red")

        # GitHub links
        links_frame = ttk.Frame(main_frame)
        links_frame.pack(fill=tk.X, pady=(10, 0))

        link1 = ttk.Label(
            links_frame,
            text="Issue #215",
            foreground="blue",
            cursor="hand2"
        )
        link1.pack(side=tk.LEFT)
        link1.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/PatrickSt1991/Samsung-Jellyfin-Installer/issues/215"))

        ttk.Label(links_frame, text=" | ").pack(side=tk.LEFT)

        link2 = ttk.Label(
            links_frame,
            text="Issue #374",
            foreground="blue",
            cursor="hand2"
        )
        link2.pack(side=tk.LEFT)
        link2.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/jellyfin/jellyfin-tizen/issues/374"))

    def _log(self, message: str, level: str = "info"):
        """Add message to log"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] ", "")
        self.log_text.insert(tk.END, f"{message}\n", level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_status(self, status: str, is_error: bool = False):
        """Update status label"""
        self.status_var.set(status)
        if is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="")

    def _set_working(self, working: bool):
        """Enable/disable buttons during work"""
        self.is_working = working
        state = tk.DISABLED if working else tk.NORMAL
        self.download_btn.config(state=state)
        self.download_only_btn.config(state=state)

        if working:
            self.progress_var.set(0)

    def _fetch_release_info_async(self):
        """Fetch release info in background"""
        def fetch():
            try:
                self.root.after(0, lambda: self._set_status("Fetching release info..."))
                self.root.after(0, lambda: self._log("Fetching latest release from GitHub...", "info"))

                req = Request(GITHUB_API_URL, headers={"User-Agent": USER_AGENT})
                with urlopen(req, timeout=30) as response:
                    releases = json.loads(response.read().decode())

                # API returns a list of releases, take the first one
                if not releases or len(releases) == 0:
                    raise Exception("No releases found")

                data = releases[0]  # First release is the latest
                version = data.get("tag_name", "unknown")

                # Collect ALL WGT assets and sort them
                wgt_files = {}
                for asset in data.get("assets", []):
                    name = asset["name"]
                    if name.endswith(".wgt"):
                        wgt_files[name] = asset["browser_download_url"]

                # Sort: prioritize 10.11, then 10.10, then others
                def sort_key(name):
                    if "10.11" in name:
                        return (0, name)
                    elif "10.10" in name:
                        return (1, name)
                    elif "master" in name:
                        return (2, name)
                    elif "prerelease" in name:
                        return (3, name)
                    else:
                        return (4, name)

                sorted_names = sorted(wgt_files.keys(), key=sort_key)

                self.root.after(0, lambda: self._update_release_info(version, sorted_names, wgt_files))

            except Exception as e:
                self.root.after(0, lambda: self._log(f"Failed to fetch: {e}", "error"))
                self.root.after(0, lambda: self._set_status("Failed to fetch release", True))

        threading.Thread(target=fetch, daemon=True).start()

    def _update_release_info(self, version: str, wgt_names: list, wgt_files: dict):
        """Update UI with release info"""
        self.latest_version.set(version)
        self._available_wgts = wgt_files

        if wgt_names:
            self.wgt_combo['values'] = wgt_names
            # Select first 10.11 version by default, or first available
            default = wgt_names[0]
            for name in wgt_names:
                if "10.11" in name and "Jellyfin" in name and "GrayFix" not in name:
                    default = name
                    break
            self.selected_wgt.set(default)
            self._log(f"Found {len(wgt_names)} WGT files in release {version}", "success")
            self._set_status("Ready")
        else:
            self._log("No WGT files found in release!", "error")
            self._set_status("No WGT found", True)

    def _open_downloads_folder(self):
        """Open downloads folder in file explorer"""
        if sys.platform == "win32":
            os.startfile(DOWNLOADS_DIR)
        elif sys.platform == "darwin":
            os.system(f'open "{DOWNLOADS_DIR}"')
        else:
            os.system(f'xdg-open "{DOWNLOADS_DIR}"')

    def _scan_local_wgts(self):
        """Scan original folder for existing WGT files"""
        wgts = list(ORIGINAL_DIR.glob("*.wgt"))
        wgt_names = [w.name for w in wgts if w.stat().st_size > 1000000]  # Only files > 1MB

        if wgt_names:
            self.local_combo['values'] = [""] + wgt_names
            self._log(f"Found {len(wgt_names)} local WGT files", "success")
        else:
            self.local_combo['values'] = [""]
            self._log("No local WGT files found in downloads/original", "warning")

    def _browse_local_wgt(self):
        """Browse for a local WGT file"""
        filepath = filedialog.askopenfilename(
            title="Select WGT file",
            initialdir=ORIGINAL_DIR,
            filetypes=[("WGT files", "*.wgt"), ("All files", "*.*")]
        )
        if filepath:
            path = Path(filepath)
            # Copy to original folder if not already there
            if path.parent != ORIGINAL_DIR:
                dest = ORIGINAL_DIR / path.name
                shutil.copy2(path, dest)
                self._log(f"Copied {path.name} to downloads/original", "info")

            self._scan_local_wgts()
            self.local_wgt_var.set(path.name)

    def _start_download_only(self):
        """Start download without patching"""
        self._start_work(patch=False)

    def _start_download_and_patch(self):
        """Start download and patch"""
        self._start_work(patch=True)

    def _start_work(self, patch: bool):
        """Start the download/patch process"""
        if self.is_working:
            return

        # Check if local WGT is selected
        local_wgt = self.local_wgt_var.get()
        if local_wgt:
            local_path = ORIGINAL_DIR / local_wgt
            if local_path.exists():
                self._set_working(True)
                method = self.patch_method.get() if patch else None
                threading.Thread(target=self._patch_local, args=(method, local_path), daemon=True).start()
                return

        # Otherwise use remote WGT
        selected = self.selected_wgt.get()
        if not selected or selected not in self._available_wgts:
            messagebox.showerror("Error", "No WGT selected. Select from dropdown or use local file.")
            return

        self._set_working(True)

        method = self.patch_method.get() if patch else None
        wgt_url = self._available_wgts[selected]
        threading.Thread(target=self._download_and_patch, args=(method, selected, wgt_url), daemon=True).start()

    def _patch_local(self, method: Optional[str], wgt_path: Path):
        """Patch a local WGT file without downloading"""
        try:
            self.root.after(0, lambda: self._log(f"Using local: {wgt_path.name}", "info"))
            self.root.after(0, lambda: self.progress_var.set(50))

            if method is None:
                self.root.after(0, lambda: self._log("No patch method selected", "info"))
                self.root.after(0, lambda: self._set_status("Ready"))
                return

            # Patch
            self.root.after(0, lambda: self._set_status(f"Patching WGT ({method})..."))
            self.root.after(0, lambda: self._log("Patching directly in ZIP (fast method)...", "info"))

            output_dir = {
                "patrick": PATCHED_PATRICK_DIR,
                "webserver": PATCHED_WEBSERVER_DIR,
                "combined": PATCHED_COMBINED_DIR,
                "nocookie": PATCHED_NOCOOKIE_DIR,
                "referrer": PATCHED_REFERRER_DIR,
                "allinone": PATCHED_ALLINONE_DIR,
            }.get(method, PATCHED_PATRICK_DIR)

            output_path = output_dir / f"{wgt_path.stem}_patched_{method}.wgt"
            success = self._patch_zip_direct(wgt_path, output_path, method)

            if not success:
                self.root.after(0, lambda: self._log("Patching failed!", "error"))
                self.root.after(0, lambda: self._set_status("Patching failed", True))
                return

            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self._log(f"Patched WGT: {output_path}", "success"))
            self.root.after(0, lambda: self._set_status("Patching complete!"))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Patched WGT created:\n{output_path}"))

        except Exception as e:
            self.root.after(0, lambda: self._log(f"Error: {e}", "error"))
            self.root.after(0, lambda: self._set_status(f"Error: {e}", True))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self._set_working(False))

    def _download_and_patch(self, method: Optional[str], wgt_name: str, wgt_url: str):
        """Download and optionally patch the WGT - FAST version using direct ZIP patching"""
        try:
            wgt_path = ORIGINAL_DIR / wgt_name

            # Download if not exists or incomplete
            if not wgt_path.exists() or wgt_path.stat().st_size < 1000000:  # < 1MB = incomplete
                self._download_wgt(wgt_url, wgt_path)
            else:
                self.root.after(0, lambda: self._log(f"Using cached: {wgt_name}", "info"))
                self.root.after(0, lambda: self.progress_var.set(50))

            if method is None:
                self.root.after(0, lambda: self._log("Download complete!", "success"))
                self.root.after(0, lambda: self._set_status("Download complete"))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Downloaded to:\n{wgt_path}"))
                return

            # Fast patching - directly modify ZIP without full extraction
            self.root.after(0, lambda: self._set_status(f"Patching WGT ({method})..."))
            self.root.after(0, lambda: self._log("Patching directly in ZIP (fast method)...", "info"))

            output_dir = {
                "patrick": PATCHED_PATRICK_DIR,
                "webserver": PATCHED_WEBSERVER_DIR,
                "combined": PATCHED_COMBINED_DIR,
                "nocookie": PATCHED_NOCOOKIE_DIR,
                "referrer": PATCHED_REFERRER_DIR,
                "allinone": PATCHED_ALLINONE_DIR,
            }.get(method, PATCHED_PATRICK_DIR)

            output_path = output_dir / f"{wgt_path.stem}_patched_{method}.wgt"
            success = self._patch_zip_direct(wgt_path, output_path, method)

            if not success:
                self.root.after(0, lambda: self._log("Patching failed!", "error"))
                self.root.after(0, lambda: self._set_status("Patching failed", True))
                return

            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self._log(f"Patched WGT: {output_path}", "success"))
            self.root.after(0, lambda: self._set_status("Patching complete!"))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Patched WGT created:\n{output_path}"))

        except Exception as e:
            self.root.after(0, lambda: self._log(f"Error: {e}", "error"))
            self.root.after(0, lambda: self._set_status(f"Error: {e}", True))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self._set_working(False))

    def _patch_zip_direct(self, input_path: Path, output_path: Path, method: str) -> bool:
        """Patch WGT directly without full extraction - FAST"""
        plugin_paths = [
            "user-scripts/plugins/youtubePlayer/plugin.js",
            "plugins/youtubePlayer/plugin.js",
            "www/plugins/youtubePlayer/plugin.js",
            "app/plugins/youtubePlayer/plugin.js",
        ]
        index_paths = ["index.html", "www/index.html", "app/index.html"]

        # Read input ZIP
        with zipfile.ZipFile(input_path, 'r') as zf_in:
            names = zf_in.namelist()

            # Find YouTube plugin - try exact paths first
            plugin_name = None
            for p in plugin_paths:
                if p in names:
                    plugin_name = p
                    break

            # Try broader search for any youtubePlayer plugin.js
            if not plugin_name:
                for n in names:
                    if "youtubeplayer" in n.lower() and n.lower().endswith("plugin.js"):
                        plugin_name = n
                        break

            # Try even broader - any plugin.js with youtube in path
            if not plugin_name:
                for n in names:
                    if "youtube" in n.lower() and "plugin.js" in n.lower():
                        plugin_name = n
                        break

            # WEBPACK BUNDLES: Search for youtubePlayer chunk files
            if not plugin_name:
                for n in names:
                    if "youtubeplayer" in n.lower() and n.endswith(".js"):
                        plugin_name = n
                        self.root.after(0, lambda: self._log(f"Found webpack chunk: {n}", "info"))
                        break

            # LAST RESORT: Search ALL JS files for playerVars content
            if not plugin_name:
                self.root.after(0, lambda: self._log("Searching JS files for playerVars...", "info"))
                js_files = [n for n in names if n.endswith(".js") and not n.endswith(".LICENSE.txt")]
                for n in js_files:
                    try:
                        content = zf_in.read(n).decode('utf-8', errors='ignore')
                        if 'playerVars' in content and ('enablejsapi' in content.lower() or 'youtube' in content.lower()):
                            plugin_name = n
                            self.root.after(0, lambda pn=n: self._log(f"Found playerVars in: {pn}", "success"))
                            break
                    except:
                        continue

            # Find index.html
            index_name = None
            for p in index_paths:
                if p in names:
                    index_name = p
                    break

            # Broader search for index.html
            if not index_name:
                for n in names:
                    if n.lower().endswith("index.html"):
                        index_name = n
                        break

            if not plugin_name:
                # Log what we found to help debug
                self.root.after(0, lambda: self._log("YouTube plugin/playerVars not found in ZIP!", "error"))

                # Check for youtube-related files
                youtube_files = [n for n in names if "youtube" in n.lower()]
                if youtube_files:
                    self.root.after(0, lambda: self._log(f"YouTube files: {youtube_files}", "warning"))

                # Check for main bundle
                main_files = [n for n in names if "main" in n.lower() and n.endswith(".js")]
                if main_files:
                    self.root.after(0, lambda: self._log(f"Main bundles: {main_files}", "warning"))

                # All plugin chunks
                plugin_files = [n for n in names if "plugin" in n.lower() and n.endswith(".js")]
                self.root.after(0, lambda: self._log(f"Plugin chunks ({len(plugin_files)}): {plugin_files[:5]}...", "warning"))

                return False

            self.root.after(0, lambda: self._log(f"Found plugin: {plugin_name}", "success"))
            self.root.after(0, lambda: self.progress_var.set(60))

            # Read plugin content
            plugin_content = zf_in.read(plugin_name).decode('utf-8')
            plugin_patched = plugin_content

            # Read index content
            index_content = None
            index_patched = None
            if index_name:
                index_content = zf_in.read(index_name).decode('utf-8')
                index_patched = index_content

            # Track which JS files need nocookie patching (for nocookie/allinone)
            js_files_to_patch = {}

            # Apply patches based on method
            if method in ["patrick", "combined", "allinone"]:
                plugin_patched = self._apply_patrick_patch(plugin_patched)

            if method in ["webserver", "combined", "allinone"]:
                if index_patched:
                    index_patched = self._apply_webserver_patch(index_patched)
                    self.root.after(0, lambda: self._log("Webserver patch applied to index", "success"))

            if method in ["nocookie", "allinone"]:
                # Patch plugin for nocookie
                plugin_patched = self._apply_nocookie_patch(plugin_patched)
                # Collect all JS files for nocookie patching
                for n in names:
                    if n.endswith(".js") and n != plugin_name:
                        try:
                            content = zf_in.read(n).decode('utf-8', errors='ignore')
                            if 'youtube.com' in content.lower():
                                js_files_to_patch[n] = self._apply_nocookie_patch(content)
                        except:
                            pass
                self.root.after(0, lambda: self._log(f"NoCookie patch applied ({len(js_files_to_patch)+1} files)", "success"))

            if method in ["referrer", "allinone"]:
                if index_patched:
                    index_patched = self._apply_referrer_patch(index_patched)
                    self.root.after(0, lambda: self._log("Referrer policy patch applied", "success"))

            self.root.after(0, lambda: self.progress_var.set(70))
            self.root.after(0, lambda: self._log("Writing patched WGT...", "info"))

            # Write output ZIP with patched files
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as zf_out:
                for name in names:
                    if name == plugin_name:
                        zf_out.writestr(name, plugin_patched.encode('utf-8'))
                    elif name == index_name and index_patched:
                        zf_out.writestr(name, index_patched.encode('utf-8'))
                    elif name in js_files_to_patch:
                        zf_out.writestr(name, js_files_to_patch[name].encode('utf-8'))
                    else:
                        zf_out.writestr(name, zf_in.read(name))

            self.root.after(0, lambda: self.progress_var.set(90))

        return True

    def _apply_patrick_patch(self, content: str) -> str:
        """Apply Patrick's origin/host patch to plugin content"""
        # Pattern for playerVars
        pattern = r'(playerVars\s*:\s*\{[^}]*)(})'

        def add_origin(match):
            existing = match.group(1)
            if 'origin' in existing.lower():
                return match.group(0)
            comma = "" if existing.rstrip().endswith(',') else ","
            return existing + comma + "origin:'https://www.youtube.com',host:'https://www.youtube.com'" + match.group(2)

        result, count = re.subn(pattern, add_origin, content, flags=re.DOTALL)

        if count == 0:
            # Try minified
            pattern2 = r'(playerVars:\{[^}]*)(})'
            result, count = re.subn(pattern2, add_origin, content, flags=re.DOTALL)

        if count == 0:
            # Fallback: after enablejsapi
            pattern3 = r'(enablejsapi\s*:\s*1)'
            result = re.sub(pattern3, r"\1,origin:'https://www.youtube.com',host:'https://www.youtube.com'", content)

        self.root.after(0, lambda: self._log(f"Patrick patch applied", "success"))
        return result

    def _apply_webserver_patch(self, content: str) -> str:
        """Inject YouTube wrapper script into index.html"""
        wrapper = '''<script>
(function(){
if(window.YT&&window.YT.Player){var O=window.YT.Player;window.YT.Player=function(e,c){if(c&&c.playerVars){c.playerVars.origin='https://www.youtube.com';c.playerVars.host='https://www.youtube.com';}return new O(e,c);};Object.keys(O).forEach(function(k){window.YT.Player[k]=O[k];});}
if(!document.querySelector('meta[name="referrer"]')){var m=document.createElement('meta');m.name='referrer';m.content='origin';document.head.appendChild(m);}
})();
</script>'''
        return content.replace('</head>', wrapper + '\n</head>')

    def _apply_nocookie_patch(self, content: str) -> str:
        """Replace youtube.com with youtube-nocookie.com for privacy-enhanced embeds"""
        # Replace various YouTube domain patterns
        replacements = [
            ('https://www.youtube.com/embed/', 'https://www.youtube-nocookie.com/embed/'),
            ('https://youtube.com/embed/', 'https://www.youtube-nocookie.com/embed/'),
            ('http://www.youtube.com/embed/', 'https://www.youtube-nocookie.com/embed/'),
            ('//www.youtube.com/embed/', '//www.youtube-nocookie.com/embed/'),
            ("'https://www.youtube.com'", "'https://www.youtube-nocookie.com'"),
            ('"https://www.youtube.com"', '"https://www.youtube-nocookie.com"'),
            # Also patch iframe API URL
            ('https://www.youtube.com/iframe_api', 'https://www.youtube-nocookie.com/iframe_api'),
        ]

        result = content
        for old, new in replacements:
            result = result.replace(old, new)

        return result

    def _apply_referrer_patch(self, content: str) -> str:
        """Add comprehensive referrer policy to index.html"""
        # Meta tag for referrer policy
        referrer_meta = '<meta name="referrer" content="strict-origin-when-cross-origin">'

        # Check if already present
        if 'strict-origin-when-cross-origin' in content:
            return content

        # CSP meta tag to allow YouTube
        csp_meta = '''<meta http-equiv="Content-Security-Policy" content="
    default-src 'self' https://*.youtube.com https://*.youtube-nocookie.com https://*.googlevideo.com;
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.youtube.com https://*.youtube-nocookie.com;
    frame-src https://*.youtube.com https://*.youtube-nocookie.com;
    img-src 'self' data: https://*.ytimg.com https://*.youtube.com;
">'''

        # JavaScript to patch all iframes with referrerpolicy attribute
        iframe_patch = '''<script>
(function(){
    // Patch existing iframes
    document.querySelectorAll('iframe').forEach(function(iframe){
        if(iframe.src && iframe.src.indexOf('youtube') !== -1){
            iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
        }
    });
    // Patch future iframes
    var origCreate = document.createElement;
    document.createElement = function(tag){
        var el = origCreate.call(document, tag);
        if(tag.toLowerCase() === 'iframe'){
            el.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
        }
        return el;
    };
    console.log('YT Patcher: Referrer policy applied to all iframes');
})();
</script>'''

        # Insert meta tags after <head>
        if '<head>' in content:
            content = content.replace('<head>', f'<head>\n{referrer_meta}\n')

        # Insert iframe patch before </head>
        content = content.replace('</head>', f'{iframe_patch}\n</head>')

        return content

    def _download_wgt(self, url: str, output_path: Path):
        """Download WGT file using native curl/PowerShell for speed"""
        self._cancel_download = False
        self.root.after(0, lambda: self._set_status("Downloading WGT..."))
        self.root.after(0, lambda: self._log(f"Downloading: {output_path.name}", "info"))

        # Delete incomplete file if exists
        if output_path.exists():
            output_path.unlink()

        start_time = time.time()

        # Try curl first (fastest) - use curl.exe on Windows for native speed
        try:
            curl_cmd = "curl.exe" if sys.platform == "win32" else "curl"
            self.root.after(0, lambda: self._log("Using curl for fast download...", "info"))

            # Don't capture output - let curl run at full speed
            process = subprocess.Popen(
                [curl_cmd, "-L", "-o", str(output_path), url, "--silent", "--fail"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._current_process = process

            # Wait for completion
            while process.poll() is None:
                if self._cancel_download:
                    process.kill()
                    if output_path.exists():
                        output_path.unlink()
                    raise Exception("Download cancelled")
                time.sleep(0.2)

                # Update progress based on file size
                if output_path.exists():
                    current_size = output_path.stat().st_size
                    elapsed = time.time() - start_time
                    speed = current_size / elapsed if elapsed > 0 else 0
                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed > 1024*1024 else f"{speed / 1024:.0f} KB/s"
                    # Estimate remaining time (assume ~10MB total if unknown)
                    estimated_total = 10 * 1024 * 1024
                    remaining_bytes = max(0, estimated_total - current_size)
                    eta = remaining_bytes / speed if speed > 0 else 0
                    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m{int(eta%60)}s"
                    status = f"Downloading: {current_size / 1024 / 1024:.1f} MB | {speed_str} | ETA: {eta_str}"
                    self.root.after(0, lambda s=status: self._set_status(s))

            if process.returncode != 0:
                raise Exception("curl failed")

        except FileNotFoundError:
            # curl not found, use PowerShell (Windows)
            self.root.after(0, lambda: self._log("curl not found, using PowerShell...", "warning"))

            ps_script = f'''
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$wc = New-Object System.Net.WebClient
$wc.DownloadFile("{url}", "{output_path}")
'''
            process = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self._current_process = process

            while process.poll() is None:
                if self._cancel_download:
                    process.kill()
                    if output_path.exists():
                        output_path.unlink()
                    raise Exception("Download cancelled")
                time.sleep(0.1)

                if output_path.exists():
                    current_size = output_path.stat().st_size
                    elapsed = time.time() - start_time
                    speed = current_size / elapsed if elapsed > 0 else 0
                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed > 1024*1024 else f"{speed / 1024:.0f} KB/s"
                    estimated_total = 10 * 1024 * 1024
                    remaining_bytes = max(0, estimated_total - current_size)
                    eta = remaining_bytes / speed if speed > 0 else 0
                    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m{int(eta%60)}s"
                    status = f"Downloading: {current_size / 1024 / 1024:.1f} MB | {speed_str} | ETA: {eta_str}"
                    self.root.after(0, lambda s=status: self._set_status(s))

            if process.returncode != 0:
                raise Exception("PowerShell failed")

        finally:
            self._current_process = None

        # Verify
        if not output_path.exists():
            raise Exception("Download failed - file not created")

        actual_size = output_path.stat().st_size
        if actual_size < 1000000:  # Less than 1MB = probably failed
            output_path.unlink()
            raise Exception(f"Download too small: {actual_size} bytes")

        elapsed = time.time() - start_time
        avg_speed = actual_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
        self.root.after(0, lambda: self.progress_var.set(50))
        self.root.after(0, lambda: self._log(f"Downloaded: {actual_size/1024/1024:.1f} MB in {elapsed:.1f}s ({avg_speed:.1f} MB/s)", "success"))


def main():
    root = tk.Tk()

    # Set icon if available
    try:
        # You can add an icon file here
        pass
    except:
        pass

    app = WGTPatcherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
