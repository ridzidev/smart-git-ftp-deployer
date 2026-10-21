"""Tab Konfigurasi: pengelolaan profil, parameter server, dan pemetaan jalur."""
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from .config import DEFAULT_CONFIG, save_config_store, log_queue
from .theme import CLR_BG, FONT_LABEL
from .ui_dropdown import TombolDropdown

class ConfigTabMixin:

    # ---------- setup_config_tab ----------
    def setup_config_tab(self):
        container = ttk.Frame(self.tab_config, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        profile_frame = ttk.LabelFrame(container, text=" Profil Konfigurasi ", padding=10)
        profile_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(profile_frame, text="Profil Aktif:").pack(side=tk.LEFT, padx=(0, 8))

        self.profile_combo = TombolDropdown(
            profile_frame,
            pilihan=list(self.config_store["profiles"].keys()),
            nilai=self.active_profile,
            on_pilih=self.on_profile_change,
            lebar=28
        )
        self.profile_combo.pack(side=tk.LEFT, padx=4)

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
            entry = ttk.Entry(form_frame, font=FONT_LABEL)
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

        ttk.Label(container, text="Data server Anda disimpan dengan aman.",
                  style="Muted.TLabel").pack(fill=tk.X, pady=(0, 6))

        ttk.Button(container, text="Simpan Konfigurasi Profil", command=self.save_config_ui, style="Primary.TButton").pack(fill=tk.X, ipady=4)

    # ---------- populate_form_from_config ----------
    def populate_form_from_config(self, cfg):
        for key, entry in self.cfg_ents.items():
            entry.delete(0, tk.END)
            entry.insert(0, cfg.get(key, ""))
        if hasattr(self, "var_ftp_tls"):
            self.var_ftp_tls.set(bool(cfg.get("FTP_TLS", False)))

        self.map_tree.delete(*self.map_tree.get_children())
        for m in cfg.get("PATH_MAPPINGS", []):
            self.map_tree.insert("", "end", values=(m.get("local", ""), m.get("remote", "")))

    # ---------- on_profile_change ----------
    def on_profile_change(self, event=None):
        selected_name = self.profile_combo.get()
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

        if hasattr(self, "perbarui_bilah_status"):
            self.perbarui_bilah_status()

        if self.browser_ftp:
            try:
                self.browser_ftp.quit()
            except Exception:
                pass
            self.browser_ftp = None

        save_config_store(self.config_store)
        log_queue.put(f"[CONFIG] Beralih ke profil: {self.active_profile}")

    # ---------- add_profile ----------
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

        self.profile_combo.pilihan = list(self.config_store["profiles"].keys())
        self.profile_combo.atur(new_name)
        self.on_profile_change()
        messagebox.showinfo("Informasi", f"Profil '{new_name}' berhasil dibuat.")

    # ---------- delete_profile ----------
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

            self.profile_combo.pilihan = list(profiles.keys())
            self.profile_combo.atur(new_active)
            self.on_profile_change()
            messagebox.showinfo("Informasi", f"Profil '{deleted_name}' telah dihapus.")

    # ---------- add_mapping ----------
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

    # ---------- del_mapping ----------
    def del_mapping(self):
        for item in self.map_tree.selection():
            self.map_tree.delete(item)

    # ---------- save_config_ui ----------
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
        else:
            messagebox.showerror(
                "Gagal Menyimpan",
                "Konfigurasi gagal tersimpan. Rinciannya ada di konsol eksekusi (tab Deployment Engine). "
                "Data konfigurasi lama tidak berubah.")
