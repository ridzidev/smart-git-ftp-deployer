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

# ================= KONFIGURASI & WARNA =================

CONFIG_FILENAME = "deploy_config.json"
APP_VERSION = "2.2"

DEFAULT_CONFIG = {
    "FTP_HOST": "",
    "FTP_USER": "",
    "FTP_PASS": "",
    "FTP_TLS": False,
    "LOCAL_DIR": ".",
    "REMOTE_DIR": "/",
    "EXCLUDE_PATTERNS": [
        "*.git*", ".env", "node_modules", "vendor", ".idea", ".vscode", "deploy_config.json"
    ],
    "PATH_MAPPINGS": []
}

# Palet warna netral gelap
CLR_BG = "#0D1117"
CLR_SURFACE = "#161B22"
CLR_SURFACE_ALT = "#21262D"
CLR_BORDER = "#30363D"
CLR_PRIMARY = "#2563EB"
CLR_PRIMARY_HOVER = "#1D4ED8"
CLR_SUCCESS = "#10B981"
CLR_DANGER = "#EF4444"
CLR_WARNING = "#F59E0B"
CLR_TEXT = "#E6EDF3"
CLR_TEXT_MUTED = "#8B949E"
CLR_CONSOLE_BG = "#030712"
CLR_CONSOLE_TEXT = "#CBD5E1"

# ================= PENGELOLA KONFIGURASI =================

log_queue = Queue()

def load_config_store():
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
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "profiles" in data and isinstance(data["profiles"], dict) and data["profiles"]:
                for p_name, p_cfg in data["profiles"].items():
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(p_cfg)
                    if not merged.get("EXCLUDE_PATTERNS"):
                        merged["EXCLUDE_PATTERNS"] = list(DEFAULT_CONFIG["EXCLUDE_PATTERNS"])
                    if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                        merged["EXCLUDE_PATTERNS"] = [
                            l.strip() for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()
                        ]
                    if merged.get("PATH_MAPPINGS") is None:
                        merged["PATH_MAPPINGS"] = []
                    data["profiles"][p_name] = merged

                if data.get("active_profile") not in data["profiles"]:
                    data["active_profile"] = list(data["profiles"].keys())[0]
                return data
            else:
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                if not merged.get("EXCLUDE_PATTERNS"):
                    merged["EXCLUDE_PATTERNS"] = list(DEFAULT_CONFIG["EXCLUDE_PATTERNS"])
                if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                    merged["EXCLUDE_PATTERNS"] = [
                        l.strip() for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()
                    ]
                if merged.get("PATH_MAPPINGS") is None:
                    merged["PATH_MAPPINGS"] = []
                return {
                    "active_profile": "Default",
                    "profiles": {"Default": merged}
                }
        except Exception as e:
            log_queue.put(f"[CONFIG] Gagal memuat berkas konfigurasi: {e}")
            return default_store
    return default_store

def save_config_store(store_dict):
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(store_dict, f, indent=2, ensure_ascii=False)
        os.chmod(config_path, 0o600)  # Lindungi kredensial dari akses user lain
        log_queue.put(f"[CONFIG] Konfigurasi disimpan ke {config_path}")
        return True
    except Exception as e:
        log_queue.put(f"[CONFIG] Gagal menyimpan konfigurasi: {e}")
        return False

def should_exclude(file_path, exclude_patterns):
    path_str = Path(file_path).as_posix()
    for pattern in exclude_patterns:
        if not pattern:
            continue
        if path_str.startswith(pattern) or f"/{pattern}" in path_str:
            return True
    return False

def resolve_remote_path(local_rel_path, mappings):
    posix_path = Path(local_rel_path).as_posix()
    for mapping in mappings:
        local_prefix = mapping.get("local", "").strip()
        remote_prefix = mapping.get("remote", "").strip()
        if not local_prefix:
            continue
        if not local_prefix.endswith("/"):
            local_prefix += "/"
        if posix_path.startswith(local_prefix):
            stripped = posix_path[len(local_prefix):]
            final_path = str(Path(remote_prefix) / stripped)
            return Path(final_path).as_posix()
    return posix_path

# ================= GIT MANAGER =================

class GitManager:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").is_dir():
            raise FileNotFoundError(f"Direktori .git tidak ditemukan pada '{self.repo_path}'.")

    def get_total_commit_count(self):
        command = ["git", "rev-list", "--count", "HEAD"]
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding="utf-8")
            return int(result.stdout.strip())
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Gagal menghitung komit: {e}")
            return 0

    def get_all_commits_chronological(self):
        """Mengambil seluruh komit dari awal (#1) hingga terkini (#N)."""
        command = ["git", "log", "--reverse", "--pretty=format:%H|%an|%ad|%s", "--date=format:%Y-%m-%d %H:%M:%S"]
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding="utf-8")
            commits = []
            idx = 1
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "index": idx,
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "subject": parts[3]
                    })
                    idx += 1
            return commits
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Gagal membaca riwayat kronologis: {e}")
            return []

    def get_changed_files(self, older_hash, newer_hash, exclude_patterns):
        if older_hash == newer_hash:
            command = ["git", "show", "--pretty=", "--name-status", newer_hash]
        else:
            parent_check = subprocess.run(
                ["git", "rev-parse", "--verify", f"{older_hash}^"],
                cwd=self.repo_path, capture_output=True, text=True
            )
            if parent_check.returncode == 0:
                base_ref = f"{older_hash}^"
            else:
                base_ref = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            command = ["git", "diff", "--name-status", base_ref, newer_hash]

        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, encoding="utf-8")
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Diff gagal: {e}")
            return {"added_modified": [], "deleted": []}

        files = {"added_modified": [], "deleted": []}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0][0].upper()
            file_path_str = parts[-1]
            if should_exclude(file_path_str, exclude_patterns):
                continue
            if status in ["A", "M", "C", "R"]:
                files["added_modified"].append(file_path_str)
            elif status == "D":
                files["deleted"].append(file_path_str)
        return files

# ================= FTP ENGINE =================

class FTPDeployer:
    def __init__(self, config, abort_event=None):
        self.host = config["FTP_HOST"]
        self.user = config["FTP_USER"]
        self.password = config["FTP_PASS"]
        self.tls = bool(config.get("FTP_TLS", False))
        self.local_dir = Path(config["LOCAL_DIR"]).resolve()
        self.remote_dir_base = config["REMOTE_DIR"]
        self.mappings = config.get("PATH_MAPPINGS", [])
        self.abort_event = abort_event or threading.Event()
        self.ftp = None

    def _log(self, message):
        log_queue.put(message)

    def connect(self):
        try:
            proto = "FTPS (TLS)" if self.tls else "FTP"
            self._log(f"[INFO] Menghubungkan ke {self.host} ({proto})...")
            if self.tls:
                self.ftp = ftplib.FTP_TLS(self.host, timeout=30)
                self.ftp.login(self.user, self.password)
                self.ftp.prot_p()
            else:
                self.ftp = ftplib.FTP(self.host, timeout=30)
                self.ftp.login(self.user, self.password)
            self.ftp.set_pasv(True)
            self._log("[OK] Terhubung (Passive Mode).")
            try:
                self.ftp.cwd(self.remote_dir_base)
            except Exception:
                self._log(f"[WARN] Direktori {self.remote_dir_base} tidak ditemukan, tetap di root.")
            return True
        except Exception as e:
            self._log(f"[ERROR] Koneksi FTP gagal: {e}")
            return False

    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                pass
            self.ftp = None

    def ensure_remote_dir(self, remote_file_path):
        parent_dir = Path(remote_file_path).parent.as_posix()
        if parent_dir in [".", "/", ""]:
            return
        parts = parent_dir.split("/")
        current = ""
        for part in parts:
            if not part:
                continue
            current += "/" + part
            try:
                self.ftp.mkd(current)
            except Exception:
                pass

    def upload_file(self, local_rel_path):
        if self.abort_event.is_set():
            return False

        local_abs = self.local_dir / local_rel_path
        if not local_abs.is_file():
            self._log(f"[WARN] Berkas lokal tidak ditemukan: {local_rel_path}")
            return False

        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        filesize = os.path.getsize(local_abs)
        uploaded_bytes = 0
        last_percent = -1

        def chunk_callback(data):
            nonlocal uploaded_bytes, last_percent
            if self.abort_event.is_set():
                raise InterruptedError("Dibatalkan pengguna.")
            uploaded_bytes += len(data)
            percent = int((uploaded_bytes / filesize) * 100) if filesize > 0 else 100
            if percent % 25 == 0 and percent != last_percent:
                self._log(f"[PROGRESS] {percent}%: {local_rel_path}")
                last_percent = percent

        self._log(f"[UPLOAD] Mengunggah: {local_rel_path} ({filesize / 1024 / 1024:.2f} MB)")
        try:
            self.ensure_remote_dir(final_remote_path)
            with open(local_abs, "rb") as f:
                self.ftp.storbinary(f"STOR {final_remote_path}", f, callback=chunk_callback)
            return True
        except InterruptedError:
            self._log(f"[WARN] Unggah berkas dibatalkan: {local_rel_path}")
            return False
        except Exception as e:
            self._log(f"[ERROR] Gagal mengunggah {final_remote_path}: {e}")
            return False

    def delete_file(self, local_rel_path):
        if self.abort_event.is_set():
            return False
        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        self._log(f"[DELETE] Menghapus: {final_remote_path}")
        try:
            self.ftp.delete(final_remote_path)
            return True
        except Exception as e:
            self._log(f"[WARN] Gagal menghapus {final_remote_path}: {e}")
            return False

# ================= ANTARMUKA GRAFIS (GUI) =================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Smart Git-FTP Deployer v{APP_VERSION}")
        self.geometry("1340x920")
        self.minsize(1080, 720)
        self.configure(bg=CLR_BG)

        self.config_store = load_config_store()
        self.active_profile = self.config_store.get("active_profile", "Default")
        self.config_data = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy())

        log_queue.put(f"[INIT] Smart Git-FTP Deployer v{APP_VERSION}")

        self.git = None
        self.all_commits = []
        self.hash_to_commit = {}
        self.files_to_process = {"added_modified": [], "deleted": []}

        self.abort_deploy_event = threading.Event()
        self.is_deploying = False
        self.browser_ftp = None
        self.ftp_lock = threading.Lock()
        self.last_focus_refresh = 0

        self.apply_styles()
        self.setup_ui()
        self.init_git()
        self.process_log_queue()

        # Binding shortcut F5 dan deteksi fokus jendela
        self.bind("<F5>", lambda e: self.refresh_git_data())
        self.bind("<FocusIn>", self.on_window_focus)

    def apply_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=CLR_BG)
        self.style.configure("Surface.TFrame", background=CLR_SURFACE)
        self.style.configure("TLabel", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI", 9))
        self.style.configure("Muted.TLabel", background=CLR_BG, foreground=CLR_TEXT_MUTED, font=("Segoe UI", 9))
        self.style.configure("Heading.TLabel", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI Bold", 10))

        self.style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=CLR_SURFACE, foreground=CLR_TEXT_MUTED,
                             padding=[16, 8], borderwidth=0, font=("Segoe UI Bold", 9))
        self.style.map("TNotebook.Tab",
                       background=[("selected", CLR_SURFACE_ALT)],
                       foreground=[("selected", CLR_PRIMARY)])

        self.style.configure("TLabelframe", background=CLR_BG, bordercolor=CLR_BORDER, relief="solid")
        self.style.configure("TLabelframe.Label", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI Bold", 9))

        self.style.configure("Treeview",
                             background=CLR_SURFACE,
                             foreground=CLR_TEXT,
                             fieldbackground=CLR_SURFACE,
                             rowheight=26,
                             borderwidth=0,
                             font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading",
                             background=CLR_SURFACE_ALT,
                             foreground=CLR_TEXT,
                             borderwidth=1,
                             relief="flat",
                             font=("Segoe UI Bold", 9))
        self.style.map("Treeview",
                       background=[("selected", CLR_PRIMARY)],
                       foreground=[("selected", "#FFFFFF")])

        self.style.configure("TButton", padding=[10, 5], font=("Segoe UI", 9), borderwidth=0)
        self.style.configure("Primary.TButton", background=CLR_PRIMARY, foreground="#FFFFFF", font=("Segoe UI Bold", 9))
        self.style.map("Primary.TButton", background=[("active", CLR_PRIMARY_HOVER)])
        self.style.configure("Success.TButton", background=CLR_SUCCESS, foreground="#FFFFFF", font=("Segoe UI Bold", 9))
        self.style.configure("Danger.TButton", background=CLR_DANGER, foreground="#FFFFFF", font=("Segoe UI Bold", 9))
        self.style.configure("Secondary.TButton", background=CLR_SURFACE_ALT, foreground=CLR_TEXT)
        self.style.configure("TCheckbutton", background=CLR_BG, foreground=CLR_TEXT, font=("Segoe UI", 9))

        self.style.configure("Horizontal.TProgressbar", background=CLR_PRIMARY, troughcolor=CLR_SURFACE_ALT, borderwidth=0)

    def init_git(self):
        try:
            self.git = GitManager(self.config_data.get("LOCAL_DIR", "."))
            log_queue.put(f"[INIT] Repositori Git aktif: {self.config_data.get('LOCAL_DIR')}")
            self.load_commits_data()
        except Exception as e:
            self.git = None
            log_queue.put(f"[INIT] Gagal memuat Git: {e}")
            if hasattr(self, "commit_tree"):
                self.commit_tree.delete(*self.commit_tree.get_children())
            if hasattr(self, "export_tree"):
                self.export_tree.delete(*self.export_tree.get_children())

    def refresh_git_data(self, silent=False):
        """Memaksa pembacaan ulang riwayat komit dari Git."""
        if self.is_deploying:
            return

        old_count = len(self.all_commits)
        try:
            if not self.git:
                self.git = GitManager(self.config_data.get("LOCAL_DIR", "."))

            self.all_commits = self.git.get_all_commits_chronological()
            self.hash_to_commit = {c["hash"]: c for c in self.all_commits}
            new_count = len(self.all_commits)

            if hasattr(self, "lbl_commit_stats"):
                self.lbl_commit_stats.config(text=f"Total Komit: {new_count}")

            if hasattr(self, "commit_tree"):
                self.filter_deployment_commits()

            if hasattr(self, "export_tree"):
                self.load_all_commits_for_exporter()

            if not silent:
                log_queue.put(f"[GIT] Data komit diperbarui (Total: {new_count} komit).")
            elif new_count != old_count:
                log_queue.put(f"[GIT] Terdeteksi komit baru! Total sekarang: {new_count} komit.")

        except Exception as e:
            if not silent:
                log_queue.put(f"[GIT ERROR] Gagal refresh: {e}")

    def on_window_focus(self, event):
        """Otomatis refresh data komit saat pengguna kembali ke jendela aplikasi."""
        if event.widget == self:
            now = time.time()
            if now - self.last_focus_refresh > 2.5:
                self.last_focus_refresh = now
                self.refresh_git_data(silent=True)

    def load_commits_data(self):
        if not self.git:
            return
        self.all_commits = self.git.get_all_commits_chronological()
        self.hash_to_commit = {c["hash"]: c for c in self.all_commits}
        total = len(self.all_commits)

        if hasattr(self, "lbl_commit_stats"):
            self.lbl_commit_stats.config(text=f"Total Komit: {total}")

        if hasattr(self, "commit_tree"):
            self.filter_deployment_commits()

        if hasattr(self, "export_tree"):
            self.load_all_commits_for_exporter()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_deploy = ttk.Frame(self.notebook)
        self.tab_exporter = ttk.Frame(self.notebook)
        self.tab_browser = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_deploy, text="Deployment Engine")
        self.notebook.add(self.tab_exporter, text="Ekspor SQL")
        self.notebook.add(self.tab_browser, text="Peramban Berkas")
        self.notebook.add(self.tab_config, text="Konfigurasi")

        self.setup_deploy_tab()
        self.setup_exporter_tab()
        self.setup_browser_tab()
        self.setup_config_tab()

    # ================= TAB 1: DEPLOYMENT =================

    def setup_deploy_tab(self):
        main_paned = ttk.PanedWindow(self.tab_deploy, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        top_split = ttk.PanedWindow(main_paned, orient=tk.HORIZONTAL)
        main_paned.add(top_split, weight=3)

        left_frame = ttk.Frame(top_split)
        top_split.add(left_frame, weight=3)

        ctrl_box = ttk.LabelFrame(left_frame, text=" Kontrol Deployment ", padding=8)
        ctrl_box.pack(fill=tk.X, pady=(0, 6))

        r1 = ttk.Frame(ctrl_box)
        r1.pack(fill=tk.X, pady=2)

        self.lbl_active_app = ttk.Label(r1, text=f"Profil: {self.active_profile}", style="Heading.TLabel")
        self.lbl_active_app.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_commit_stats = ttk.Label(r1, text="Total Komit: 0", style="Muted.TLabel")
        self.lbl_commit_stats.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(r1, text="Dari No:").pack(side=tk.LEFT, padx=(0, 3))
        self.ent_dep_start = ttk.Entry(r1, width=6, font=("Segoe UI", 9))
        self.ent_dep_start.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(r1, text="Sampai No:").pack(side=tk.LEFT, padx=(0, 3))
        self.ent_dep_end = ttk.Entry(r1, width=6, font=("Segoe UI", 9))
        self.ent_dep_end.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(r1, text="Pilih Rentang", command=self.apply_deploy_range, style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="Komit Terbaru", command=self.select_latest_commit, style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # Tombol Refresh yang jelas dan mencolok
        self.btn_refresh = ttk.Button(r1, text="Muat Ulang (F5)", command=self.refresh_git_data, style="Secondary.TButton")
        self.btn_refresh.pack(side=tk.LEFT, padx=2)

        r2 = ttk.Frame(ctrl_box)
        r2.pack(fill=tk.X, pady=(6, 2))

        self.var_consecutive = tk.BooleanVar(value=True)
        chk_consec = ttk.Checkbutton(
            r2,
            text="Mode Bertahap (Per Komit)",
            variable=self.var_consecutive,
            style="TCheckbutton"
        )
        chk_consec.pack(side=tk.LEFT)

        self.var_fail_fast = tk.BooleanVar(value=True)
        chk_fail = ttk.Checkbutton(
            r2,
            text="Hentikan jika ada galat",
            variable=self.var_fail_fast,
            style="TCheckbutton"
        )
        chk_fail.pack(side=tk.LEFT, padx=12)

        self.btn_abort = ttk.Button(r2, text="Batalkan", command=self.abort_deployment, state=tk.DISABLED, style="Danger.TButton")
        self.btn_abort.pack(side=tk.RIGHT, padx=2)

        self.btn_start_deploy = ttk.Button(r2, text="Mulai Deployment", command=self.start_deploy, state=tk.DISABLED, style="Primary.TButton")
        self.btn_start_deploy.pack(side=tk.RIGHT, padx=4)

        search_box = ttk.Frame(left_frame)
        search_box.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(search_box, text="Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_search = ttk.Entry(search_box)
        self.ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_search.bind("<KeyRelease>", lambda e: self.filter_deployment_commits())

        tree_box = ttk.Frame(left_frame)
        tree_box.pack(fill=tk.BOTH, expand=True)

        self.commit_tree = ttk.Treeview(
            tree_box,
            columns=("num", "hash", "date", "author", "subject"),
            show="headings",
            selectmode="extended"
        )
        self.commit_tree.heading("num", text="No")
        self.commit_tree.heading("hash", text="Hash")
        self.commit_tree.heading("date", text="Tanggal")
        self.commit_tree.heading("author", text="Penulis")
        self.commit_tree.heading("subject", text="Pesan Komit")

        self.commit_tree.column("num", width=60, anchor="center")
        self.commit_tree.column("hash", width=80, anchor="center")
        self.commit_tree.column("date", width=140, anchor="center")
        self.commit_tree.column("author", width=120)
        self.commit_tree.column("subject", width=300)

        c_scroll = ttk.Scrollbar(tree_box, orient=tk.VERTICAL, command=self.commit_tree.yview)
        self.commit_tree.configure(yscrollcommand=c_scroll.set)

        self.commit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        c_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.commit_tree.bind("<<TreeviewSelect>>", self.on_commit_tree_select)

        right_frame = ttk.LabelFrame(top_split, text=" Berkas dalam Antrean ", padding=6)
        top_split.add(right_frame, weight=2)

        self.lbl_queue_summary = ttk.Label(right_frame, text="Tidak ada komit terpilih.", style="Muted.TLabel")
        self.lbl_queue_summary.pack(fill=tk.X, pady=(0, 4))

        f_tree_box = ttk.Frame(right_frame)
        f_tree_box.pack(fill=tk.BOTH, expand=True)

        self.file_tree = ttk.Treeview(f_tree_box, columns=("action", "remote"), show="headings")
        self.file_tree.heading("action", text="Aksi")
        self.file_tree.heading("remote", text="Tujuan di Server")
        self.file_tree.column("action", width=75, anchor="center")
        self.file_tree.column("remote", width=360)

        f_scroll = ttk.Scrollbar(f_tree_box, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=f_scroll.set)

        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        f_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        bottom_frame = ttk.LabelFrame(main_paned, text=" Konsol Eksekusi & Status ", padding=6)
        main_paned.add(bottom_frame, weight=1)

        prog_bar_box = ttk.Frame(bottom_frame)
        prog_bar_box.pack(fill=tk.X, pady=(0, 4))

        self.progress_bar = ttk.Progressbar(prog_bar_box, orient=tk.HORIZONTAL, mode="determinate", style="Horizontal.TProgressbar")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.lbl_progress_status = ttk.Label(prog_bar_box, text="Status: Siap", font=("Segoe UI Bold", 9))
        self.lbl_progress_status.pack(side=tk.RIGHT)

        log_head = ttk.Frame(bottom_frame)
        log_head.pack(fill=tk.X, pady=(2, 2))
        ttk.Button(log_head, text="Bersihkan Konsol", command=self.clear_logs, style="Secondary.TButton").pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(
            bottom_frame,
            state="disabled",
            font=("Consolas", 9),
            bg=CLR_CONSOLE_BG,
            fg=CLR_CONSOLE_TEXT,
            insertbackground=CLR_TEXT,
            borderwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config("INFO", foreground="#60A5FA")
        self.log_text.tag_config("SUCCESS", foreground="#34D399")
        self.log_text.tag_config("ERROR", foreground="#F87171")
        self.log_text.tag_config("WARN", foreground="#FBBF24")
        self.log_text.tag_config("UPLOAD", foreground="#A78BFA")
        self.log_text.tag_config("DELETE", foreground="#F472B6")
        self.log_text.tag_config("PROGRESS", foreground="#94A3B8")
        self.log_text.tag_config("TIMESTAMP", foreground="#4B5563")

    def filter_deployment_commits(self):
        query = self.ent_search.get().strip().lower() if hasattr(self, "ent_search") else ""
        self.commit_tree.delete(*self.commit_tree.get_children())
        for c in reversed(self.all_commits):
            if query:
                match = (query in c["hash"].lower() or
                         query in c["subject"].lower() or
                         query in c["author"].lower() or
                         query == str(c["index"]))
                if not match:
                    continue
            self.commit_tree.insert(
                "",
                "end",
                iid=str(c["index"]),
                values=(f"#{c['index']}", c["hash"][:8], c["date"], c["author"], c["subject"])
            )

    def select_latest_commit(self):
        # Selalu refresh repositori sebelum memilih komit terbaru
        self.refresh_git_data(silent=True)
        if not self.all_commits:
            return
        latest = self.all_commits[-1]
        self.ent_dep_start.delete(0, tk.END)
        self.ent_dep_start.insert(0, str(latest["index"]))
        self.ent_dep_end.delete(0, tk.END)
        self.ent_dep_end.insert(0, str(latest["index"]))
        self.apply_deploy_range()

    def apply_deploy_range(self):
        try:
            start_no = int(self.ent_dep_start.get().strip())
            end_no = int(self.ent_dep_end.get().strip())
        except ValueError:
            messagebox.showerror("Galat", "Nomor rentang harus berupa angka bulat positif.")
            return

        total = len(self.all_commits)
        if start_no < 1 or end_no > total or start_no > end_no:
            messagebox.showwarning("Peringatan", f"Rentang komit harus antara 1 sampai {total}.")
            return

        selected_iids = [str(i) for i in range(start_no, end_no + 1)]
        existing_iids = [iid for iid in selected_iids if self.commit_tree.exists(iid)]

        self.commit_tree.selection_set(existing_iids)
        if existing_iids:
            self.commit_tree.see(existing_iids[0])

        self.recalculate_staged_files()

    def on_commit_tree_select(self, event):
        self.recalculate_staged_files()

    def get_selected_commit_objects(self):
        selected_iids = self.commit_tree.selection()
        if not selected_iids:
            return []
        indices = sorted([int(iid) for iid in selected_iids if iid.isdigit()])
        selected_commits = [self.all_commits[idx - 1] for idx in indices]
        return selected_commits

    def recalculate_staged_files(self):
        selected_commits = self.get_selected_commit_objects()
        self.file_tree.delete(*self.file_tree.get_children())

        if not selected_commits:
            self.lbl_queue_summary.config(text="Tidak ada komit terpilih.")
            self.btn_start_deploy.config(state=tk.DISABLED)
            return

        maps = self.config_data.get("PATH_MAPPINGS", [])
        exclude = self.config_data.get("EXCLUDE_PATTERNS", [])

        if self.var_consecutive.get():
            total_up = 0
            total_del = 0
            for c in selected_commits:
                diff = self.git.get_changed_files(c["hash"], c["hash"], exclude)
                total_up += len(diff["added_modified"])
                total_del += len(diff["deleted"])

            first_num = selected_commits[0]["index"]
            last_num = selected_commits[-1]["index"]
            count = len(selected_commits)
            summary_txt = f"Rentang: #{first_num} s/d #{last_num} ({count} komit) | Total Operasi: {total_up + total_del} berkas ({total_up} upload, {total_del} delete)"
            self.lbl_queue_summary.config(text=summary_txt)

            for c in selected_commits:
                diff = self.git.get_changed_files(c["hash"], c["hash"], exclude)
                for f in diff["added_modified"]:
                    self.file_tree.insert("", "end", values=(f"UP (#{c['index']})", resolve_remote_path(f, maps)))
                for f in diff["deleted"]:
                    self.file_tree.insert("", "end", values=(f"DEL (#{c['index']})", resolve_remote_path(f, maps)))

            self.btn_start_deploy.config(state=tk.NORMAL if (total_up + total_del) > 0 else tk.DISABLED)

        else:
            older = selected_commits[0]["hash"]
            newer = selected_commits[-1]["hash"]
            diff = self.git.get_changed_files(older, newer, exclude)

            for f in diff["added_modified"]:
                self.file_tree.insert("", "end", values=("UPLOAD", resolve_remote_path(f, maps)))
            for f in diff["deleted"]:
                self.file_tree.insert("", "end", values=("DELETE", resolve_remote_path(f, maps)))

            total_items = len(diff["added_modified"]) + len(diff["deleted"])
            summary_txt = f"Mode Akumulatif: {total_items} berkas berbeda antara #{selected_commits[0]['index']} dan #{selected_commits[-1]['index']}."
            self.lbl_queue_summary.config(text=summary_txt)
            self.btn_start_deploy.config(state=tk.NORMAL if total_items > 0 else tk.DISABLED)

    def start_deploy(self):
        selected_commits = self.get_selected_commit_objects()
        if not selected_commits:
            return

        consecutive = self.var_consecutive.get()
        start_no = selected_commits[0]["index"]
        end_no = selected_commits[-1]["index"]
        mode_desc = f"bertahap per-komit (#{start_no} s/d #{end_no})" if consecutive else f"akumulatif langsung (#{start_no} ke #{end_no})"

        if not messagebox.askyesno("Konfirmasi", f"Mulai deployment {mode_desc} ke profil [{self.active_profile}]?"):
            return

        self.is_deploying = True
        self.abort_deploy_event.clear()
        self.btn_start_deploy.config(state=tk.DISABLED)
        self.btn_abort.config(state=tk.NORMAL)
        self.progress_bar["value"] = 0
        self.lbl_progress_status.config(text="Status: Memulai koneksi FTP...")

        threading.Thread(target=self.worker_deploy_thread, args=(selected_commits, consecutive), daemon=True).start()

    def abort_deployment(self):
        if self.is_deploying:
            self.abort_deploy_event.set()
            log_queue.put("[WARN] Mengirim sinyal pembatalan ke engine deployment...")
            self.lbl_progress_status.config(text="Status: Membatalkan...")
            self.btn_abort.config(state=tk.DISABLED)

    def worker_deploy_thread(self, selected_commits, consecutive_mode):
        deployer = FTPDeployer(self.config_data, abort_event=self.abort_deploy_event)
        exclude = self.config_data.get("EXCLUDE_PATTERNS", [])
        fail_fast = self.var_fail_fast.get()

        if not deployer.connect():
            self._finalize_deploy_ui(False, "Gagal terhubung ke FTP.")
            return

        success_all = True
        try:
            if consecutive_mode:
                tasks = []
                total_ops = 0
                for c in selected_commits:
                    diff = self.git.get_changed_files(c["hash"], c["hash"], exclude)
                    file_count = len(diff["added_modified"]) + len(diff["deleted"])
                    total_ops += file_count
                    tasks.append((c, diff))

                log_queue.put(f"[INFO] Deployment bertahap dimulai: {len(tasks)} komit, total {total_ops} operasi berkas.")
                processed = 0

                for i, (commit, diff) in enumerate(tasks, 1):
                    if self.abort_deploy_event.is_set():
                        log_queue.put("[WARN] Deployment dihentikan oleh pengguna.")
                        success_all = False
                        break

                    c_idx = commit["index"]
                    c_hash = commit["hash"][:8]
                    log_queue.put(f"[STAGE {i}/{len(tasks)}] Memproses Komit #{c_idx} [{c_hash}]: {commit['subject']}")

                    for f in diff["deleted"]:
                        if self.abort_deploy_event.is_set(): break
                        ok = deployer.delete_file(f)
                        processed += 1
                        self._update_progress_ui(processed, total_ops)
                        if not ok and fail_fast:
                            log_queue.put(f"[ERROR] Operasi gagal pada berkas {f}. Proses dihentikan.")
                            success_all = False
                            break

                    if not success_all:
                        break

                    for f in diff["added_modified"]:
                        if self.abort_deploy_event.is_set(): break
                        ok = deployer.upload_file(f)
                        processed += 1
                        self._update_progress_ui(processed, total_ops)
                        if not ok and fail_fast:
                            log_queue.put(f"[ERROR] Operasi unggah gagal pada berkas {f}. Proses dihentikan.")
                            success_all = False
                            break

                    if not success_all:
                        break

                    log_queue.put(f"[OK] Komit #{c_idx} selesai disinkronkan.")

            else:
                older = selected_commits[0]["hash"]
                newer = selected_commits[-1]["hash"]
                diff = self.git.get_changed_files(older, newer, exclude)
                total_ops = len(diff["added_modified"]) + len(diff["deleted"])
                log_queue.put(f"[INFO] Deployment akumulatif dimulai: {total_ops} berkas.")
                processed = 0

                for f in diff["deleted"]:
                    if self.abort_deploy_event.is_set(): break
                    ok = deployer.delete_file(f)
                    processed += 1
                    self._update_progress_ui(processed, total_ops)
                    if not ok and fail_fast:
                        success_all = False
                        break

                if success_all:
                    for f in diff["added_modified"]:
                        if self.abort_deploy_event.is_set(): break
                        ok = deployer.upload_file(f)
                        processed += 1
                        self._update_progress_ui(processed, total_ops)
                        if not ok and fail_fast:
                            success_all = False
                            break

        except Exception as e:
            log_queue.put(f"[ERROR] Terjadi eksepsi fatal selama deployment: {e}")
            success_all = False

        deployer.disconnect()

        if self.abort_deploy_event.is_set():
            self._finalize_deploy_ui(False, "Dibatalkan oleh pengguna.")
        elif success_all:
            log_queue.put("[SUCCESS] Seluruh rentang komit berhasil di-deploy tanpa kesalahan.")
            self._finalize_deploy_ui(True, "Selesai Berhasil.")
        else:
            log_queue.put("[ERROR] Deployment selesai dengan beberapa kesalahan.")
            self._finalize_deploy_ui(False, "Selesai dengan Galat.")

    def _update_progress_ui(self, current, total):
        pct = int((current / total) * 100) if total > 0 else 100
        def _update():
            self.progress_bar["value"] = pct
            self.lbl_progress_status.config(text=f"Progres: {current}/{total} berkas ({pct}%)")
        self.after(0, _update)

    def _finalize_deploy_ui(self, is_success, status_msg):
        def _cleanup():
            self.is_deploying = False
            self.btn_abort.config(state=tk.DISABLED)
            self.btn_start_deploy.config(state=tk.NORMAL)
            self.lbl_progress_status.config(text=f"Status: {status_msg}")
        self.after(0, _cleanup)

    # ================= TAB 2: EKSPOR SQL =================

    def setup_exporter_tab(self):
        paned = ttk.PanedWindow(self.tab_exporter, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ctrl_frame = ttk.LabelFrame(paned, text=" Parameter Ekspor SQL ", padding=8)
        paned.add(ctrl_frame, weight=0)

        r1 = ttk.Frame(ctrl_frame)
        r1.pack(fill=tk.X, pady=2)

        self.lbl_export_profile = ttk.Label(r1, text=f"Profil: {self.active_profile}", style="Heading.TLabel")
        self.lbl_export_profile.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_real_total = ttk.Label(r1, text="Total Komit: 0", font=("Segoe UI Bold", 9))
        self.lbl_real_total.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(r1, text="App ID:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_sql_appid = ttk.Entry(r1, width=6)
        self.ent_sql_appid.insert(0, "1")
        self.ent_sql_appid.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(r1, text="Branch:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_sql_branch = ttk.Entry(r1, width=10)
        self.ent_sql_branch.insert(0, "main")
        self.ent_sql_branch.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(r1, text="Dari No:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_range_start = ttk.Entry(r1, width=6)
        self.ent_range_start.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(r1, text="Sampai No:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_range_end = ttk.Entry(r1, width=6)
        self.ent_range_end.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(r1, text="Terapkan Rentang", command=self.apply_export_range, style="Primary.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(r1, text="Semua", command=self.preset_select_all, style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="50 Terakhir", command=self.preset_select_last_50, style="Secondary.TButton").pack(side=tk.LEFT, padx=2)

        r2 = ttk.Frame(ctrl_frame)
        r2.pack(fill=tk.X, pady=(8, 0))

        self.lbl_export_status = ttk.Label(r2, text="", style="Muted.TLabel")
        self.lbl_export_status.pack(side=tk.LEFT)

        btn_box = ttk.Frame(r2)
        btn_box.pack(side=tk.RIGHT)

        ttk.Button(btn_box, text="Simpan Berkas .sql", command=self.save_sql_file, style="Secondary.TButton").pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_box, text="Salin Query SQL", command=self.copy_sql_to_clipboard, style="Primary.TButton").pack(side=tk.LEFT, padx=3)

        split_content = ttk.PanedWindow(paned, orient=tk.VERTICAL)
        paned.add(split_content, weight=1)

        tbl_frame = ttk.LabelFrame(split_content, text=" Urutan Kronologis (#1 = Komit Pertama) ", padding=4)
        split_content.add(tbl_frame, weight=2)

        tbl_wrapper = ttk.Frame(tbl_frame)
        tbl_wrapper.pack(fill=tk.BOTH, expand=True)

        self.export_tree = ttk.Treeview(
            tbl_wrapper,
            columns=("num", "hash", "date", "author", "msg"),
            show="headings",
            selectmode="extended"
        )
        self.export_tree.heading("num", text="No")
        self.export_tree.heading("hash", text="Hash")
        self.export_tree.heading("date", text="Tanggal")
        self.export_tree.heading("author", text="Penulis")
        self.export_tree.heading("msg", text="Pesan Komit")

        self.export_tree.column("num", width=60, anchor="center")
        self.export_tree.column("hash", width=85, anchor="center")
        self.export_tree.column("date", width=140, anchor="center")
        self.export_tree.column("author", width=130)
        self.export_tree.column("msg", width=500)

        exp_scroll = ttk.Scrollbar(tbl_wrapper, orient=tk.VERTICAL, command=self.export_tree.yview)
        self.export_tree.configure(yscrollcommand=exp_scroll.set)

        self.export_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        exp_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        sql_frame = ttk.LabelFrame(split_content, text=" Pratinjau Query SQL ", padding=4)
        split_content.add(sql_frame, weight=1)

        self.txt_sql_preview = scrolledtext.ScrolledText(
            sql_frame,
            font=("Consolas", 9),
            bg=CLR_CONSOLE_BG,
            fg=CLR_CONSOLE_TEXT,
            insertbackground=CLR_TEXT,
            borderwidth=0
        )
        self.txt_sql_preview.pack(fill=tk.BOTH, expand=True)

    def load_all_commits_for_exporter(self):
        self.export_tree.delete(*self.export_tree.get_children())
        total = len(self.all_commits)
        self.lbl_real_total.config(text=f"Total Komit: {total}")

        for c in self.all_commits:
            self.export_tree.insert("", "end", iid=str(c["index"]), values=(
                f"#{c['index']}",
                c["hash"][:8],
                c["date"],
                c["author"],
                c["subject"]
            ))

        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, "1")
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))

        self.lbl_export_status.config(text=f"Memuat {total} komit. Tentukan rentang indeks untuk ekspor.")
        self.generate_sql_query(1, total)

    def preset_select_all(self):
        total = len(self.all_commits)
        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, "1")
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))
        self.apply_export_range()

    def preset_select_last_50(self):
        total = len(self.all_commits)
        start = max(1, total - 49)
        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, str(start))
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))
        self.apply_export_range()

    def apply_export_range(self):
        try:
            start_no = int(self.ent_range_start.get().strip())
            end_no = int(self.ent_range_end.get().strip())
        except ValueError:
            messagebox.showerror("Galat", "Rentang harus berupa angka bulat.")
            return

        total = len(self.all_commits)
        if start_no < 1 or end_no > total or start_no > end_no:
            messagebox.showwarning("Peringatan", f"Rentang nomor tidak valid (1 s/d {total}).")
            return

        self.export_tree.selection_set([str(i) for i in range(start_no, end_no + 1)])
        if str(start_no) in self.export_tree.get_children():
            self.export_tree.see(str(start_no))

        count = (end_no - start_no) + 1
        self.lbl_export_status.config(text=f"Memilih {count} komit (#{start_no} s/d #{end_no}).")
        self.generate_sql_query(start_no, end_no)

    def generate_sql_query(self, start_no, end_no):
        app_id_str = self.ent_sql_appid.get().strip() or "1"
        branch_str = self.ent_sql_branch.get().strip() or "main"

        selected = [c for c in self.all_commits if start_no <= c["index"] <= end_no]
        if not selected:
            self.txt_sql_preview.delete("1.0", tk.END)
            self.txt_sql_preview.insert(tk.END, "-- Tidak ada komit dalam rentang ini.")
            return ""

        lines = [
            "-- =========================================================",
            f"-- EKSPOR KOMIT: #{start_no} - #{end_no} (TOTAL: {len(selected)})",
            f"-- TOTAL KOMIT: {len(self.all_commits)}",
            f"-- PROFIL: {self.active_profile} (APP ID: {app_id_str})",
            f"-- TANGGAL: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =========================================================\n",
            "INSERT IGNORE INTO `app_commits` (`app_id`, `commit_hash`, `branch`, `author`, `commit_message`, `committed_at`) VALUES"
        ]

        val_rows = []
        for c in selected:
            clean_msg = c["subject"].replace("'", "''").replace("\\", "\\\\")
            clean_auth = c["author"].replace("'", "''").replace("\\", "\\\\")
            val_rows.append(f"({app_id_str}, '{c['hash']}', '{branch_str}', '{clean_auth}', '{clean_msg}', '{c['date']}')")

        lines.append(",\n".join(val_rows) + ";\n")
        sql_content = "\n".join(lines)

        self.txt_sql_preview.delete("1.0", tk.END)
        self.txt_sql_preview.insert(tk.END, sql_content)
        return sql_content

    def copy_sql_to_clipboard(self):
        sql = self.txt_sql_preview.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showwarning("Peringatan", "Query SQL kosong.")
            return
        self.clipboard_clear()
        self.clipboard_append(sql)
        self.update()
        messagebox.showinfo("Informasi", "Query SQL telah disalin ke clipboard.")

    def save_sql_file(self):
        sql = self.txt_sql_preview.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showwarning("Peringatan", "Query SQL kosong.")
            return

        default_name = f"commits_{self.active_profile}_{self.ent_range_start.get()}_to_{self.ent_range_end.get()}.sql"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".sql",
            initialfile=default_name,
            filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(sql)
                messagebox.showinfo("Informasi", f"Berkas disimpan ke:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Galat", str(e))

    # ================= TAB 3: PERAMBAN BERKAS =================

    def setup_browser_tab(self):
        paned = ttk.PanedWindow(self.tab_browser, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        local_frame = ttk.LabelFrame(paned, text=" Direktori Lokal ", padding=6)
        paned.add(local_frame, weight=1)

        self.local_tree = ttk.Treeview(local_frame, show="tree")
        self.local_tree.pack(fill=tk.BOTH, expand=True)
        self.local_tree.bind("<<TreeviewOpen>>", self.on_local_expand)

        remote_frame = ttk.LabelFrame(paned, text=" Server FTP ", padding=6)
        paned.add(remote_frame, weight=1)

        btn_box = ttk.Frame(remote_frame)
        btn_box.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_box, text="Hubungkan & Jelajahi", command=self.refresh_remote_tree, style="Secondary.TButton").pack(fill=tk.X)

        self.remote_tree = ttk.Treeview(remote_frame, show="tree")
        self.remote_tree.pack(fill=tk.BOTH, expand=True)
        self.remote_tree.bind("<<TreeviewOpen>>", self.on_remote_expand)

        self.after(100, self.refresh_local_root)

    def refresh_local_root(self):
        self.local_tree.delete(*self.local_tree.get_children())
        p = os.path.abspath(self.config_data.get("LOCAL_DIR", "."))
        node = self.local_tree.insert("", "end", text=f"[DIR] {os.path.basename(p)}", values=(p, "dir"), open=True)
        self._populate_local_node(node, p)

    def _populate_local_node(self, parent_node, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                tag = "[DIR]" if entry.is_dir() else "[FILE]"
                node = self.local_tree.insert(parent_node, "end", text=f"{tag} {entry.name}",
                                             values=(entry.path, "dir" if entry.is_dir() else "file"))
                if entry.is_dir():
                    self.local_tree.insert(node, "end", text="memuat...")
        except Exception:
            pass

    def on_local_expand(self, event):
        node = self.local_tree.focus()
        if not node:
            return
        path, n_type = self.local_tree.item(node, "values")
        if n_type == "dir":
            children = self.local_tree.get_children(node)
            if children and self.local_tree.item(children[0], "text") == "memuat...":
                self.local_tree.delete(*children)
                self._populate_local_node(node, path)

    def _ensure_browser_ftp(self):
        with self.ftp_lock:
            try:
                if self.browser_ftp:
                    self.browser_ftp.voidcmd("NOOP")
                    return True
            except Exception:
                pass

            try:
                cfg = self.config_data
                if cfg.get("FTP_TLS"):
                    self.browser_ftp = ftplib.FTP_TLS(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                    self.browser_ftp.prot_p()
                else:
                    self.browser_ftp = ftplib.FTP(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                self.browser_ftp.set_pasv(True)
                return True
            except Exception as e:
                log_queue.put(f"[ERROR] Koneksi FTP browser gagal: {e}")
                return False

    def refresh_remote_tree(self):
        self.remote_tree.delete(*self.remote_tree.get_children())
        root_path = self.config_data.get("REMOTE_DIR", "/")
        if not root_path:
            root_path = "/"

        root_id = self.remote_tree.insert("", "end", text=f"[ROOT] {root_path}", values=(root_path, "dir"), open=True)
        self.remote_tree.insert(root_id, "end", text="memuat...")
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
                    log_queue.put(f"[FTP] Membuka: {target_path}")

                    items = []
                    try:
                        self.browser_ftp.cwd(target_path)
                        for name, facts in self.browser_ftp.mlsd():
                            if name in [".", ".."]:
                                continue
                            is_dir = facts.get("type") in ["dir", "pdir", "cdir"]
                            items.append((name, is_dir))
                    except Exception:
                        try:
                            lines = []
                            self.browser_ftp.retrlines("LIST", lines.append)
                            for line in lines:
                                if not line:
                                    continue
                                parts = line.split()
                                if len(parts) < 9:
                                    continue
                                name = " ".join(parts[8:])
                                if name in [".", ".."]:
                                    continue
                                is_dir = line.startswith("d") or "<DIR>" in line.upper()
                                items.append((name, is_dir))
                        except Exception as e2:
                            log_queue.put(f"[FTP ERROR] Gagal membaca direktori: {e2}")

                    items.sort(key=lambda x: (not x[1], x[0].lower()))

                    def fill_ui():
                        self.remote_tree.delete(*self.remote_tree.get_children(parent_node))
                        if not items:
                            self.remote_tree.insert(parent_node, "end", text="(Kosong)", values=("", "file"))
                            return

                        for name, is_dir in items:
                            tag = "[DIR]" if is_dir else "[FILE]"
                            new_path = (target_path.rstrip("/") + "/" + name).replace("//", "/")
                            node = self.remote_tree.insert(
                                parent_node,
                                "end",
                                text=f"{tag} {name}",
                                values=(new_path, "dir" if is_dir else "file")
                            )
                            if is_dir:
                                self.remote_tree.insert(node, "end", text="memuat...")

                        self.remote_tree.item(parent_node, open=True)

                    self.after(0, fill_ui)
            except Exception as e:
                log_queue.put(f"[FTP ERROR] Pembacaan gagal: {e}")
                self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))

        threading.Thread(target=worker, daemon=True).start()

    def on_remote_expand(self, event):
        node = self.remote_tree.focus()
        if not node:
            return
        vals = self.remote_tree.item(node, "values")
        if not vals or len(vals) < 2:
            return

        path, n_type = vals
        if n_type == "dir":
            children = self.remote_tree.get_children(node)
            if children:
                first_text = self.remote_tree.item(children[0], "text").strip()
                if first_text == "memuat...":
                    self._fetch_remote_content(node, path)

    # ================= TAB 4: KONFIGURASI =================

    def setup_config_tab(self):
        container = ttk.Frame(self.tab_config, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        profile_frame = ttk.LabelFrame(container, text=" Profil Konfigurasi ", padding=10)
        profile_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(profile_frame, text="Profil Aktif:").pack(side=tk.LEFT, padx=(0, 8))

        self.profile_var = tk.StringVar(value=self.active_profile)
        self.profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            state="readonly",
            font=("Segoe UI", 9),
            width=28
        )
        self.profile_combo["values"] = list(self.config_store["profiles"].keys())
        self.profile_combo.pack(side=tk.LEFT, padx=4)
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)

        ttk.Button(profile_frame, text="Tambah Profil", command=self.add_profile, style="Secondary.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Button(profile_frame, text="Hapus Profil", command=self.delete_profile, style="Danger.TButton").pack(side=tk.LEFT, padx=4)

        form_frame = ttk.LabelFrame(container, text=" Parameter Server & Direktori ", padding=10)
        form_frame.pack(fill=tk.X)

        fields = [
            ("Host FTP:", "FTP_HOST"),
            ("User FTP:", "FTP_USER"),
            ("Password FTP:", "FTP_PASS"),
            ("Direktori Lokal:", "LOCAL_DIR"),
            ("Direktori Remote:", "REMOTE_DIR")
        ]

        self.cfg_ents = {}
        for i, (label_text, key) in enumerate(fields):
            ttk.Label(form_frame, text=label_text).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            entry = ttk.Entry(form_frame, font=("Segoe UI", 9))
            if "Password" in label_text:
                entry.config(show="*")
            entry.insert(0, self.config_data.get(key, ""))
            entry.grid(row=i, column=1, sticky="ew", pady=4)
            self.cfg_ents[key] = entry
        form_frame.columnconfigure(1, weight=1)

        self.var_ftp_tls = tk.BooleanVar(value=bool(self.config_data.get("FTP_TLS")))
        ttk.Checkbutton(
            form_frame,
            text="FTP over TLS (FTPS)",
            variable=self.var_ftp_tls,
            style="TCheckbutton"
        ).grid(row=len(fields), column=1, sticky="w", pady=4)

        map_frame = ttk.LabelFrame(container, text=" Pemetaan Jalur (Path Mapping) ", padding=10)
        map_frame.pack(fill=tk.BOTH, expand=True, pady=12)

        self.map_tree = ttk.Treeview(map_frame, columns=("local", "remote"), show="headings", height=4)
        self.map_tree.heading("local", text="Prefix Jalur Lokal")
        self.map_tree.heading("remote", text="Tujuan Jalur Remote")
        self.map_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        map_btn_frame = ttk.Frame(map_frame)
        map_btn_frame.pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(map_btn_frame, text="Tambah", command=self.add_mapping, style="Secondary.TButton").pack(fill=tk.X, pady=2)
        ttk.Button(map_btn_frame, text="Hapus", command=self.del_mapping, style="Secondary.TButton").pack(fill=tk.X, pady=2)

        for m in self.config_data.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m["local"], m["remote"]))

        ttk.Button(container, text="Simpan Konfigurasi Profil", command=self.save_config_ui, style="Primary.TButton").pack(fill=tk.X, ipady=4)

    def populate_form_from_config(self, cfg):
        for key, entry in self.cfg_ents.items():
            entry.delete(0, tk.END)
            entry.insert(0, cfg.get(key, ""))
        if hasattr(self, "var_ftp_tls"):
            self.var_ftp_tls.set(bool(cfg.get("FTP_TLS", False)))

        self.map_tree.delete(*self.map_tree.get_children())
        for m in cfg.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m.get("local", ""), m.get("remote", "")))

    def on_profile_change(self, event=None):
        selected_name = self.profile_var.get()
        if selected_name not in self.config_store["profiles"]:
            return

        self.active_profile = selected_name
        self.config_store["active_profile"] = selected_name
        self.config_data = self.config_store["profiles"][selected_name]

        self.populate_form_from_config(self.config_data)
        self.lbl_active_app.config(text=f"Profil: {self.active_profile}")

        if hasattr(self, "lbl_export_profile"):
            self.lbl_export_profile.config(text=f"Profil: {self.active_profile}")

        self.init_git()
        self.refresh_local_root()

        if self.browser_ftp:
            try:
                self.browser_ftp.quit()
            except Exception:
                pass
            self.browser_ftp = None

        save_config_store(self.config_store)
        log_queue.put(f"[CONFIG] Beralih ke profil: {self.active_profile}")

    def add_profile(self):
        new_name = simpledialog.askstring("Tambah Profil", "Nama profil baru:", parent=self)
        if not new_name:
            return
        new_name = new_name.strip()

        if new_name in self.config_store["profiles"]:
            messagebox.showerror("Galat", f"Profil '{new_name}' sudah ada.")
            return

        current_active = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy()).copy()
        self.config_store["profiles"][new_name] = current_active
        self.config_store["active_profile"] = new_name

        self.profile_combo["values"] = list(self.config_store["profiles"].keys())
        self.profile_var.set(new_name)
        self.on_profile_change()
        messagebox.showinfo("Informasi", f"Profil '{new_name}' berhasil dibuat.")

    def delete_profile(self):
        profiles = self.config_store["profiles"]
        if len(profiles) <= 1:
            messagebox.showwarning("Peringatan", "Minimal harus menyisakan 1 profil konfigurasi.")
            return

        if messagebox.askyesno("Konfirmasi", f"Hapus profil '{self.active_profile}'?"):
            deleted_name = self.active_profile
            del profiles[deleted_name]

            new_active = list(profiles.keys())[0]
            self.active_profile = new_active
            self.config_store["active_profile"] = new_active

            self.profile_combo["values"] = list(profiles.keys())
            self.profile_var.set(new_active)
            self.on_profile_change()
            messagebox.showinfo("Informasi", f"Profil '{deleted_name}' telah dihapus.")

    def add_mapping(self):
        dialog = tk.Toplevel(self, bg=CLR_BG)
        dialog.title("Tambah Pemetaan Jalur")
        dialog.geometry("380x180")
        dialog.resizable(False, False)

        ttk.Label(dialog, text="Prefix Lokal (cth: dist/):").pack(pady=(12, 2), padx=16, anchor="w")
        e1 = ttk.Entry(dialog)
        e1.pack(fill=tk.X, padx=16)

        ttk.Label(dialog, text="Tujuan Remote (cth: public_html/):").pack(pady=(8, 2), padx=16, anchor="w")
        e2 = ttk.Entry(dialog)
        e2.pack(fill=tk.X, padx=16)

        def save():
            loc = e1.get().strip()
            rem = e2.get().strip()
            if loc and rem:
                self.map_tree.insert("", "end", values=(loc, rem))
                dialog.destroy()

        ttk.Button(dialog, text="Simpan", command=save, style="Primary.TButton").pack(pady=14)

    def del_mapping(self):
        for item in self.map_tree.selection():
            self.map_tree.delete(item)

    def save_config_ui(self):
        mappings = []
        for row in self.map_tree.get_children():
            val = self.map_tree.item(row)["values"]
            mappings.append({"local": str(val[0]), "remote": str(val[1])})

        updated = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy())
        for key, entry in self.cfg_ents.items():
            updated[key] = entry.get().strip()
        updated["PATH_MAPPINGS"] = mappings
        if hasattr(self, "var_ftp_tls"):
            updated["FTP_TLS"] = bool(self.var_ftp_tls.get())

        self.config_store["profiles"][self.active_profile] = updated
        self.config_data = updated

        if save_config_store(self.config_store):
            messagebox.showinfo("Informasi", f"Konfigurasi profil '{self.active_profile}' tersimpan.")
            self.init_git()

    # ================= PEMROSES LOG TERMINAL BERWARNA =================

    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def process_log_queue(self):
        try:
            while True:
                msg = log_queue.get_nowait()
                timestamp = time.strftime("[%H:%M:%S] ")
                
                tag = "INFO"
                if "[ERROR]" in msg:
                    tag = "ERROR"
                elif "[SUCCESS]" in msg:
                    tag = "SUCCESS"
                elif "[WARN]" in msg:
                    tag = "WARN"
                elif "[UPLOAD]" in msg:
                    tag = "UPLOAD"
                elif "[DELETE]" in msg:
                    tag = "DELETE"
                elif "[PROGRESS]" in msg:
                    tag = "PROGRESS"

                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, timestamp, "TIMESTAMP")
                self.log_text.insert(tk.END, f"{msg}\n", tag)
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
        except Exception:
            pass
        self.after(100, self.process_log_queue)

if __name__ == "__main__":
    app = App()
    app.mainloop()