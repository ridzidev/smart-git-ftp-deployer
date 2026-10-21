"""Jendela utama aplikasi: perakitan tab, gaya tampilan, dan pemroses log."""
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .theme import (CLR_BG, CLR_BORDER, CLR_PRIMARY, CLR_PRIMARY_HOVER,
    CLR_SUCCESS, CLR_DANGER, CLR_SURFACE, CLR_SURFACE_ALT, CLR_TEXT, CLR_TEXT_MUTED,
    FONT_JUDUL, FONT_LABEL, FONT_LABEL_TEBAL)

from .config import APP_VERSION, DEFAULT_CONFIG, load_config_store, log_queue
from .git_manager import GitManager
from .ui_deploy import DeployTabMixin
from .ui_exporter import ExporterTabMixin
from .ui_browser import BrowserTabMixin
from .ui_config import ConfigTabMixin
from .ui_splash import LayarPembuka
from .ui_tutorial import PanduanTabMixin
from .ui_changelog import ChangelogTabMixin

class App(DeployTabMixin, ExporterTabMixin, BrowserTabMixin, ConfigTabMixin,
          PanduanTabMixin, ChangelogTabMixin, tk.Tk):

    # ---------- __init__ ----------
    def __init__(self):
        super().__init__()
        self.title(f"Smart Git-FTP Deployer v{APP_VERSION}")
        self.geometry("1340x920")
        self.minsize(1080, 720)
        self.configure(bg=CLR_BG)
        self.withdraw()  # tampil setelah layar pembuka selesai

        self.config_store = load_config_store()
        self.active_profile = self.config_store.get("active_profile", "Default")
        self.config_data = self.config_store["profiles"].get(self.active_profile, DEFAULT_CONFIG.copy())

        log_queue.put(f"[INFO] Smart Git-FTP Deployer v{APP_VERSION} siap digunakan.")

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
        self.perbarui_bilah_status()

        # Binding shortcut F5 dan deteksi fokus jendela
        self.bind("<F5>", lambda e: self.refresh_git_data())
        self.bind("<FocusIn>", self.on_window_focus)

        # layar pembuka tampil minimal sesaat, lalu menyerahkan tampilan saat data siap
        self.layar_pembuka = LayarPembuka(self, APP_VERSION, self._tampilkan_utama)
        self.layar_pembuka.siap()

    # ---------- _tampilkan_utama ----------
    def _tampilkan_utama(self):
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass

    # ---------- perbarui_bilah_status ----------
    def perbarui_bilah_status(self):
        if not hasattr(self, "lbl_status_kiri"):
            return
        nama_repo = "-"
        try:
            if self.git:
                nama_repo = Path(self.config_data.get("LOCAL_DIR", ".")).resolve().name
        except Exception:
            pass
        self.lbl_status_kiri.config(
            text=(f"Profil: {self.active_profile}     •     Repositori: {nama_repo}"
                  f"     •     Total komit: {len(self.all_commits)}"))

    # ---------- apply_styles ----------
    def apply_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=CLR_BG)
        self.style.configure("Surface.TFrame", background=CLR_SURFACE)
        self.style.configure("TLabel", background=CLR_BG, foreground=CLR_TEXT, font=FONT_LABEL)
        self.style.configure("Muted.TLabel", background=CLR_BG, foreground=CLR_TEXT_MUTED, font=FONT_LABEL)
        self.style.configure("Heading.TLabel", background=CLR_BG, foreground=CLR_TEXT, font=FONT_JUDUL)

        self.style.configure("TNotebook", background=CLR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=CLR_SURFACE, foreground=CLR_TEXT_MUTED,
                             padding=[16, 8], borderwidth=0, font=FONT_LABEL_TEBAL)
        self.style.map("TNotebook.Tab",
                       background=[("selected", CLR_SURFACE_ALT)],
                       foreground=[("selected", CLR_PRIMARY)])

        self.style.configure("TLabelframe", background=CLR_BG, bordercolor=CLR_BORDER, relief="solid")
        self.style.configure("TLabelframe.Label", background=CLR_BG, foreground=CLR_TEXT, font=FONT_LABEL_TEBAL)

        self.style.configure("Treeview",
                             background=CLR_SURFACE,
                             foreground=CLR_TEXT,
                             fieldbackground=CLR_SURFACE,
                             rowheight=26,
                             borderwidth=0,
                             font=FONT_LABEL)
        self.style.configure("Treeview.Heading",
                             background=CLR_SURFACE_ALT,
                             foreground=CLR_TEXT,
                             borderwidth=1,
                             relief="flat",
                             font=FONT_LABEL_TEBAL)
        self.style.map("Treeview",
                       background=[("selected", CLR_PRIMARY)],
                       foreground=[("selected", "#FFFFFF")])

        self.style.configure("TButton", padding=[10, 5], font=FONT_LABEL, borderwidth=0)
        self.style.configure("Primary.TButton", background=CLR_PRIMARY, foreground="#FFFFFF", font=FONT_LABEL_TEBAL)
        self.style.map("Primary.TButton", background=[("active", CLR_PRIMARY_HOVER)])
        self.style.configure("Success.TButton", background=CLR_SUCCESS, foreground="#FFFFFF", font=FONT_LABEL_TEBAL)
        self.style.configure("Danger.TButton", background=CLR_DANGER, foreground="#FFFFFF", font=FONT_LABEL_TEBAL)
        self.style.configure("Secondary.TButton", background=CLR_SURFACE_ALT, foreground=CLR_TEXT)
        self.style.map("Secondary.TButton",
                       background=[("active", "#2B3239"), ("pressed", CLR_SURFACE_ALT)],
                       foreground=[("disabled", CLR_TEXT_MUTED)])

        self.style.configure("TCheckbutton", background=CLR_BG, foreground=CLR_TEXT, font=FONT_LABEL)

        # kolom isian gelap: tanpa gaya ini kolom memakai tampilan terang bawaan
        self.style.configure("TEntry",
                             fieldbackground=CLR_SURFACE,
                             foreground=CLR_TEXT,
                             insertcolor=CLR_TEXT,
                             bordercolor=CLR_BORDER,
                             lightcolor=CLR_BORDER,
                             darkcolor=CLR_BORDER)
        self.style.map("TEntry",
                       fieldbackground=[("active", CLR_SURFACE_ALT)],
                       foreground=[("disabled", CLR_TEXT_MUTED)])

        self.style.configure("TScrollbar",
                             background=CLR_SURFACE_ALT,
                             troughcolor=CLR_BG,
                             borderwidth=0,
                             arrowcolor=CLR_TEXT_MUTED)
        self.style.map("TScrollbar", background=[("active", "#2B3239")])

        self.style.configure("TPanedwindow", background=CLR_BG, sashwidth=5, sashpad=2)

        self.style.configure("Horizontal.TProgressbar", background=CLR_PRIMARY, troughcolor=CLR_SURFACE_ALT, borderwidth=0)

    # ---------- init_git ----------
    def init_git(self):
        try:
            self.git = GitManager(self.config_data.get("LOCAL_DIR", "."))
            nama_repo = Path(self.config_data.get("LOCAL_DIR", ".")).resolve().name
            log_queue.put(f"[GIT] Repositori aktif: {nama_repo}")
            self.load_commits_data()
        except Exception:
            self.git = None
            log_queue.put("[GIT] Repositori Git tidak ditemukan di direktori lokal profil ini. "
                          "Periksa kolom Direktori Lokal di tab Konfigurasi.")
            if hasattr(self, "commit_tree"):
                self.commit_tree.delete(*self.commit_tree.get_children())
            if hasattr(self, "export_tree"):
                self.export_tree.delete(*self.export_tree.get_children())

    # ---------- refresh_git_data ----------
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
                log_queue.put(f"[GIT] Komit baru terdeteksi (Total: {new_count}).")

            self.perbarui_bilah_status()

        except Exception:
            if not silent:
                log_queue.put("[ERROR] Refresh data komit gagal.")

    # ---------- on_window_focus ----------
    def on_window_focus(self, event):
        """Otomatis refresh data komit saat pengguna kembali ke jendela aplikasi."""
        if event.widget == self:
            now = time.time()
            if now - self.last_focus_refresh > 2.5:
                self.last_focus_refresh = now
                self.refresh_git_data(silent=True)

    # ---------- load_commits_data ----------
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

        self.perbarui_bilah_status()

    # ---------- setup_ui ----------
    def setup_ui(self):
        bilah_bawah = ttk.Frame(self)
        bilah_bawah.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 8))

        self.lbl_status_kiri = ttk.Label(bilah_bawah, text="Menyiapkan...", style="Muted.TLabel")
        self.lbl_status_kiri.pack(side=tk.LEFT)

        ttk.Label(bilah_bawah, text=f"v{APP_VERSION}   •   created by ridzidev",
                  style="Muted.TLabel").pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        self.tab_deploy = ttk.Frame(self.notebook)
        self.tab_exporter = ttk.Frame(self.notebook)
        self.tab_browser = ttk.Frame(self.notebook)
        self.tab_config = ttk.Frame(self.notebook)
        self.tab_tutorial = ttk.Frame(self.notebook)
        self.tab_changelog = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_deploy, text="Deployment Engine")
        self.notebook.add(self.tab_exporter, text="Ekspor SQL")
        self.notebook.add(self.tab_browser, text="Peramban Berkas")
        self.notebook.add(self.tab_config, text="Konfigurasi")
        self.notebook.add(self.tab_tutorial, text="Panduan")
        self.notebook.add(self.tab_changelog, text="Perubahan")

        self.setup_deploy_tab()
        self.setup_exporter_tab()
        self.setup_browser_tab()
        self.setup_config_tab()
        self.setup_tutorial_tab()
        self.setup_changelog_tab()

    # ---------- clear_logs ----------
    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    # ---------- process_log_queue ----------
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
