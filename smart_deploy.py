#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ftplib
import os
import sys
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
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

# ================= UTILS & LOGIC =================

log_queue = Queue()

def load_config():
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    if config_path.is_file():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                merged["EXCLUDE_PATTERNS"] = [l for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()]
            if merged.get("PATH_MAPPINGS") is None:
                merged["PATH_MAPPINGS"] = []
            return merged
        except Exception as e:
            log_queue.put(f"[CONFIG] Gagal memuat {config_path}: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(config_dict):
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        log_queue.put(f"[CONFIG] Disimpan ke {config_path}")
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
        self._log(f"⬆️ UP: {local_rel_path} -> {final_remote_path}")
        try:
            self.ensure_remote_dir(final_remote_path)
            with open(local_abs, 'rb') as f:
                self.ftp.storbinary(f'STOR {final_remote_path}', f)
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
        self.title("Smart Git-FTP Deployer V2.0 (Tree & Mapping Support)")
        self.geometry("1200x850")
        self.configure(bg=CLR_BG)
        
        self.config_data = load_config()
        self.git = None
        self.init_git()
        self.commits_data = []
        self.files_to_process = {'added_modified': [], 'deleted': []}

        self.apply_styles()
        self.setup_ui()
        self.process_log_queue()
        self.ftp_lock = threading.Lock() 

    def apply_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        # Notebook Styling
        self.style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=CLR_SURFACE, foreground=CLR_TEXT, padding=[20, 8], borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", CLR_ACCENT)], foreground=[("selected", CLR_BG)])
        
        # General Styles
        self.style.configure("TFrame", background=CLR_BG)
        self.style.configure("TLabel", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI", 10))
        
        # Treeview Styling (Modern Cyber)
        self.style.configure("Treeview", background=CLR_SURFACE, foreground=CLR_TEXT, fieldbackground=CLR_SURFACE, 
                             rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", background=CLR_SURFACE, foreground=CLR_ACCENT, borderwidth=1, font=("Segoe UI Bold", 9))
        self.style.map("Treeview", background=[('selected', CLR_ACCENT)], foreground=[('selected', CLR_BG)])

        # Button Styles
        self.style.configure("TButton", padding=6, font=("Segoe UI Bold", 9))
        self.style.configure("Accent.TButton", background=CLR_ACCENT, foreground=CLR_BG)
        self.style.configure("Deploy.TButton", background=CLR_SUCCESS, foreground=CLR_TEXT, font=("Segoe UI Bold", 10))

    def init_git(self):
        try: self.git = GitManager(self.config_data["LOCAL_DIR"])
        except Exception as e:
            self.git = None
            log_queue.put(f"[INIT] Git Error: {e}")

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
        # Master Vertical Split
        main_paned = ttk.PanedWindow(self.tab_deploy, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # TOP: Commit & File Diff Area (Horizontal Split)
        top_split = ttk.PanedWindow(main_paned, orient=tk.HORIZONTAL)
        main_paned.add(top_split, weight=3)

        # --- LEFT: Git Commits Panel (MODERNIZED) ---
        commit_frame = ttk.Frame(top_split)
        top_split.add(commit_frame, weight=1)

        # Command Bar (Refresh & Deploy Dekat Sesuai Request)
        cmd_bar = ttk.Frame(commit_frame)
        cmd_bar.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(cmd_bar, text="GIT HISTORY", font=("Segoe UI Black", 12), foreground=CLR_ACCENT).pack(side=tk.LEFT)
        
        self.btn_deploy = ttk.Button(cmd_bar, text="🚀 START DEPLOY", command=self.start_deploy, state=tk.DISABLED, style="Deploy.TButton")
        self.btn_deploy.pack(side=tk.RIGHT, padx=5)
        
        self.btn_refresh = ttk.Button(cmd_bar, text="🔄 REFRESH", command=self.load_commits)
        self.btn_refresh.pack(side=tk.RIGHT, padx=5)

        # Commit Treeview
        self.commit_tree = ttk.Treeview(commit_frame, columns=("hash", "date", "subject"), show="headings", selectmode="extended")
        self.commit_tree.heading("hash", text="HASH")
        self.commit_tree.heading("date", text="DATE")
        self.commit_tree.heading("subject", text="COMMIT MESSAGE")
        self.commit_tree.column("hash", width=80, anchor="center")
        self.commit_tree.column("date", width=100, anchor="center")
        self.commit_tree.column("subject", width=300)
        self.commit_tree.pack(fill=tk.BOTH, expand=True)
        self.commit_tree.bind("<<TreeviewSelect>>", self.on_commit_select)

        # --- RIGHT: File Diff List ---
        file_frame = ttk.LabelFrame(top_split, text=" STAGED FOR DEPLOY (MAPPED PATH) ")
        top_split.add(file_frame, weight=1)
        
        self.file_tree = ttk.Treeview(file_frame, columns=("action", "remote"), show="headings")
        self.file_tree.heading("action", text="ACTION")
        self.file_tree.heading("remote", text="REMOTE DESTINATION")
        self.file_tree.column("action", width=80, anchor="center")
        self.file_tree.column("remote", width=400)
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # BOTTOM: Terminal Console
        console_frame = ttk.LabelFrame(main_paned, text=" DEPLOYMENT CONSOLE ")
        main_paned.add(console_frame, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(console_frame, state='disabled', font=("Consolas", 10), bg="#010409", fg="#3FB950", borderwidth=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        if self.git: self.load_commits()

    def setup_browser_tab(self):
        paned = ttk.PanedWindow(self.tab_browser, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- LOCAL PROJECT ---
        lf = ttk.LabelFrame(paned, text=" LOCAL PROJECT ")
        paned.add(lf, weight=1)
        self.local_tree = ttk.Treeview(lf, show="tree")
        self.local_tree.pack(fill=tk.BOTH, expand=True)
        self.local_tree.bind("<<TreeviewOpen>>", self.on_local_expand)

        # --- FTP SERVER ---
        rf = ttk.LabelFrame(paned, text=" FTP SERVER ")
        paned.add(rf, weight=1)
        btn_rf = ttk.Button(rf, text="🛰️ CONNECT & EXPLORE", command=self.refresh_remote_tree)
        btn_rf.pack(fill=tk.X, padx=5, pady=5)
        self.remote_tree = ttk.Treeview(rf, show="tree")
        self.remote_tree.pack(fill=tk.BOTH, expand=True)
        self.remote_tree.bind("<<TreeviewOpen>>", self.on_remote_expand)
        
        self.after(100, self.refresh_local_root)
        self.browser_ftp = None

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

    def refresh_remote_tree(self):
        threading.Thread(target=self._worker_list_ftp_root, daemon=True).start()

    def _worker_list_ftp_root(self):
        try:
            cfg = self.config_data
            if self.browser_ftp:
                try: self.browser_ftp.quit()
                except: pass
            
            log_queue.put(f"DEBUG: Menghubungkan ke {cfg['FTP_HOST']}...")
            self.browser_ftp = ftplib.FTP(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
            self.browser_ftp.set_pasv(True)
            
            root_path = cfg["REMOTE_DIR"] if cfg["REMOTE_DIR"] else "/"
            log_queue.put(f"DEBUG: Berhasil Login. Lokasi root: {root_path}")
            
            def update_ui():
                self.remote_tree.delete(*self.remote_tree.get_children())
                root_id = self.remote_tree.insert("", "end", text=f" 🌍 {root_path}", values=(root_path, "dir"), open=True)
                self.remote_tree.insert(root_id, "end", text="loading...")
                # Langsung fetch isi root
                self._fetch_remote_content(root_id, root_path)
            self.after(0, update_ui)
        except Exception as e:
            log_queue.put(f"❌ FTP BROWSER ERROR: {str(e)}")

    def _ensure_browser_ftp(self):
        """Memastikan koneksi FTP browser tetap aktif."""
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
        """Memulai ulang tree dari root remote."""
        self.remote_tree.delete(*self.remote_tree.get_children())
        root_path = self.config_data.get("REMOTE_DIR", "/")
        if not root_path: root_path = "/"
        
        # Buat root node
        root_id = self.remote_tree.insert("", "end", text=f" 🌍 {root_path}", 
                                         values=(root_path, "dir"), open=True)
        self.remote_tree.insert(root_id, "end", text="loading...")
        
        # Jalankan worker
        threading.Thread(target=self._fetch_remote_content, args=(root_id, root_path), daemon=True).start()

    def _fetch_remote_content(self, parent_node, path):
        """Worker thread untuk mengambil isi folder FTP."""
        if not self._ensure_browser_ftp():
            self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))
            return

        with self.ftp_lock:
            try:
                items = []
                # Pastikan path diawali dengan /
                target_path = path if path.startswith('/') else '/' + path
                
                log_queue.put(f"🔍 Fetching: {target_path}")
                
                try:
                    # Gunakan MLSD (lebih modern & akurat)
                    for name, facts in self.browser_ftp.mlsd(target_path):
                        if name in [".", ".."]: continue
                        items.append((name, facts.get("type") == "dir"))
                except:
                    # Fallback ke NLST/LIST jika MLSD tidak didukung
                    self.browser_ftp.cwd(target_path)
                    lines = []
                    self.browser_ftp.retrlines('LIST', lines.append)
                    for line in lines:
                        parts = line.split()
                        if not parts: continue
                        name = parts[-1]
                        if name in [".", ".."]: continue
                        # Deteksi folder berdasarkan flag 'd' di awal string LIST
                        is_dir = line.lower().startswith('d') or '<dir>' in line.lower()
                        items.append((name, is_dir))

                # Sort: Folder dulu, baru file
                items.sort(key=lambda x: (not x[1], x[0].lower()))

                def update_ui():
                    # Hapus loading dummy
                    self.remote_tree.delete(*self.remote_tree.get_children(parent_node))
                    if not items:
                        self.remote_tree.insert(parent_node, "end", text=" (Kosong)", values=("", "file"))
                        return
                        
                    for name, is_dir in items:
                        icon = "📁" if is_dir else "📄"
                        # Gabungkan path dengan benar
                        full_p = os.path.join(path, name).replace('\\', '/')
                        node = self.remote_tree.insert(parent_node, "end", text=f" {icon} {name}", 
                                                      values=(full_p, "dir" if is_dir else "file"))
                        if is_dir:
                            self.remote_tree.insert(node, "end", text="loading...")
                
                self.after(0, update_ui)

            except Exception as e:
                log_queue.put(f"❌ Error listing {path}: {e}")
                self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))

    def _fetch_remote_content(self, parent_node, path):
        """Worker thread yang jauh lebih stabil untuk mengambil isi folder FTP."""
        def worker():
            try:
                # 1. Pastikan koneksi siap
                if not self._ensure_browser_ftp():
                    return

                with self.ftp_lock:
                    # Normalisasi path: hapus double slash dan pastikan diawali /
                    target_path = "/" + path.strip("/")
                    target_path = target_path.replace("//", "/")
                    
                    log_queue.put(f"📂 Membuka folder: {target_path}")
                    
                    items = []
                    
                    # 2. Coba cara modern (MLSD)
                    try:
                        # Kita pindah folder dulu untuk memastikan server 'sadar' posisi
                        self.browser_ftp.cwd(target_path)
                        for name, facts in self.browser_ftp.mlsd():
                            if name in [".", ".."]: continue
                            is_dir = facts.get("type") in ["dir", "pdir", "cdir"]
                            items.append((name, is_dir))
                    except Exception as e:
                        log_queue.put(f"⚠️ MLSD Gagal, mencoba LIST standar...")
                        # 3. Fallback ke LIST standar jika MLSD dilarang/gagal
                        try:
                            lines = []
                            self.browser_ftp.retrlines('LIST', lines.append)
                            for line in lines:
                                if not line: continue
                                parts = line.split()
                                if len(parts) < 9: continue
                                name = " ".join(parts[8:]) # Ambil nama file (bisa mengandung spasi)
                                if name in [".", ".."]: continue
                                is_dir = line.startswith('d') or '<DIR>' in line.upper()
                                items.append((name, is_dir))
                        except Exception as e2:
                            log_queue.put(f"❌ Semua metode gagal: {e2}")

                    # Urutkan: Folder dulu, baru file
                    items.sort(key=lambda x: (not x[1], x[0].lower()))

                    def fill_ui():
                        # Hapus "loading..."
                        self.remote_tree.delete(*self.remote_tree.get_children(parent_node))
                        
                        if not items:
                            # Jika benar-benar kosong, beri tanda agar user tidak bingung
                            self.remote_tree.insert(parent_node, "end", text=" (Kosong/Tanpa Izin)", values=("", "file"))
                            return

                        for name, is_dir in items:
                            icon = "📁" if is_dir else "📄"
                            # Gabung path dengan rapi
                            new_path = (target_path.rstrip("/") + "/" + name).replace("//", "/")
                            
                            node = self.remote_tree.insert(parent_node, "end", 
                                                          text=f" {icon} {name}", 
                                                          values=(new_path, "dir" if is_dir else "file"))
                            if is_dir:
                                # Tambahkan dummy loading lagi untuk anak folder
                                self.remote_tree.insert(node, "end", text="loading...")
                        
                        # Buka folder tersebut agar terlihat isinya
                        self.remote_tree.item(parent_node, open=True)
                        log_queue.put(f"✅ Berhasil memuat {len(items)} item di {target_path}")

                    self.after(0, fill_ui)

            except Exception as e:
                log_queue.put(f"❌ Error fatal saat fetch: {str(e)}")
                self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))

        threading.Thread(target=worker, daemon=True).start()

    def on_remote_expand(self, event):
        """Trigger saat user klik tanda [+] di sebelah folder."""
        node = self.remote_tree.focus()
        if not node: return
        
        vals = self.remote_tree.item(node, "values")
        if not vals or len(vals) < 2: return
        
        path, n_type = vals
        if n_type == "dir":
            children = self.remote_tree.get_children(node)
            # Cek apakah anak pertamanya tulisan "loading..."
            if children:
                first_child_text = self.remote_tree.item(children[0], "text").strip()
                if first_child_text == "loading...":
                    # Panggil fungsi fetch untuk mengganti "loading..." dengan isi asli
                    self._fetch_remote_content(node, path)




    def setup_config_tab(self):
        container = ttk.Frame(self.tab_config, padding=30)
        container.pack(fill=tk.BOTH, expand=True)

        grid = ttk.Frame(container)
        grid.pack(fill=tk.X)
        
        flds = [
            ("FTP HOST:", "FTP_HOST"), ("FTP USER:", "FTP_USER"), ("FTP PASS:", "FTP_PASS"),
            ("LOCAL PROJECT ROOT:", "LOCAL_DIR"), ("REMOTE TARGET ROOT:", "REMOTE_DIR")
        ]

        self.cfg_ents = {}
        for i, (lbl, key) in enumerate(flds):
            ttk.Label(grid, text=lbl, font=("Segoe UI Bold", 9), foreground=CLR_TEXT_DIM).grid(row=i, column=0, sticky="w", pady=8)
            e = ttk.Entry(grid, font=("Segoe UI", 11))
            if "PASS" in lbl: e.config(show="*")
            e.insert(0, self.config_data.get(key, ""))
            e.grid(row=i, column=1, sticky="ew", padx=15)
            self.cfg_ents[key] = e
        grid.columnconfigure(1, weight=1)

        # MAPPING
        m_frame = ttk.LabelFrame(container, text=" PATH MAPPING LOGIC ", padding=15)
        m_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.map_tree = ttk.Treeview(m_frame, columns=("l", "r"), show="headings", height=5)
        self.map_tree.heading("l", text="LOCAL PREFIX")
        self.map_tree.heading("r", text="REMOTE TARGET")
        self.map_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn_m = ttk.Frame(m_frame)
        btn_m.pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_m, text="➕ ADD", command=self.add_mapping).pack(fill=tk.X, pady=2)
        ttk.Button(btn_m, text="❌ DEL", command=self.del_mapping).pack(fill=tk.X, pady=2)

        for m in self.config_data.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m['local'], m['remote']))

        ttk.Button(container, text="💾 SAVE ALL CONFIGURATIONS", command=self.save_config_ui, style="Accent.TButton").pack(fill=tk.X, ipady=10)

    def add_mapping(self):
        w = tk.Toplevel(self, bg=CLR_BG); w.title("Add Mapping")
        ttk.Label(w, text="Local Prefix:").pack(pady=5)
        e1 = ttk.Entry(w); e1.pack(padx=20)
        ttk.Label(w, text="Remote Target:").pack(pady=5)
        e2 = ttk.Entry(w); e2.pack(padx=20)
        def _sv(): self.map_tree.insert("", "end", values=(e1.get(), e2.get())); w.destroy()
        ttk.Button(w, text="OK", command=_sv).pack(pady=15)

    def del_mapping(self):
        for s in self.map_tree.selection(): self.map_tree.delete(s)

    def save_config_ui(self):
        maps = []
        for i in self.map_tree.get_children():
            v = self.map_tree.item(i)["values"]
            maps.append({"local": str(v[0]), "remote": str(v[1])})
        for k, e in self.cfg_ents.items(): self.config_data[k] = e.get()
        self.config_data["PATH_MAPPINGS"] = maps
        if save_config(self.config_data):
            messagebox.showinfo("Success", "Configuration Secured.")
            self.init_git(); self.load_commits()

    def load_commits(self):
        if not self.git: return
        self.commit_tree.delete(*self.commit_tree.get_children())
        self.commits_data = self.git.get_recent_commits()
        for c in self.commits_data:
            self.commit_tree.insert("", "end", iid=c['hash'], values=(c['hash'][:8], c['date'], c['subject']))

    def on_commit_select(self, event):
        sel = self.commit_tree.selection()
        if not sel: return
        # Range: oldest selected to newest selected
        start, end = sel[-1], sel[0]
        self.files_to_process = self.git.get_changed_files(start, end, self.config_data["EXCLUDE_PATTERNS"])
        
        self.file_tree.delete(*self.file_tree.get_children())
        maps = self.config_data.get("PATH_MAPPINGS", [])
        for f in self.files_to_process['added_modified']:
            self.file_tree.insert("", "end", values=("UPLOAD", resolve_remote_path(f, maps)))
        for f in self.files_to_process['deleted']:
            self.file_tree.insert("", "end", values=("DELETE", resolve_remote_path(f, maps)))

        self.btn_deploy.config(state=tk.NORMAL if (self.files_to_process['added_modified'] or self.files_to_process['deleted']) else tk.DISABLED)

    def start_deploy(self):
        if messagebox.askyesno("Confirm", "Deploy selected commits to server?"):
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