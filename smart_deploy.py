#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ftplib
import os
import sys
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
from pathlib import Path
from queue import Queue
import json
import stat

# ================= CONFIGURATION & CONSTANTS =================

CONFIG_FILENAME = "deploy_config.json"

DEFAULT_CONFIG = {
    "FTP_HOST": "",
    "FTP_USER": "",
    "FTP_PASS": "",
    "LOCAL_DIR": ".",
    "REMOTE_DIR": "/",
    "EXCLUDE_PATTERNS": [
        "*.git*", ".env", "node_modules", "vendor", ".idea", ".vscode", "deploy_config.json"
    ],
    "PATH_MAPPINGS": [] 
}

# ================= UI COLORS 2026 =================

CLR_BG = "#0D1117"        # Dark Deep Space
CLR_SURFACE = "#161B22"   # Github Dark Surface
CLR_BORDER = "#30363D"    # Border subtle
CLR_ACCENT = "#58A6FF"    # Modern Blue
CLR_SUCCESS = "#238636"   # Success Green
CLR_DANGER = "#DA3633"    # Error Red
CLR_TEXT = "#C9D1D9"      # Main Text
CLR_TEXT_DIM = "#8B949E"  # Muted Text
CLR_HASH = "#D2A8FF"      # Purple Hash
CLR_QUICK = "#F2A742"     # Gold/Orange for Quick Deploy

# ================= UTILS & MULTI-CONFIG STORE =================

log_queue = Queue()

def load_config_store():
    """
    Memuat store konfigurasi (multi-profile).
    Mendukung format lama (single-config) dan otomatis mengubahnya ke multi-profile.
    """
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    
    default_store = {
        "active_profile": "Default",
        "profiles": {
            "Default": DEFAULT_CONFIG.copy()
        }
    }

    if config_path.is_file():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Format Multi-Profile Modern
            if "profiles" in data and isinstance(data["profiles"], dict) and data["profiles"]:
                for p_name, p_cfg in data["profiles"].items():
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(p_cfg)
                    if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                        merged["EXCLUDE_PATTERNS"] = [l for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()]
                    if merged.get("PATH_MAPPINGS") is None:
                        merged["PATH_MAPPINGS"] = []
                    data["profiles"][p_name] = merged

                if data.get("active_profile") not in data["profiles"]:
                    data["active_profile"] = list(data["profiles"].keys())[0]
                return data
            else:
                # Migrasi otomatis dari file konfigurasi single lama
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                    merged["EXCLUDE_PATTERNS"] = [l for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()]
                if merged.get("PATH_MAPPINGS") is None:
                    merged["PATH_MAPPINGS"] = []
                
                migrated = {
                    "active_profile": "Default",
                    "profiles": {
                        "Default": merged
                    }
                }
                return migrated
        except Exception as e:
            log_queue.put(f"[CONFIG] Gagal memuat {config_path}: {e}")
            return default_store
    return default_store

def save_config_store(store_dict):
    """Menyimpan seluruh profile store ke file deploy_config.json."""
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(store_dict, f, indent=2, ensure_ascii=False)
        log_queue.put(f"[CONFIG] Konfigurasi profil disimpan ke {config_path}")
        return True
    except Exception as e:
        log_queue.put(f"[CONFIG] Gagal menyimpan konfigurasi: {e}")
        return False

def should_exclude(file_path, exclude_patterns):
    path_str = Path(file_path).as_posix()
    for pattern in exclude_patterns:
        if not pattern: continue
        if path_str.startswith(pattern) or f"/{pattern}" in path_str:
            return True
    return False

def resolve_remote_path(local_rel_path, mappings):
    path_obj = Path(local_rel_path)
    posix_path = path_obj.as_posix()
    for m in mappings:
        local_prefix = m.get("local", "").strip()
        remote_prefix = m.get("remote", "").strip()
        if not local_prefix: continue
        if not local_prefix.endswith('/'): local_prefix += '/'
        if posix_path.startswith(local_prefix):
            stripped = posix_path[len(local_prefix):]
            final_path = str(Path(remote_prefix) / stripped)
            return Path(final_path).as_posix()
    return posix_path

# ================= GIT MANAGER =================

class GitManager:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / '.git').is_dir():
            raise FileNotFoundError(f"Direktori .git tidak ditemukan di '{self.repo_path}'.")

    def get_recent_commits(self, count=35):
        command = ['git', 'log', f'-n{count}', '--pretty=format:%H|%an|%s|%ad', '--date=short']
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding='utf-8')
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line: continue
                parts = line.split('|', 3)
                commits.append({'hash': parts[0], 'author': parts[1], 'subject': parts[2], 'date': parts[3]})
            return commits
        except Exception as e:
            log_queue.put(f"GIT ERROR: {e}")
            return []

    def get_changed_files(self, start_hash, end_hash, exclude_patterns):
        if start_hash == end_hash:
            command = ['git', 'show', '--pretty=', '--name-status', start_hash]
        else:
            command = ['git', 'diff', '--name-status', f'{start_hash}^', end_hash]
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, encoding='utf-8')
        except Exception as e:
            log_queue.put(f"GIT DIFF ERROR: {e}")
            return {'added_modified': [], 'deleted': []}
        files = {'added_modified': [], 'deleted': []}
        for line in result.stdout.strip().split('\n'):
            if not line: continue
            parts = line.split('\t')
            if len(parts) < 2: continue
            status = parts[0][0]
            file_path_str = parts[-1]
            if should_exclude(file_path_str, exclude_patterns): continue
            if status.upper() in ['A', 'M', 'C', 'R']: files['added_modified'].append(file_path_str)
            elif status.upper() == 'D': files['deleted'].append(file_path_str)
        return files

# ================= FTP DEPLOYER =================

class FTPDeployer:
    def __init__(self, config):
        self.host = config["FTP_HOST"]
        self.user = config["FTP_USER"]
        self.password = config["FTP_PASS"]
        self.local_dir = Path(config["LOCAL_DIR"]).resolve()
        self.remote_dir_base = config["REMOTE_DIR"]
        self.mappings = config.get("PATH_MAPPINGS", [])
        self.ftp = None

    def _log(self, message): log_queue.put(message)

    def connect(self):
        try:
            self._log(f"⚡ Menghubungkan ke {self.host}...")
            self.ftp = ftplib.FTP(self.host, timeout=30)
            self.ftp.login(self.user, self.password)
            self.ftp.set_pasv(True)
            self._log("✔️ Terhubung (Passive Mode).")
            try: self.ftp.cwd(self.remote_dir_base)
            except: self._log(f"⚠️ Gagal masuk ke {self.remote_dir_base}, di root.")
            return True
        except Exception as e:
            self._log(f"❌ FTP ERROR: {e}")
            return False

    def disconnect(self):
        if self.ftp:
            try: self.ftp.quit()
            except: pass

    def ensure_remote_dir(self, remote_file_path):
        p = Path(remote_file_path)
        parent_dir = p.parent.as_posix()
        if parent_dir in [".", "/", ""]: return
        parts = parent_dir.split('/')
        current = ""
        for part in parts:
            if not part: continue
            current += "/" + part
            try: self.ftp.mkd(current)
            except: pass

    def upload_file(self, local_rel_path):
        local_abs = self.local_dir / local_rel_path
        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        
        filesize = os.path.getsize(local_abs)
        uploaded_bytes = 0
        last_percent = -1

        def progress_callback(data):
            nonlocal uploaded_bytes, last_percent
            uploaded_bytes += len(data)
            percent = int((uploaded_bytes / filesize) * 100) if filesize > 0 else 100
            
            if percent % 10 == 0 and percent != last_percent:
                self._log(f"   [ {percent}% ] {local_rel_path}")
                last_percent = percent

        self._log(f"⬆️ UP: {local_rel_path} ({filesize / 1024 / 1024:.2f} MB)")
        try:
            self.ensure_remote_dir(final_remote_path)
            with open(local_abs, 'rb') as f:
                self.ftp.storbinary(f'STOR {final_remote_path}', f, callback=progress_callback)
            return True
        except Exception as e:
            self._log(f"❌ ERROR Upload {final_remote_path}: {e}")
            return False

    def delete_file(self, local_rel_path):
        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        self._log(f"🗑️ DEL: {final_remote_path}")
        try:
            self.ftp.delete(final_remote_path)
            return True
        except: return False

    def deploy(self, files_to_process):
        if not self.connect(): return
        added = files_to_process.get('added_modified', [])
        deleted = files_to_process.get('deleted', [])
        self._log(f"🚀 Memulai Deployment: {len(added)+len(deleted)} item.")
        for f in deleted: self.delete_file(f)
        for f in added: self.upload_file(f)
        self._log("✨ Deployment Selesai Berhasil!")
        self.disconnect()

# ================= GUI APPLICATION =================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Git-FTP Deployer V2.5 (Multi-Profile Support)")
        self.geometry("1220x880")
        self.configure(bg=CLR_BG)
        
        # Load Multi-profile Data
        self.config_store = load_config_store()
        self.active_profile = self.config_store.get("active_profile", "Default")
        self.config_data = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy())
        
        self.git = None
        self.commits_data = []
        self.files_to_process = {'added_modified': [], 'deleted': []}
        self.browser_ftp = None
        self.ftp_lock = threading.Lock() 

        self.apply_styles()
        self.setup_ui()
        self.init_git()
        self.process_log_queue()

    def apply_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        self.style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=CLR_SURFACE, foreground=CLR_TEXT, padding=[20, 8], borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", CLR_ACCENT)], foreground=[("selected", CLR_BG)])
        
        self.style.configure("TFrame", background=CLR_BG)
        self.style.configure("TLabel", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI", 10))
        self.style.configure("TLabelframe", background=CLR_BG, foreground=CLR_ACCENT)
        self.style.configure("TLabelframe.Label", background=CLR_BG, foreground=CLR_ACCENT, font=("Segoe UI Bold", 10))
        
        self.style.configure("Treeview", background=CLR_SURFACE, foreground=CLR_TEXT, fieldbackground=CLR_SURFACE, 
                             rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", background=CLR_SURFACE, foreground=CLR_ACCENT, borderwidth=1, font=("Segoe UI Bold", 9))
        self.style.map("Treeview", background=[('selected', CLR_ACCENT)], foreground=[('selected', CLR_BG)])

        self.style.configure("TButton", padding=6, font=("Segoe UI Bold", 9))
        self.style.configure("Accent.TButton", background=CLR_ACCENT, foreground=CLR_BG)
        self.style.configure("Deploy.TButton", background=CLR_SUCCESS, foreground=CLR_TEXT, font=("Segoe UI Bold", 10))
        self.style.configure("Quick.TButton", background=CLR_QUICK, foreground=CLR_BG, font=("Segoe UI Black", 10))
        self.style.configure("Danger.TButton", background=CLR_DANGER, foreground=CLR_TEXT, font=("Segoe UI Bold", 9))

    def init_git(self):
        try:
            self.git = GitManager(self.config_data.get("LOCAL_DIR", "."))
            log_queue.put(f"✔️ Git Repo aktif: {self.config_data.get('LOCAL_DIR')}")
            if hasattr(self, 'commit_tree'):
                self.load_commits()
        except Exception as e:
            self.git = None
            log_queue.put(f"[INIT] Git Error: {e}")
            if hasattr(self, 'commit_tree'):
                self.commit_tree.delete(*self.commit_tree.get_children())

    def setup_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_deploy = ttk.Frame(self.notebook)
        self.tab_browser = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_deploy, text="  🚀 DEPLOYMENT  ")
        self.notebook.add(self.tab_browser, text="  📂 FILE BROWSER  ")
        self.notebook.add(self.tab_config, text="  ⚙️ CONFIGURATION  ")

        self.setup_deploy_tab()
        self.setup_browser_tab()
        self.setup_config_tab()

    def setup_deploy_tab(self):
        main_paned = ttk.PanedWindow(self.tab_deploy, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_split = ttk.PanedWindow(main_paned, orient=tk.HORIZONTAL)
        main_paned.add(top_split, weight=3)

        # Commit Panel
        commit_frame = ttk.Frame(top_split)
        top_split.add(commit_frame, weight=1)

        cmd_bar = ttk.Frame(commit_frame)
        cmd_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_active_app = ttk.Label(cmd_bar, text=f"GIT ({self.active_profile})", font=("Segoe UI Black", 12), foreground=CLR_ACCENT)
        self.lbl_active_app.pack(side=tk.LEFT)
        
        self.btn_quick_deploy = ttk.Button(cmd_bar, text="⚡ QUICK DEPLOY (LATEST)", command=self.quick_auto_deploy, style="Quick.TButton")
        self.btn_quick_deploy.pack(side=tk.RIGHT, padx=5)

        self.btn_deploy = ttk.Button(cmd_bar, text="🚀 START DEPLOY", command=self.start_deploy, state=tk.DISABLED, style="Deploy.TButton")
        self.btn_deploy.pack(side=tk.RIGHT, padx=5)
        
        self.btn_refresh = ttk.Button(cmd_bar, text="🔄 REFRESH", command=self.load_commits)
        self.btn_refresh.pack(side=tk.RIGHT, padx=5)

        self.commit_tree = ttk.Treeview(commit_frame, columns=("hash", "date", "subject"), show="headings", selectmode="extended")
        self.commit_tree.heading("hash", text="HASH")
        self.commit_tree.heading("date", text="DATE")
        self.commit_tree.heading("subject", text="COMMIT MESSAGE")
        self.commit_tree.column("hash", width=80, anchor="center")
        self.commit_tree.column("date", width=100, anchor="center")
        self.commit_tree.column("subject", width=300)
        self.commit_tree.pack(fill=tk.BOTH, expand=True)
        self.commit_tree.bind("<<TreeviewSelect>>", self.on_commit_select)

        # File Diff Panel
        file_frame = ttk.LabelFrame(top_split, text=" STAGED FOR DEPLOY (MAPPED PATH) ")
        top_split.add(file_frame, weight=1)
        
        self.file_tree = ttk.Treeview(file_frame, columns=("action", "remote"), show="headings")
        self.file_tree.heading("action", text="ACTION")
        self.file_tree.heading("remote", text="REMOTE DESTINATION")
        self.file_tree.column("action", width=80, anchor="center")
        self.file_tree.column("remote", width=400)
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Terminal Console Panel
        console_frame = ttk.LabelFrame(main_paned, text=" DEPLOYMENT CONSOLE ")
        main_paned.add(console_frame, weight=1)
        
        log_bar = ttk.Frame(console_frame)
        log_bar.pack(fill=tk.X, padx=5, pady=(2, 0))
        ttk.Button(log_bar, text="🧹 CLEAR LOG", command=self.clear_logs).pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(console_frame, state='disabled', font=("Consolas", 10), bg="#010409", fg="#3FB950", borderwidth=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def quick_auto_deploy(self):
        if not self.git:
            log_queue.put("❌ Error: Git Manager belum siap.")
            return
        
        log_queue.put("⚡ Menjalankan Quick Deploy (Otomatis)...")
        self.load_commits()
        
        if not self.commits_data:
            log_queue.put("❌ Gagal: Tidak ada history commit.")
            return

        latest_commit = self.commits_data[0]
        latest_hash = latest_commit['hash']
        log_queue.put(f"✅ Mendeteksi Commit Terbaru: {latest_hash[:8]} - {latest_commit['subject']}")

        self.commit_tree.selection_set(latest_hash)
        self.files_to_process = self.git.get_changed_files(latest_hash, latest_hash, self.config_data.get("EXCLUDE_PATTERNS", []))
        
        self.file_tree.delete(*self.file_tree.get_children())
        maps = self.config_data.get("PATH_MAPPINGS", [])
        for f in self.files_to_process['added_modified']:
            self.file_tree.insert("", "end", values=("UPLOAD", resolve_remote_path(f, maps)))
        for f in self.files_to_process['deleted']:
            self.file_tree.insert("", "end", values=("DELETE", resolve_remote_path(f, maps)))

        if self.files_to_process['added_modified'] or self.files_to_process['deleted']:
            log_queue.put("🚀 Melakukan push otomatis ke server...")
            threading.Thread(target=self.worker_deploy, daemon=True).start()
        else:
            log_queue.put("ℹ️ Tidak ada file baru yang perlu di-deploy.")

    def clear_logs(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state='disabled')

    def setup_browser_tab(self):
        paned = ttk.PanedWindow(self.tab_browser, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        lf = ttk.LabelFrame(paned, text=" LOCAL PROJECT ")
        paned.add(lf, weight=1)
        self.local_tree = ttk.Treeview(lf, show="tree")
        self.local_tree.pack(fill=tk.BOTH, expand=True)
        self.local_tree.bind("<<TreeviewOpen>>", self.on_local_expand)

        rf = ttk.LabelFrame(paned, text=" FTP SERVER ")
        paned.add(rf, weight=1)
        btn_rf = ttk.Button(rf, text="🛰️ CONNECT & EXPLORE", command=self.refresh_remote_tree)
        btn_rf.pack(fill=tk.X, padx=5, pady=5)
        self.remote_tree = ttk.Treeview(rf, show="tree")
        self.remote_tree.pack(fill=tk.BOTH, expand=True)
        self.remote_tree.bind("<<TreeviewOpen>>", self.on_remote_expand)
        
        self.after(100, self.refresh_local_root)

    def refresh_local_root(self):
        self.local_tree.delete(*self.local_tree.get_children())
        p = os.path.abspath(self.config_data.get("LOCAL_DIR", "."))
        node = self.local_tree.insert("", "end", text=f" 📂 {os.path.basename(p)}", values=(p, "dir"), open=True)
        self._populate_local_node(node, p)

    def _populate_local_node(self, parent_node, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith('.'): continue
                icon = "📁" if entry.is_dir() else "📄"
                node = self.local_tree.insert(parent_node, "end", text=f" {icon} {entry.name}", 
                                             values=(entry.path, "dir" if entry.is_dir() else "file"))
                if entry.is_dir(): self.local_tree.insert(node, "end", text="loading...")
        except: pass

    def on_local_expand(self, event):
        node = self.local_tree.focus()
        if not node: return
        path, n_type = self.local_tree.item(node, "values")
        if n_type == "dir":
            children = self.local_tree.get_children(node)
            if children and self.local_tree.item(children[0], "text") == "loading...":
                self.local_tree.delete(*children)
                self._populate_local_node(node, path)

    def _ensure_browser_ftp(self):
        with self.ftp_lock:
            try:
                if self.browser_ftp:
                    self.browser_ftp.voidcmd("NOOP")
                    return True
            except:
                pass
            
            try:
                cfg = self.config_data
                self.browser_ftp = ftplib.FTP(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                self.browser_ftp.set_pasv(True)
                return True
            except Exception as e:
                log_queue.put(f"❌ FTP Reconnect Error: {e}")
                return False

    def refresh_remote_tree(self):
        self.remote_tree.delete(*self.remote_tree.get_children())
        root_path = self.config_data.get("REMOTE_DIR", "/")
        if not root_path: root_path = "/"
        
        root_id = self.remote_tree.insert("", "end", text=f" 🌍 {root_path}", values=(root_path, "dir"), open=True)
        self.remote_tree.insert(root_id, "end", text="loading...")
        self._fetch_remote_content(root_id, root_path)

    def _fetch_remote_content(self, parent_node, path):
        def worker():
            try:
                if not self._ensure_browser_ftp():
                    self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))
                    return

                with self.ftp_lock:
                    target_path = "/" + path.strip("/")
                    target_path = target_path.replace("//", "/")
                    log_queue.put(f"📂 Membuka remote folder: {target_path}")
                    
                    items = []
                    try:
                        self.browser_ftp.cwd(target_path)
                        for name, facts in self.browser_ftp.mlsd():
                            if name in [".", ".."]: continue
                            is_dir = facts.get("type") in ["dir", "pdir", "cdir"]
                            items.append((name, is_dir))
                    except Exception:
                        try:
                            lines = []
                            self.browser_ftp.retrlines('LIST', lines.append)
                            for line in lines:
                                if not line: continue
                                parts = line.split()
                                if len(parts) < 9: continue
                                name = " ".join(parts[8:])
                                if name in [".", ".."]: continue
                                is_dir = line.startswith('d') or '<DIR>' in line.upper()
                                items.append((name, is_dir))
                        except Exception as e2:
                            log_queue.put(f"❌ Error LIST FTP: {e2}")

                    items.sort(key=lambda x: (not x[1], x[0].lower()))

                    def fill_ui():
                        self.remote_tree.delete(*self.remote_tree.get_children(parent_node))
                        if not items:
                            self.remote_tree.insert(parent_node, "end", text=" (Kosong/Tanpa Izin)", values=("", "file"))
                            return

                        for name, is_dir in items:
                            icon = "📁" if is_dir else "📄"
                            new_path = (target_path.rstrip("/") + "/" + name).replace("//", "/")
                            node = self.remote_tree.insert(parent_node, "end", text=f" {icon} {name}", 
                                                          values=(new_path, "dir" if is_dir else "file"))
                            if is_dir:
                                self.remote_tree.insert(node, "end", text="loading...")
                        
                        self.remote_tree.item(parent_node, open=True)

                    self.after(0, fill_ui)
            except Exception as e:
                log_queue.put(f"❌ Error listing remote: {e}")
                self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))

        threading.Thread(target=worker, daemon=True).start()

    def on_remote_expand(self, event):
        node = self.remote_tree.focus()
        if not node: return
        vals = self.remote_tree.item(node, "values")
        if not vals or len(vals) < 2: return
        
        path, n_type = vals
        if n_type == "dir":
            children = self.remote_tree.get_children(node)
            if children:
                first_child_text = self.remote_tree.item(children[0], "text").strip()
                if first_child_text == "loading...":
                    self._fetch_remote_content(node, path)

    # ================= CONFIGURATION & MULTI-PROFILE UI =================

    def setup_config_tab(self):
        container = ttk.Frame(self.tab_config, padding=25)
        container.pack(fill=tk.BOTH, expand=True)

        # --- PROFILE SELECTION HEADER ---
        profile_frame = ttk.LabelFrame(container, text=" 🎛️ CONFIGURATION PRESETS / PROFILES ", padding=12)
        profile_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(profile_frame, text="Active Profile:", font=("Segoe UI Bold", 10)).pack(side=tk.LEFT, padx=(5, 10))
        
        self.profile_var = tk.StringVar(value=self.active_profile)
        self.profile_combo = ttk.Combobox(profile_frame, textvariable=self.profile_var, state="readonly", font=("Segoe UI Bold", 10), width=30)
        self.profile_combo['values'] = list(self.config_store["profiles"].keys())
        self.profile_combo.pack(side=tk.LEFT, padx=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)

        ttk.Button(profile_frame, text="➕ NEW PROFILE", command=self.add_profile, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(profile_frame, text="🗑️ DELETE PROFILE", command=self.delete_profile).pack(side=tk.LEFT, padx=5)

        # --- CONFIG FIELDS ---
        grid = ttk.Frame(container)
        grid.pack(fill=tk.X)
        
        flds = [
            ("FTP HOST:", "FTP_HOST"), ("FTP USER:", "FTP_USER"), ("FTP PASS:", "FTP_PASS"),
            ("LOCAL PROJECT ROOT:", "LOCAL_DIR"), ("REMOTE TARGET ROOT:", "REMOTE_DIR")
        ]

        self.cfg_ents = {}
        for i, (lbl, key) in enumerate(flds):
            ttk.Label(grid, text=lbl, font=("Segoe UI Bold", 9), foreground=CLR_TEXT_DIM).grid(row=i, column=0, sticky="w", pady=6)
            e = ttk.Entry(grid, font=("Segoe UI", 10))
            if "PASS" in lbl: e.config(show="*")
            e.insert(0, self.config_data.get(key, ""))
            e.grid(row=i, column=1, sticky="ew", padx=15)
            self.cfg_ents[key] = e
        grid.columnconfigure(1, weight=1)

        # --- MAPPING ---
        m_frame = ttk.LabelFrame(container, text=" PATH MAPPING LOGIC ", padding=12)
        m_frame.pack(fill=tk.BOTH, expand=True, pady=15)
        
        self.map_tree = ttk.Treeview(m_frame, columns=("l", "r"), show="headings", height=4)
        self.map_tree.heading("l", text="LOCAL PREFIX")
        self.map_tree.heading("r", text="REMOTE TARGET")
        self.map_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn_m = ttk.Frame(m_frame)
        btn_m.pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_m, text="➕ ADD", command=self.add_mapping).pack(fill=tk.X, pady=2)
        ttk.Button(btn_m, text="❌ DEL", command=self.del_mapping).pack(fill=tk.X, pady=2)

        for m in self.config_data.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m['local'], m['remote']))

        ttk.Button(container, text="💾 SAVE CURRENT CONFIGURATION", command=self.save_config_ui, style="Accent.TButton").pack(fill=tk.X, ipady=8)

    def populate_form_from_config(self, cfg):
        """Mengisi nilai widget konfigurasi sesuai profile yang dipilih."""
        for key, entry in self.cfg_ents.items():
            entry.delete(0, tk.END)
            entry.insert(0, cfg.get(key, ""))
            
        self.map_tree.delete(*self.map_tree.get_children())
        for m in cfg.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m.get('local', ''), m.get('remote', '')))

    def on_profile_change(self, event=None):
        selected_name = self.profile_var.get()
        if selected_name not in self.config_store["profiles"]:
            return

        self.active_profile = selected_name
        self.config_store["active_profile"] = selected_name
        self.config_data = self.config_store["profiles"][selected_name]

        # Isi form UI dengan data profil baru
        self.populate_form_from_config(self.config_data)

        # Update label UI
        self.lbl_active_app.config(text=f"GIT ({self.active_profile})")

        # Re-inisialisasi Git & Local Tree sesuai LOCAL_DIR profil yang baru
        self.init_git()
        self.refresh_local_root()

        # Tutup koneksi browser FTP sebelumnya agar reconnect ke server baru
        if self.browser_ftp:
            try: self.browser_ftp.quit()
            except: pass
            self.browser_ftp = None

        save_config_store(self.config_store)
        log_queue.put(f"🔀 Berpindah ke profile: '{self.active_profile}'")

    def add_profile(self):
        new_name = simpledialog.askstring("New Profile", "Masukkan Nama Profil Aplikasi Baru:\n(Contoh: primaginary hr)", parent=self)
        if not new_name: return
        new_name = new_name.strip()
        
        if new_name in self.config_store["profiles"]:
            messagebox.showerror("Error", f"Profil dengan nama '{new_name}' sudah ada!")
            return

        # Clone konfigurasi yang sedang aktif sebagai basis profil baru
        current_active = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG).copy()
        self.config_store["profiles"][new_name] = current_active
        self.config_store["active_profile"] = new_name

        # Update combo box list & switch ke profil baru
        profiles_list = list(self.config_store["profiles"].keys())
        self.profile_combo['values'] = profiles_list
        self.profile_var.set(new_name)
        
        self.on_profile_change()
        messagebox.showinfo("Success", f"Profil '{new_name}' berhasil dibuat dan diaktifkan!")

    def delete_profile(self):
        profiles = self.config_store["profiles"]
        if len(profiles) <= 1:
            messagebox.showwarning("Warning", "Minimal harus ada 1 profil tersisa.")
            return

        if messagebox.askyesno("Confirm Delete", f"Hapus profil '{self.active_profile}'?"):
            deleted_name = self.active_profile
            del profiles[deleted_name]
            
            # Switch ke profil pertama yang tersisa
            new_active = list(profiles.keys())[0]
            self.active_profile = new_active
            self.config_store["active_profile"] = new_active
            
            self.profile_combo['values'] = list(profiles.keys())
            self.profile_var.set(new_active)
            self.on_profile_change()
            messagebox.showinfo("Deleted", f"Profil '{deleted_name}' berhasil dihapus.")

    def add_mapping(self):
        w = tk.Toplevel(self, bg=CLR_BG)
        w.title("Add Mapping")
        ttk.Label(w, text="Local Prefix:").pack(pady=5)
        e1 = ttk.Entry(w); e1.pack(padx=20)
        ttk.Label(w, text="Remote Target:").pack(pady=5)
        e2 = ttk.Entry(w); e2.pack(padx=20)
        def _sv():
            self.map_tree.insert("", "end", values=(e1.get(), e2.get()))
            w.destroy()
        ttk.Button(w, text="OK", command=_sv).pack(pady=15)

    def del_mapping(self):
        for s in self.map_tree.selection(): 
            self.map_tree.delete(s)

    def save_config_ui(self):
        maps = []
        for i in self.map_tree.get_children():
            v = self.map_tree.item(i)["values"]
            maps.append({"local": str(v[0]), "remote": str(v[1])})
        
        updated_cfg = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy())
        for k, e in self.cfg_ents.items():
            updated_cfg[k] = e.get()
        updated_cfg["PATH_MAPPINGS"] = maps

        self.config_store["profiles"][self.active_profile] = updated_cfg
        self.config_data = updated_cfg

        if save_config_store(self.config_store):
            messagebox.showinfo("Success", f"Konfigurasi '{self.active_profile}' berhasil disimpan.")
            self.init_git()
            self.load_commits()

    def load_commits(self):
        if not self.git: return
        self.commit_tree.delete(*self.commit_tree.get_children())
        self.commits_data = self.git.get_recent_commits()
        for c in self.commits_data:
            self.commit_tree.insert("", "end", iid=c['hash'], values=(c['hash'][:8], c['date'], c['subject']))

    def on_commit_select(self, event):
        sel = self.commit_tree.selection()
        if not sel: return

        focused = self.commit_tree.focus()
        if focused:
            vals = self.commit_tree.item(focused, "values")
            if vals:
                copy_text = f"{vals[0]} | {vals[1]} | {vals[2]}"
                self.clipboard_clear()
                self.clipboard_append(copy_text)
                self.update()
                log_queue.put(f"📋 Info dicopy ke clipboard: {vals[0]}")

        start, end = sel[-1], sel[0]
        self.files_to_process = self.git.get_changed_files(start, end, self.config_data.get("EXCLUDE_PATTERNS", []))
        
        self.file_tree.delete(*self.file_tree.get_children())
        maps = self.config_data.get("PATH_MAPPINGS", [])
        for f in self.files_to_process['added_modified']:
            self.file_tree.insert("", "end", values=("UPLOAD", resolve_remote_path(f, maps)))
        for f in self.files_to_process['deleted']:
            self.file_tree.insert("", "end", values=("DELETE", resolve_remote_path(f, maps)))

        self.btn_deploy.config(state=tk.NORMAL if (self.files_to_process['added_modified'] or self.files_to_process['deleted']) else tk.DISABLED)

    def start_deploy(self):
        if messagebox.askyesno("Confirm", f"Deploy selected commits to server ({self.active_profile})?"):
            self.btn_deploy.config(state=tk.DISABLED)
            threading.Thread(target=self.worker_deploy, daemon=True).start()

    def worker_deploy(self):
        deployer = FTPDeployer(self.config_data)
        deployer.deploy(self.files_to_process)
        self.after(0, lambda: self.btn_deploy.config(state=tk.NORMAL))

    def process_log_queue(self):
        try:
            while True:
                msg = log_queue.get_nowait()
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except: pass
        self.after(100, self.process_log_queue)

if __name__ == "__main__":
    app = App()
    app.mainloop()