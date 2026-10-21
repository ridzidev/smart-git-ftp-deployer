"""Tab Ekspor SQL: menyusun riwayat commit menjadi pernyataan SQL."""
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from .theme import CLR_CONSOLE_BG, CLR_CONSOLE_TEXT, CLR_ROW_GENAP, CLR_TEXT, FONT_KONSOL, FONT_LABEL_TEBAL
from .ui_date_filter import DateRangeFilter, tanggal_komit

class ExporterTabMixin:

    # ---------- setup_exporter_tab ----------
    def setup_exporter_tab(self):
        paned_tiang = ttk.PanedWindow(self.tab_exporter, orient=tk.HORIZONTAL)
        paned_tiang.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ----- kolom kiri: seluruh paramater ekspor di satu sidebar -----
        sidebar = ttk.Frame(paned_tiang, padding=(10, 8, 8, 8), width=310)
        sidebar.pack_propagate(False)
        paned_tiang.add(sidebar, weight=0)

        self.lbl_export_profile = ttk.Label(sidebar, text=f"Profil: {self.active_profile}", style="Heading.TLabel")
        self.lbl_export_profile.pack(fill=tk.X)
        self.lbl_real_total = ttk.Label(sidebar, text="Total Komit: 0", font=FONT_LABEL_TEBAL)
        self.lbl_real_total.pack(fill=tk.X, pady=(0, 6))

        ttk.Separator(sidebar).pack(fill=tk.X, pady=6)

        # parameter tujuan SQL
        ttk.Label(sidebar, text="Parameter SQL", style="Muted.TLabel").pack(anchor="w")
        r_param = ttk.Frame(sidebar)
        r_param.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(r_param, text="App ID:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_sql_appid = ttk.Entry(r_param, width=5)
        self.ent_sql_appid.insert(0, "1")
        self.ent_sql_appid.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(r_param, text="Branch:").pack(side=tk.LEFT, padx=(0, 4))
        self.ent_sql_branch = ttk.Entry(r_param, width=9)
        self.ent_sql_branch.insert(0, "main")
        self.ent_sql_branch.pack(side=tk.LEFT)

        # rentang nomor komit
        ttk.Label(sidebar, text="Rentang Nomor", style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
        r_no = ttk.Frame(sidebar)
        r_no.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(r_no, text="Dari No:").pack(side=tk.LEFT, padx=(0, 3))
        self.ent_range_start = ttk.Entry(r_no, width=6)
        self.ent_range_start.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(r_no, text="Sampai No:").pack(side=tk.LEFT, padx=(0, 3))
        self.ent_range_end = ttk.Entry(r_no, width=6)
        self.ent_range_end.pack(side=tk.LEFT)

        r_preset = ttk.Frame(sidebar)
        r_preset.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(r_preset, text="Semua", command=self.preset_select_all,
                   style="Secondary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(r_preset, text="50 Terakhir", command=self.preset_select_last_50,
                   style="Secondary.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(sidebar, text="Terapkan Rentang", command=self.apply_export_range,
                   style="Primary.TButton").pack(fill=tk.X, pady=(8, 0), ipady=5)

        # saringan rentang tanggal versi menumpuk
        self.date_filter_export = DateRangeFilter(
            sidebar,
            on_change=self.filter_exporter_commits,
            on_apply=self.apply_date_range_export,
            teks_tombol="Pilih Rentang Ini",
            menumpuk=True
        )
        self.date_filter_export.pack(fill=tk.X, pady=(12, 0))

        ttk.Separator(sidebar).pack(fill=tk.X, pady=10)

        # status + aksi hasil
        self.lbl_export_status = ttk.Label(sidebar, text="", style="Muted.TLabel",
                                           wraplength=280, justify=tk.LEFT)
        self.lbl_export_status.pack(anchor="w")

        ttk.Button(sidebar, text="Salin Query SQL", command=self.copy_sql_to_clipboard,
                   style="Primary.TButton").pack(fill=tk.X, pady=(14, 0), ipady=6)
        ttk.Button(sidebar, text="Simpan Berkas .sql", command=self.save_sql_file,
                   style="Secondary.TButton").pack(fill=tk.X, pady=(6, 0))

        # ----- kolom kanan: tabel kronologis di atas, pratinjau SQL melintang di bawah -----
        paned_kanan = ttk.PanedWindow(paned_tiang, orient=tk.VERTICAL)
        paned_tiang.add(paned_kanan, weight=1)

        tbl_frame = ttk.LabelFrame(paned_kanan, text=" Urutan Kronologis (#1 = Komit Pertama) ", padding=4)
        paned_kanan.add(tbl_frame, weight=6)

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
        self.export_tree.tag_configure("genap", background=CLR_ROW_GENAP)

        sql_frame = ttk.LabelFrame(paned_kanan, text=" Pratinjau Query SQL ", padding=4)
        paned_kanan.add(sql_frame, weight=4)

        self.txt_sql_preview = scrolledtext.ScrolledText(
            sql_frame,
            font=FONT_KONSOL,
            bg=CLR_CONSOLE_BG,
            fg=CLR_CONSOLE_TEXT,
            insertbackground=CLR_TEXT,
            borderwidth=0
        )
        self.txt_sql_preview.pack(fill=tk.BOTH, expand=True)

    # ---------- load_all_commits_for_exporter ----------
    def load_all_commits_for_exporter(self):
        total = len(self.all_commits)
        self.lbl_real_total.config(text=f"Total Komit: {total}")
        self.filter_exporter_commits()

        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, "1")
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))

        self.lbl_export_status.config(text=f"Memuat {total} komit. Tentukan rentang indeks untuk ekspor.")
        self.generate_sql_query(1, total)

    # ---------- filter_exporter_commits ----------
    def filter_exporter_commits(self):
        """Tampilkan ulang daftar komit sesuai saringan tanggal (tanpa batas = semua)."""
        tgl_dari, tgl_sampai = (self.date_filter_export.get_range()
                                if hasattr(self, "date_filter_export") else (None, None))
        saring_tanggal = bool(tgl_dari or tgl_sampai)

        self.export_tree.delete(*self.export_tree.get_children())
        tampil = 0
        for c in self.all_commits:
            if saring_tanggal:
                c_tgl = tanggal_komit(c)
                if c_tgl is None:
                    continue
                if tgl_dari and c_tgl < tgl_dari:
                    continue
                if tgl_sampai and c_tgl > tgl_sampai:
                    continue
            self.export_tree.insert("", "end", iid=str(c["index"]), values=(
                f"#{c['index']}",
                c["hash"][:8],
                c["date"],
                c["author"],
                c["subject"]
            ), tags=("genap",) if tampil % 2 == 0 else ())
            tampil += 1

        if hasattr(self, "date_filter_export"):
            self.date_filter_export.set_hitung(tampil, len(self.all_commits), saring_tanggal)

    # ---------- apply_date_range_export ----------
    def apply_date_range_export(self):
        """Pilih rentang ekspor sesuai hasil saringan tanggal yang tampil saat ini."""
        if not self.date_filter_export.terapkan_valid():
            return

        indeks = sorted(int(i) for i in self.export_tree.get_children() if str(i).isdigit())
        if not indeks:
            messagebox.showinfo("Informasi", "Tidak ada komit dalam rentang tanggal ini.")
            return

        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, str(indeks[0]))
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(indeks[-1]))
        self.apply_export_range()

    # ---------- preset_select_all ----------
    def preset_select_all(self):
        total = len(self.all_commits)
        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, "1")
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))
        self.apply_export_range()

    # ---------- preset_select_last_50 ----------
    def preset_select_last_50(self):
        total = len(self.all_commits)
        start = max(1, total - 49)
        self.ent_range_start.delete(0, tk.END)
        self.ent_range_start.insert(0, str(start))
        self.ent_range_end.delete(0, tk.END)
        self.ent_range_end.insert(0, str(total))
        self.apply_export_range()

    # ---------- apply_export_range ----------
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

        kandidat = [str(i) for i in range(start_no, end_no + 1)]
        ada = [iid for iid in kandidat if self.export_tree.exists(iid)]

        self.export_tree.selection_set(ada)
        if ada:
            self.export_tree.see(ada[0])

        count = (end_no - start_no) + 1
        self.lbl_export_status.config(text=f"Memilih {count} komit (#{start_no} s/d #{end_no}).")
        self.generate_sql_query(start_no, end_no)

    # ---------- generate_sql_query ----------
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

    # ---------- copy_sql_to_clipboard ----------
    def copy_sql_to_clipboard(self):
        sql = self.txt_sql_preview.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showwarning("Peringatan", "Query SQL kosong.")
            return
        self.clipboard_clear()
        self.clipboard_append(sql)
        self.update()
        messagebox.showinfo("Informasi", "Query SQL telah disalin ke clipboard.")

    # ---------- save_sql_file ----------
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
