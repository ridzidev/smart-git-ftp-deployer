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

# CONFIG FILE NAME (disimpan di direktori skrip)
CONFIG_FILENAME = "deploy_config.json"

# DEFAULT KONFIGURASI (digunakan saat file config tidak ditemukan) isi debgan konfigurasi standar anda
DEFAULT_CONFIG = {
    "FTP_HOST": "",
    "FTP_USER": "",
    "FTP_PASS": "",
    "LOCAL_DIR": ".",
    "REMOTE_DIR": "/",
    "EXCLUDE_PATTERNS": [
    ]
}

# ==============================================================================

log_queue = Queue()

def load_config():
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    if config_path.is_file():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            # ensure keys exist (merge defaults)
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            # ensure EXCLUDE_PATTERNS is list
            if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                # maybe user saved as newline text; convert to list
                merged["EXCLUDE_PATTERNS"] = [l for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()]
            elif merged.get("EXCLUDE_PATTERNS") is None:
                merged["EXCLUDE_PATTERNS"] = DEFAULT_CONFIG["EXCLUDE_PATTERNS"]
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
        if not pattern:
            continue
        if path_str.startswith(pattern):
            return True
    return False

class GitManager:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / '.git').is_dir():
            raise FileNotFoundError(f"Direktori .git tidak ditemukan di '{self.repo_path}'.")
    def get_recent_commits(self, count=30):
        command = ['git', 'log', f'-n{count}', '--pretty=format:%H|%an|%s']
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding='utf-8')
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line: continue
                parts = line.split('|', 2)
                commits.append({'hash': parts[0], 'author': parts[1], 'subject': parts[2]})
            return commits
        except subprocess.CalledProcessError as e:
            log_queue.put(f"GIT ERROR: {e.stderr}")
            return []
        except FileNotFoundError:
            log_queue.put("GIT ERROR: Perintah 'git' tidak ditemukan.")
            return []

    def get_changed_files(self, start_hash, end_hash, exclude_patterns):
        if start_hash == end_hash:
            command = ['git', 'show', '--pretty=', '--name-status', start_hash]
        else:
            command = ['git', 'diff', '--name-status', f'{start_hash}^', end_hash]
        result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, encoding='utf-8')
        files = {'added_modified': [], 'deleted': []}
        for line in result.stdout.strip().split('\n'):
            if not line: continue
            # status and path are separated by tab(s)
            parts = line.split('\t')
            if len(parts) < 2: continue
            status = parts[0]
            file_path_str = parts[-1]
            if should_exclude(file_path_str, exclude_patterns):
                log_queue.put(f"  Diabaikan: {file_path_str}")
                continue
            if status.strip().upper() in ['A', 'M', 'C', 'R']:
                files['added_modified'].append(file_path_str)
            elif status.strip().upper() == 'D':
                files['deleted'].append(file_path_str)
        return files

class FTPDeployer:
    def __init__(self, host, user, password, local_dir, remote_dir):
        self.host = host
        self.user = user
        self.password = password
        self.local_dir = Path(local_dir).resolve()
        self.remote_dir = remote_dir
        self.ftp = None

    def _log(self, message):
        log_queue.put(message)

    def connect(self):
        try:
            self._log(f"Menghubungkan ke {self.host}...")
            self.ftp = ftplib.FTP(self.host, timeout=30)
            self.ftp.login(self.user, self.password)
            # Force passive mode
            self.ftp.set_pasv(True)
            self._log("Berhasil terhubung! (Mode Pasif diaktifkan)")
            self.ftp.cwd(self.remote_dir)
            self._log(f"Berada di direktori remote: {self.ftp.pwd()}")
            return True
        except Exception as e:
            self._log(f"FTP ERROR: Gagal terhubung: {e}")
            return False

    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except:
                    pass
            self._log("Koneksi FTP ditutup.")

    def create_remote_dir_recursively(self, remote_path):
        dir_path = Path(remote_path).parent.as_posix()
        if dir_path and dir_path != '.':
            parts = dir_path.split('/')
            current_path = ""
            for part in parts:
                if not part: continue
                current_path += "/" + part
                try: self.ftp.mkd(current_path)
                except Exception: pass

    def upload_file(self, relative_path_str):
        local_file = self.local_dir / relative_path_str
        remote_file = Path(relative_path_str).as_posix()
        self._log(f"-> Mengunggah: {remote_file}")
        try:
            self.create_remote_dir_recursively(remote_file)
            with open(local_file, 'rb') as f: self.ftp.storbinary(f'STOR {remote_file}', f)
            return True
        except FileNotFoundError:
            self._log(f"!! ERROR: File lokal tidak ditemukan: {local_file}")
            return False
        except Exception as e:
            self._log(f"!! ERROR saat mengunggah {remote_file}: {e}")
            return False

    def delete_file(self, relative_path_str):
        remote_file = Path(relative_path_str).as_posix()
        self._log(f"-> Menghapus: {remote_file}")
        try:
            self.ftp.delete(remote_file)
            self.try_remove_empty_parent_dirs(remote_file)
            return True
        except Exception as e:
            self._log(f"!! Gagal menghapus {remote_file} (mungkin sudah tidak ada).")
            return False

    def try_remove_empty_parent_dirs(self, remote_path):
        parent = Path(remote_path).parent.as_posix()
        while parent and parent != '.':
            try:
                if not self.ftp.nlst(parent):
                    self.ftp.rmd(parent)
                    self._log(f"  Direktori kosong dihapus: {parent}")
                    parent = Path(parent).parent.as_posix()
                else: break
            except: break

    def deploy(self, files_to_process):
        if not self.connect(): return
        added_modified = files_to_process.get('added_modified', [])
        deleted = files_to_process.get('deleted', [])
        total_actions = len(added_modified) + len(deleted)
        self._log("\n" + "="*20 + " MULAI DEPLOYMENT " + "="*20)
        start_time = time.time()
        if deleted:
            self._log(f"\n--- Menghapus {len(deleted)} file... ---")
            for file_path in deleted: self.delete_file(file_path)
        if added_modified:
            self._log(f"\n--- Mengunggah {len(added_modified)} file... ---")
            for file_path in added_modified: self.upload_file(file_path)
        elapsed_time = time.time() - start_time
        self._log("\n" + "="*20 + " DEPLOYMENT SELESAI " + "="*20)
        self._log(f"Total aksi: {total_actions}. Waktu: {elapsed_time:.2f} detik.")
        self.disconnect()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Git-FTP Deployer (Structure-Aware) - with Config")
        self.geometry("980x720")

        # load configuration
        self.config_data = load_config()

        # initialize git manager (may raise)
        try:
            self.git = GitManager(self.config_data["LOCAL_DIR"])
        except FileNotFoundError as e:
            # still allow app to open, but show error and disable deploy features
            messagebox.showerror("Error Inisialisasi Git", f"{e}\n\nAplikasi akan tetap dibuka, perbaiki LOCAL_DIR di tab Configuration.")
            self.git = None

        self.commits_data = []
        self.files_to_process = {'added_modified': [], 'deleted': []}
        self.create_widgets()
        if self.git:
            self.load_commits()
        self.process_log_queue()

    def create_widgets(self):
        # Notebook with two tabs: Deploy & Configuration
        notebook = ttk.Notebook(self, padding=6)
        notebook.pack(fill=tk.BOTH, expand=True)

        # ---------- Deploy Tab ----------
        deploy_frame = ttk.Frame(notebook)
        notebook.add(deploy_frame, text="Deploy")

        left_pane = ttk.Frame(deploy_frame)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,5), pady=10)

        top_left_frame = ttk.Frame(left_pane)
        top_left_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(top_left_frame, text="Commit Terbaru:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(top_left_frame, text="Refresh", command=self.load_commits).pack(side=tk.RIGHT)
        self.test_conn_button = ttk.Button(top_left_frame, text="Tes Koneksi FTP", command=self.start_connection_test)
        self.test_conn_button.pack(side=tk.RIGHT, padx=(0, 5))

        self.commit_listbox = tk.Listbox(left_pane, selectmode=tk.EXTENDED, exportselection=False, font=("Consolas", 10))
        self.commit_listbox.pack(fill=tk.BOTH, expand=True)
        self.commit_listbox.bind('<<ListboxSelect>>', self.on_commit_select)

        right_pane = ttk.PanedWindow(deploy_frame, orient=tk.VERTICAL)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=10)

        file_pane = ttk.LabelFrame(right_pane, text="File yang Akan Diproses")
        right_pane.add(file_pane, weight=1)
        self.file_listbox = tk.Listbox(file_pane, font=("Consolas", 9))
        self.file_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_pane_container = ttk.Frame(right_pane)
        right_pane.add(log_pane_container, weight=1)
        log_frame = ttk.LabelFrame(log_pane_container, text="Log & Progress")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled', font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.deploy_button = ttk.Button(log_pane_container, text="Deploy Selected Commits", command=self.start_deployment, state=tk.DISABLED, style="Accent.TButton")
        self.deploy_button.pack(fill=tk.X, pady=(10, 0), ipady=8)
        self.style = ttk.Style(self)
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # ---------- Configuration Tab ----------
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Configuration")

        cfg_inner = ttk.Frame(config_frame, padding=10)
        cfg_inner.pack(fill=tk.BOTH, expand=True)

        # FTP host/user/pass
        row = 0
        ttk.Label(cfg_inner, text="FTP Host:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.ftp_host_var = tk.StringVar(value=self.config_data.get("FTP_HOST", ""))
        ttk.Entry(cfg_inner, textvariable=self.ftp_host_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(cfg_inner, text="FTP User:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.ftp_user_var = tk.StringVar(value=self.config_data.get("FTP_USER", ""))
        ttk.Entry(cfg_inner, textvariable=self.ftp_user_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(cfg_inner, text="FTP Pass:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.ftp_pass_var = tk.StringVar(value=self.config_data.get("FTP_PASS", ""))
        ttk.Entry(cfg_inner, textvariable=self.ftp_pass_var, show="*", width=40).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # Local directory with browse
        ttk.Label(cfg_inner, text="LOCAL_DIR (project root):").grid(row=row, column=0, sticky=tk.W, pady=6)
        self.local_dir_var = tk.StringVar(value=self.config_data.get("LOCAL_DIR", "."))
        local_entry = ttk.Entry(cfg_inner, textvariable=self.local_dir_var, width=46)
        local_entry.grid(row=row, column=1, sticky=tk.W, pady=6)
        ttk.Button(cfg_inner, text="Browse...", command=self.browse_local_dir).grid(row=row, column=2, sticky=tk.W, padx=4)
        row += 1

        ttk.Label(cfg_inner, text="REMOTE_DIR (FTP root):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.remote_dir_var = tk.StringVar(value=self.config_data.get("REMOTE_DIR", "/"))
        ttk.Entry(cfg_inner, textvariable=self.remote_dir_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # Exclude patterns (multiline)
        ttk.Label(cfg_inner, text="EXCLUDE_PATTERNS (satu per baris):").grid(row=row, column=0, sticky=tk.NW, pady=6)
        self.exclude_text = scrolledtext.ScrolledText(cfg_inner, width=50, height=12)
        # fill exclude_text from list
        excludes = self.config_data.get("EXCLUDE_PATTERNS", [])
        if isinstance(excludes, list):
            self.exclude_text.insert(tk.END, "\n".join(excludes))
        else:
            # fallback
            self.exclude_text.insert(tk.END, str(excludes))
        self.exclude_text.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=6)
        row += 1

        # config buttons
        btn_frame = ttk.Frame(cfg_inner)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=(6,0))
        ttk.Button(btn_frame, text="Load Config (disk)", command=self.load_config_from_disk).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Save Config", command=self.save_config_from_ui).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Apply (update Git & UI)", command=self.apply_config_changes).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Reset to Defaults", command=self.reset_config_to_defaults).pack(side=tk.LEFT, padx=4)

        # Info label
        ttk.Label(cfg_inner, text=f"Config file: {Path(__file__).parent.resolve()/CONFIG_FILENAME}", font=("Segoe UI", 8)).grid(row=row+1, column=0, columnspan=3, sticky=tk.W, pady=(8,0))

    # ----------------- Config UI handlers -----------------
    def browse_local_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.local_dir_var.get() or ".")
        if chosen:
            self.local_dir_var.set(chosen)

    def load_config_from_disk(self):
        self.config_data = load_config()
        # update UI fields
        self.ftp_host_var.set(self.config_data.get("FTP_HOST", ""))
        self.ftp_user_var.set(self.config_data.get("FTP_USER", ""))
        self.ftp_pass_var.set(self.config_data.get("FTP_PASS", ""))
        self.local_dir_var.set(self.config_data.get("LOCAL_DIR", "."))
        self.remote_dir_var.set(self.config_data.get("REMOTE_DIR", "/"))
        self.exclude_text.delete("1.0", tk.END)
        excludes = self.config_data.get("EXCLUDE_PATTERNS", [])
        if isinstance(excludes, list):
            self.exclude_text.insert(tk.END, "\n".join(excludes))
        else:
            self.exclude_text.insert(tk.END, str(excludes))
        log_queue.put("[CONFIG] Dimuat dari disk.")
        # apply to runtime (update git manager)
        self.apply_config_changes()

    def save_config_from_ui(self):
        cfg = {
            "FTP_HOST": self.ftp_host_var.get().strip(),
            "FTP_USER": self.ftp_user_var.get().strip(),
            "FTP_PASS": self.ftp_pass_var.get(),
            "LOCAL_DIR": self.local_dir_var.get().strip() or ".",
            "REMOTE_DIR": self.remote_dir_var.get().strip() or "/",
            "EXCLUDE_PATTERNS": [line.strip() for line in self.exclude_text.get("1.0", tk.END).splitlines() if line.strip()]
        }
        ok = save_config(cfg)
        if ok:
            self.config_data = cfg
            messagebox.showinfo("Sukses", "Konfigurasi berhasil disimpan.")
        else:
            messagebox.showerror("Gagal", "Gagal menyimpan konfigurasi. Periksa log.")
        # do not auto-apply unless user clicks Apply to avoid surprise

    def apply_config_changes(self):
        # update runtime config and refresh git manager & UI
        self.config_data = {
            "FTP_HOST": self.ftp_host_var.get().strip(),
            "FTP_USER": self.ftp_user_var.get().strip(),
            "FTP_PASS": self.ftp_pass_var.get(),
            "LOCAL_DIR": self.local_dir_var.get().strip() or ".",
            "REMOTE_DIR": self.remote_dir_var.get().strip() or "/",
            "EXCLUDE_PATTERNS": [line.strip() for line in self.exclude_text.get("1.0", tk.END).splitlines() if line.strip()]
        }
        # recreate git manager
        try:
            self.git = GitManager(self.config_data["LOCAL_DIR"])
            log_queue.put(f"[CONFIG] GitManager diupdate ke {self.config_data['LOCAL_DIR']}")
            self.load_commits()
        except FileNotFoundError as e:
            self.git = None
            messagebox.showerror("Error Git", f"{e}\nPeriksa LOCAL_DIR.")
        # update FTP test button state (always enabled)
        log_queue.put("[CONFIG] Konfigurasi diterapkan di runtime.")

    def reset_config_to_defaults(self):
        self.config_data = DEFAULT_CONFIG.copy()
        self.ftp_host_var.set(self.config_data["FTP_HOST"])
        self.ftp_user_var.set(self.config_data["FTP_USER"])
        self.ftp_pass_var.set(self.config_data["FTP_PASS"])
        self.local_dir_var.set(self.config_data["LOCAL_DIR"])
        self.remote_dir_var.set(self.config_data["REMOTE_DIR"])
        self.exclude_text.delete("1.0", tk.END)
        self.exclude_text.insert(tk.END, "\n".join(self.config_data["EXCLUDE_PATTERNS"]))
        log_queue.put("[CONFIG] Direset ke default (UI). Simpan jika ingin permanen.")

    # ----------------- Logging queue processing -----------------
    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)

    def process_log_queue(self):
        try:
            while True:
                self.log(log_queue.get_nowait())
        except Exception:
            pass
        self.after(100, self.process_log_queue)

    # ----------------- Git / commit handling -----------------
    def load_commits(self):
        if not self.git:
            log_queue.put("GIT: GitManager tidak tersedia. Periksa konfigurasi LOCAL_DIR.")
            return
        self.log("Memuat commit dari Git...")
        self.commit_listbox.delete(0, tk.END)
        self.file_listbox.delete(0, tk.END)
        self.deploy_button.config(state=tk.DISABLED)
        self.commits_data = self.git.get_recent_commits()
        for commit in self.commits_data:
            display_text = f"{commit['hash'][:7]} - {commit['subject']} ({commit['author']})"
            self.commit_listbox.insert(tk.END, display_text)
        self.log(f"{len(self.commits_data)} commit berhasil dimuat.")

    def on_commit_select(self, event=None):
        if not self.git:
            messagebox.showwarning("Git tidak tersedia", "Tidak dapat mendeteksi file yang berubah karena GitManager tidak tersedia.")
            return
        selected_indices = self.commit_listbox.curselection()
        self.file_listbox.delete(0, tk.END)
        if not selected_indices:
            self.deploy_button.config(state=tk.DISABLED)
            return
        selected_commits = [self.commits_data[i] for i in selected_indices]
        newest_commit_hash, oldest_commit_hash = selected_commits[0]['hash'], selected_commits[-1]['hash']
        self.log(f"\nMendeteksi file yang berubah dari commit {oldest_commit_hash[:7]} hingga {newest_commit_hash[:7]}...")
        self.files_to_process = self.git.get_changed_files(oldest_commit_hash, newest_commit_hash, self.config_data.get("EXCLUDE_PATTERNS", []))
        added_modified, deleted = self.files_to_process.get('added_modified', []), self.files_to_process.get('deleted', [])
        if added_modified or deleted:
            for f in added_modified: self.file_listbox.insert(tk.END, f"[UNGGAH] {f}")
            for f in deleted: self.file_listbox.insert(tk.END, f"[HAPUS]   {f}")
            self.log(f"Ditemukan {len(added_modified)} file untuk diunggah dan {len(deleted)} file untuk dihapus.")
            self.deploy_button.config(state=tk.NORMAL)
        else:
            self.log("Tidak ada file yang berubah pada commit yang dipilih (setelah filter).")
            self.deploy_button.config(state=tk.DISABLED)

    # ----------------- Connection test & deployment -----------------
    def start_connection_test(self):
        self.log("\n" + "="*10 + " MEMULAI TES KONEKSI FTP " + "="*10)
        self.test_conn_button.config(state=tk.DISABLED)
        test_thread = threading.Thread(target=self.run_connection_test_worker, daemon=True)
        test_thread.start()

    def run_connection_test_worker(self):
        cfg = self.config_data
        deployer = FTPDeployer(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], cfg["LOCAL_DIR"], cfg["REMOTE_DIR"])
        if deployer.connect():
            try:
                deployer._log("-> Tes transfer data: Mencoba mengambil daftar file di direktori root...")
                listing = deployer.ftp.nlst()
                deployer._log(f"  [OK] Berhasil mengambil daftar file. Ditemukan {len(listing)} item.")
                deployer._log("\n[BERHASIL] Tes koneksi dan transfer data (listing) berhasil!")
            except Exception as e:
                deployer._log(f"\n!! [GAGAL] Koneksi awal berhasil, tapi tes transfer data GAGAL: {e}")
            finally:
                deployer.disconnect()
        else:
            deployer._log("\n[GAGAL] Tes koneksi tidak berhasil.")
        self.after(0, lambda: self.test_conn_button.config(state=tk.NORMAL))

    def start_deployment(self):
        if not self.files_to_process.get('added_modified') and not self.files_to_process.get('deleted'):
            messagebox.showwarning("Tidak Ada File", "Tidak ada file yang perlu diproses.")
            return
        total_files = len(self.files_to_process.get('added_modified', [])) + len(self.files_to_process.get('deleted', []))
        if messagebox.askyesno("Konfirmasi Deployment", f"Anda akan memproses {total_files} file (unggah/hapus) ke server. Lanjutkan?"):
            self.deploy_button.config(state=tk.DISABLED)
            deploy_thread = threading.Thread(target=self.run_deployment_worker, daemon=True)
            deploy_thread.start()

    def run_deployment_worker(self):
        cfg = self.config_data
        deployer = FTPDeployer(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], cfg["LOCAL_DIR"], cfg["REMOTE_DIR"])
        deployer.deploy(self.files_to_process)
        self.after(0, lambda: self.deploy_button.config(state=tk.NORMAL))

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        # Tampilkan error sederhana sebelum keluar
        try:
            messagebox.showerror("Fatal Error", f"Terjadi kesalahan fatal saat aplikasi dimulai:\n{e}")
        except:
            print("Fatal Error:", e)
        sys.exit(1)
