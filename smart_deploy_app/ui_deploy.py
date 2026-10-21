"""Tab Deployment Engine: pemilihan commit, antrean berkas, dan eksekusi deployment."""
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from .config import log_queue, resolve_remote_path
from .ftp_deployer import FTPDeployer
from .ui_date_filter import DateRangeFilter, tanggal_komit
from .theme import CLR_CONSOLE_BG, CLR_CONSOLE_TEXT, CLR_TEXT

class DeployTabMixin:

    # ---------- setup_deploy_tab ----------
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

        date_box = ttk.Frame(left_frame)
        date_box.pack(fill=tk.X, pady=(0, 4))

        self.date_filter_deploy = DateRangeFilter(
            date_box,
            on_change=self.filter_deployment_commits,
            on_apply=self.apply_date_range_deploy,
        )
        self.date_filter_deploy.pack(fill=tk.X)

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

    # ---------- filter_deployment_commits ----------
    def filter_deployment_commits(self):
        query = self.ent_search.get().strip().lower() if hasattr(self, "ent_search") else ""
        tgl_dari, tgl_sampai = (self.date_filter_deploy.get_range()
                                if hasattr(self, "date_filter_deploy") else (None, None))
        saring_tanggal = bool(tgl_dari or tgl_sampai)

        self.commit_tree.delete(*self.commit_tree.get_children())
        tampil = 0
        for c in reversed(self.all_commits):
            if query:
                match = (query in c["hash"].lower() or
                         query in c["subject"].lower() or
                         query in c["author"].lower() or
                         query == str(c["index"]))
                if not match:
                    continue
            if saring_tanggal:
                c_tgl = tanggal_komit(c)
                if c_tgl is None:
                    continue
                if tgl_dari and c_tgl < tgl_dari:
                    continue
                if tgl_sampai and c_tgl > tgl_sampai:
                    continue
            self.commit_tree.insert(
                "",
                "end",
                iid=str(c["index"]),
                values=(f"#{c['index']}", c["hash"][:8], c["date"], c["author"], c["subject"])
            )
            tampil += 1

        if hasattr(self, "date_filter_deploy"):
            self.date_filter_deploy.set_hitung(tampil, len(self.all_commits), saring_tanggal)

    # ---------- apply_date_range_deploy ----------
    def apply_date_range_deploy(self):
        """Pilih rentang commit sesuai hasil saringan tanggal yang tampil saat ini."""
        indeks = sorted(int(i) for i in self.commit_tree.get_children() if str(i).isdigit())
        if not indeks:
            messagebox.showinfo("Informasi", "Tidak ada komit dalam rentang tanggal ini.")
            return

        self.ent_dep_start.delete(0, tk.END)
        self.ent_dep_start.insert(0, str(indeks[0]))
        self.ent_dep_end.delete(0, tk.END)
        self.ent_dep_end.insert(0, str(indeks[-1]))
        self.apply_deploy_range()

    # ---------- select_latest_commit ----------
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

    # ---------- apply_deploy_range ----------
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

    # ---------- on_commit_tree_select ----------
    def on_commit_tree_select(self, event):
        self.recalculate_staged_files()

    # ---------- get_selected_commit_objects ----------
    def get_selected_commit_objects(self):
        selected_iids = self.commit_tree.selection()
        if not selected_iids:
            return []
        indices = sorted([int(iid) for iid in selected_iids if iid.isdigit()])
        selected_commits = [self.all_commits[idx - 1] for idx in indices]
        return selected_commits

    # ---------- recalculate_staged_files ----------
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

    # ---------- start_deploy ----------
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

    # ---------- abort_deployment ----------
    def abort_deployment(self):
        if self.is_deploying:
            self.abort_deploy_event.set()
            log_queue.put("[WARN] Mengirim sinyal pembatalan ke engine deployment...")
            self.lbl_progress_status.config(text="Status: Membatalkan...")
            self.btn_abort.config(state=tk.DISABLED)

    # ---------- worker_deploy_thread ----------
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

    # ---------- _update_progress_ui ----------
    def _update_progress_ui(self, current, total):
        pct = int((current / total) * 100) if total > 0 else 100
        def _update():
            self.progress_bar["value"] = pct
            self.lbl_progress_status.config(text=f"Progres: {current}/{total} berkas ({pct}%)")
        self.after(0, _update)

    # ---------- _finalize_deploy_ui ----------
    def _finalize_deploy_ui(self, is_success, status_msg):
        def _cleanup():
            self.is_deploying = False
            self.btn_abort.config(state=tk.DISABLED)
            self.btn_start_deploy.config(state=tk.NORMAL)
            self.lbl_progress_status.config(text=f"Status: {status_msg}")
        self.after(0, _cleanup)
