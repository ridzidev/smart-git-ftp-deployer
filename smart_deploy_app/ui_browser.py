"""Tab Peramban Berkas: penjelajahan dan operasi berkas lokal serta server FTP.

Panel datar berkolom (Nama, Ukuran, Diubah) dengan bilah alamat per sisi,
ikon, sortir kolom, menu klik kanan, dobel-klik untuk pindah folder atau
transfer, overlay status Git di panel lokal, dan saklar sinkron navigasi.
"""
import datetime as dt
import ftplib
import io
import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .config import log_queue, should_exclude
from .ui_editor import CodeEditor, MAX_BYTES
from .theme import (CLR_DANGER, CLR_ROW_GENAP, CLR_SUCCESS, CLR_TEXT_MUTED,
                    CLR_WARNING, NAMA_FONT)

FMT_WAKTU = "%Y-%m-%d %H:%M"
FONT_KECUALI = (NAMA_FONT, 9, "overstrike")

TIPE_DIR = "dir"
TIPE_FILE = "file"


def _fmt_ukuran(nilai):
    if nilai is None:
        return "-"
    ukuran = float(nilai)
    for satuan in ("B", "KB", "MB", "GB"):
        if ukuran < 1024:
            return f"{ukuran:.1f} {satuan}".replace(".0 ", " ")
        ukuran /= 1024
    return f"{ukuran:.1f} TB"


def _fmt_waktu(stempel):
    """Stempel waktu epoch (lokal) menjadi teks pendek."""
    if not stempel:
        return "-"
    try:
        return dt.datetime.fromtimestamp(stempel).strftime(FMT_WAKTU)
    except (ValueError, OSError, OverflowError):
        return "-"


def _waktu_server(teks):
    """Fakta MLSD 'YYYYMMDDHHMMSS' menjadi teks pendek."""
    bersih = str(teks or "").strip()
    if len(bersih) < 14 or not bersih.isdigit():
        return "-"
    try:
        hasil = dt.datetime.strptime(bersih[:14], "%Y%m%d%H%M%S")
        return hasil.strftime(FMT_WAKTU)
    except ValueError:
        return "-"


def _gabung_server(*bagian):
    """Satukan potongan jalur server tanpa menyobek pemisah ganda."""
    jalur = "/".join(s.strip("/") for s in bagian if s and s.strip("/"))
    return "/" + jalur if jalur else "/"


def _induk_server(jalur):
    bersih = "/" + (jalur or "").strip("/")
    if bersih == "/":
        return None
    return _gabung_server("/", bersih.rsplit("/", 1)[0])


class BrowserTabMixin:

    # ---------- setup_browser_tab ----------
    def setup_browser_tab(self):
        self._ops_sibuk = False
        self._urutan = {"lokal": ("nama", True), "server": ("nama", True)}
        self._cache_lokal = []
        self._cache_server = []
        self._baris_atas = {"lokal": None, "server": None}
        self._panel_pilihan = "lokal"
        self._token_server = 0
        self.akar_lokal = os.path.abspath(self.config_data.get("LOCAL_DIR", "."))
        self._server_path = self.config_data.get("REMOTE_DIR") or "/"
        self.var_sinkron = tk.BooleanVar(value=False)

        paned_tiang = ttk.PanedWindow(self.tab_browser, orient=tk.HORIZONTAL)
        paned_tiang.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._paned_tiang = paned_tiang

        # ---------- panel lokal ----------
        panel_lokal = ttk.LabelFrame(paned_tiang, text=" Direktori Lokal ", padding=6)
        paned_tiang.add(panel_lokal, weight=1)

        r_alamat = ttk.Frame(panel_lokal)
        r_alamat.pack(fill=tk.X)
        ttk.Button(r_alamat, text="Naik", width=6, style="Secondary.TButton",
                   command=self._naik_lokal).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(r_alamat, text="Root", width=6, style="Secondary.TButton",
                   command=lambda: self._isi_lokal(self.akar_lokal)).pack(side=tk.LEFT, padx=(0, 4))
        self.ent_alamat_lokal = ttk.Entry(r_alamat)
        self.ent_alamat_lokal.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_alamat_lokal.bind("<Return>", lambda e: self._dari_alamat("lokal"))
        self.ent_alamat_lokal.bind("<KP_Enter>", lambda e: self._dari_alamat("lokal"))
        ttk.Button(r_alamat, text="Muat", width=6, style="Secondary.TButton",
                   command=lambda: self._dari_alamat("lokal")).pack(side=tk.LEFT, padx=(4, 0))

        self.lbl_info_lokal = ttk.Label(panel_lokal, text="", style="Muted.TLabel")
        self.lbl_info_lokal.pack(fill=tk.X, pady=(4, 2))

        self.local_tree = self._bangun_tree(panel_lokal, "lokal")

        # ---------- rail aksi ----------
        rail = ttk.LabelFrame(paned_tiang, text=" Aksi ", padding=8)
        paned_tiang.add(rail, weight=0)

        self.btn_rail_unggah = ttk.Button(rail, text="Unggah →", width=13,
                                          style="Secondary.TButton", command=self._unggah)
        self.btn_rail_unggah.pack(fill=tk.X)
        self.btn_rail_unduh = ttk.Button(rail, text="← Unduh", width=13,
                                         style="Secondary.TButton", command=self._unduh)
        self.btn_rail_unduh.pack(fill=tk.X, pady=(6, 0))

        ttk.Separator(rail).pack(fill=tk.X, pady=8)

        self.btn_rail_folder = ttk.Button(rail, text="Buat Folder", width=13,
                                          style="Secondary.TButton", command=self._buat_folder)
        self.btn_rail_folder.pack(fill=tk.X)
        self.btn_rail_nama = ttk.Button(rail, text="Ubah Nama", width=13,
                                        style="Secondary.TButton", command=self._ubah_nama)
        self.btn_rail_nama.pack(fill=tk.X, pady=(6, 0))
        self.btn_rail_hapus = ttk.Button(rail, text="Hapus", width=13,
                                         style="Danger.TButton", command=self._hapus)
        self.btn_rail_hapus.pack(fill=tk.X, pady=(6, 0))

        ttk.Separator(rail).pack(fill=tk.X, pady=8)

        ttk.Checkbutton(rail, text="Sinkron navigasi", variable=self.var_sinkron,
                        style="TCheckbutton").pack(anchor="w")
        self.lbl_browser_status = ttk.Label(rail, text="Siap.", style="Muted.TLabel",
                                            wraplength=112, justify=tk.LEFT)
        self.lbl_browser_status.pack(anchor="w", fill=tk.X, pady=(10, 4))
        self.prog_browser = ttk.Progressbar(rail, mode="determinate",
                                            style="Horizontal.TProgressbar")
        self.prog_browser.pack(fill=tk.X)

        # ---------- panel server ----------
        panel_server = ttk.LabelFrame(paned_tiang, text=" Server FTP ", padding=6)
        paned_tiang.add(panel_server, weight=1)

        r_alamat_s = ttk.Frame(panel_server)
        r_alamat_s.pack(fill=tk.X)
        ttk.Button(r_alamat_s, text="Naik", width=6, style="Secondary.TButton",
                   command=self._naik_server).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(r_alamat_s, text="Root", width=6, style="Secondary.TButton",
                   command=self.refresh_remote_tree).pack(side=tk.LEFT, padx=(0, 4))
        self.ent_alamat_server = ttk.Entry(r_alamat_s)
        self.ent_alamat_server.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_alamat_server.bind("<Return>", lambda e: self._dari_alamat("server"))
        self.ent_alamat_server.bind("<KP_Enter>", lambda e: self._dari_alamat("server"))
        ttk.Button(r_alamat_s, text="Muat", width=6, style="Secondary.TButton",
                   command=lambda: self._dari_alamat("server")).pack(side=tk.LEFT, padx=(4, 0))

        r_hub = ttk.Frame(panel_server)
        r_hub.pack(fill=tk.X, pady=(4, 2))
        self.lbl_info_server = ttk.Label(r_hub, text="Terputus", style="Muted.TLabel")
        self.lbl_info_server.pack(side=tk.LEFT)
        self.btn_sambung_server = ttk.Button(r_hub, text="Hubungkan", width=12,
                                             style="Secondary.TButton",
                                             command=self.refresh_remote_tree)
        self.btn_sambung_server.pack(side=tk.RIGHT)

        self.remote_tree = self._bangun_tree(panel_server, "server")

        # ---------- panel editor (v3.0), muncul saat berkas server dipilih ----------
        self._editor_dibuka = False
        self._editor_memuat = False
        self._editor_server_id = None
        self.panel_editor = ttk.LabelFrame(paned_tiang, text=" Editor ", padding=0)
        self.editor = CodeEditor(self.panel_editor,
                                 on_save=self._simpan_dari_editor,
                                 on_close=self._sembunyikan_editor)
        self.editor.pack(fill=tk.BOTH, expand=True)

        self._bangun_menu()
        self._putuskan_server()
        self.after(100, self.refresh_local_root)

    # ---------- _bangun_tree ----------
    def _bangun_tree(self, induk, panel):
        tree = ttk.Treeview(induk, columns=("ukuran", "diubah"),
                            show="tree headings", selectmode="extended")
        tree.heading("#0", text="Nama", command=lambda: self._urutkan(panel, "nama"))
        tree.heading("ukuran", text="Ukuran", command=lambda: self._urutkan(panel, "ukuran"))
        tree.heading("diubah", text="Diubah", command=lambda: self._urutkan(panel, "diubah"))
        tree.column("#0", width=300, anchor="w")
        tree.column("ukuran", width=88, anchor="e", stretch=False)
        tree.column("diubah", width=132, anchor="center", stretch=False)

        scroll = ttk.Scrollbar(induk, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        # scrollbar dahulu supaya tak terdorong keluar saat panel sempit
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree.tag_configure("genap", background=CLR_ROW_GENAP)
        tree.tag_configure("git_baru", foreground=CLR_SUCCESS)
        tree.tag_configure("git_ubah", foreground=CLR_WARNING)
        tree.tag_configure("kecuali", foreground=CLR_DANGER, font=FONT_KECUALI)

        tree.bind("<Double-1>", lambda e: self._dobel_klik(panel))
        tree.bind("<Button-2>", lambda e: self._menu_popup(panel, e))
        tree.bind("<Button-3>", lambda e: self._menu_popup(panel, e))
        tree.bind("<<TreeviewSelect>>", lambda e, p=panel: self._pilihan_berubah(p))
        return tree

    # ---------- _bangun_menu ----------
    def _bangun_menu(self):
        self.menu_lokal = tk.Menu(self.local_tree, tearoff=0)
        self.menu_lokal.add_command(label="Unggah ke Server", command=self._unggah)
        self.menu_lokal.add_command(label="Buat Folder", command=self._buat_folder)
        self.menu_lokal.add_command(label="Ubah Nama", command=self._ubah_nama)
        self.menu_lokal.add_separator()
        self.menu_lokal.add_command(label="Hapus", command=self._hapus)
        self.menu_lokal.add_command(label="Salin jalur",
                                    command=lambda: self._salin_jalur("lokal"))

        self.menu_server = tk.Menu(self.remote_tree, tearoff=0)
        self.menu_server.add_command(label="Unduh ke Lokal", command=self._unduh)
        self.menu_server.add_command(label="Buat Folder", command=self._buat_folder)
        self.menu_server.add_command(label="Ubah Nama", command=self._ubah_nama)
        self.menu_server.add_separator()
        self.menu_server.add_command(label="Hapus", command=self._hapus)
        self.menu_server.add_command(label="Salin jalur",
                                     command=lambda: self._salin_jalur("server"))

    # ---------- status & tampilan ----------
    def _putuskan_server(self):
        try:
            if self.browser_ftp:
                self.browser_ftp.close()
        except Exception:
            pass
        self.browser_ftp = None
        self._token_server += 1
        self._server_path = self.config_data.get("REMOTE_DIR") or "/"
        self.ent_alamat_server.delete(0, tk.END)
        self.ent_alamat_server.insert(0, self._server_path)
        self.remote_tree.delete(*self.remote_tree.get_children())
        self._cache_server = []
        self._baris_atas["server"] = None
        self.remote_tree.insert("", "end", text="Belum tersambung. Tekan tombol Hubungkan.",
                                values=("", ""), tags=())
        self.lbl_info_server.config(text="Terputus")

    def refresh_local_root(self):
        """Kembalikan panel lokal ke akar proyek dan reset panel server."""
        self._putuskan_server()
        self.akar_lokal = os.path.abspath(self.config_data.get("LOCAL_DIR", "."))
        self._isi_lokal(self.akar_lokal)

    def refresh_remote_tree(self):
        """Hubungkan ke server lalu isi daftar dari REMOTE_DIR."""
        self._nav_server(self.config_data.get("REMOTE_DIR") or "/")

    # ---------- panel lokal ----------
    def _status_git(self):
        """git status --porcelain menjadi peta nama berkas -> token (baru/ubah)."""
        try:
            luar = subprocess.run(
                ["git", "-C", self.akar_lokal, "status", "--porcelain"],
                capture_output=True, text=True, timeout=8)
            peta = {}
            for garis in (luar.stdout or "").splitlines():
                if len(garis) < 4:
                    continue
                path = garis[3:].strip().strip('"')
                token = "baru" if garis[:2].strip() == "??" else "ubah"
                if path.endswith("/"):
                    path = path[:-1]
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                peta[path] = token
            return peta
        except Exception:
            return {}

    def _isi_lokal(self, jalur):
        bersih = (jalur or "").strip()
        if not bersih:
            return
        path_abs = os.path.abspath(os.path.expanduser(bersih))
        if not os.path.isdir(path_abs):
            self.lbl_info_lokal.config(text="Alamat tidak ditemukan.")
            return

        self.ent_alamat_lokal.delete(0, tk.END)
        self.ent_alamat_lokal.insert(0, path_abs)
        induk = os.path.dirname(path_abs)
        self._baris_atas["lokal"] = induk if induk != path_abs else None

        pola = self.config_data.get("EXCLUDE_PATTERNS", [])
        status = self._status_git()
        baris = []
        try:
            entris = sorted(os.scandir(path_abs),
                            key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        except OSError:
            entris = []

        for e in entris:
            jenis = TIPE_DIR if e.is_dir(follow_symlinks=False) else TIPE_FILE
            try:
                info = e.stat(follow_symlinks=False)
                ukuran = info.st_size if jenis == TIPE_FILE else None
                waktu_sort = dt.datetime.fromtimestamp(info.st_mtime).strftime("%Y%m%d%H%M%S")
                waktu_tampil = _fmt_waktu(info.st_mtime)
            except OSError:
                ukuran, waktu_sort, waktu_tampil = None, "", "-"

            tags = ()
            rel = os.path.relpath(e.path, self.akar_lokal)
            if not rel.startswith(".."):
                if should_exclude(rel, pola):
                    tags = ("kecuali",)
                else:
                    token = status.get(e.name) or status.get(e.name + "/")
                    if token == "baru":
                        tags = ("git_baru",)
                    elif token == "ubah":
                        tags = ("git_ubah",)

            baris.append({"nama": e.name, "path": e.path, "jenis": jenis,
                          "ukuran": ukuran, "waktu_sort": waktu_sort,
                          "waktu_tampil": waktu_tampil, "tags": tags})

        self._cache_lokal = baris
        self._gambar_baris("lokal")
        self.lbl_info_lokal.config(text=f"{len(baris)} item")

        if self.var_sinkron.get():
            tujuan = self._tujuan_server_dari_lokal(path_abs)
            if tujuan:
                self._nav_server(tujuan)

    def _naik_lokal(self):
        kini = self.ent_alamat_lokal.get().strip()
        induk = os.path.dirname(os.path.abspath(os.path.expanduser(kini)))
        if induk and induk != os.path.abspath(kini):
            self._isi_lokal(induk)

    def _tujuan_server_dari_lokal(self, jalur_lokal):
        """Jalur server padanan lokal untuk saklar sinkron navigasi."""
        try:
            rel = os.path.relpath(jalur_lokal, self.akar_lokal)
        except ValueError:
            return None
        if rel.startswith(".."):
            return None
        dasar = self.config_data.get("REMOTE_DIR") or "/"
        return _gabung_server(dasar, rel.replace(os.sep, "/"))

    # ---------- panel server ----------
    def _dari_alamat(self, panel):
        isian = (self.ent_alamat_lokal if panel == "lokal" else self.ent_alamat_server).get()
        if panel == "lokal":
            self._isi_lokal(isian)
        else:
            self._nav_server(isian)

    def _naik_server(self):
        induk = _induk_server(self._server_path)
        if induk:
            self._nav_server(induk)

    def _nav_server(self, jalur):
        target = "/" + (jalur or "/").strip("/")
        target = target.replace("//", "/")
        self.ent_alamat_server.delete(0, tk.END)
        self.ent_alamat_server.insert(0, target)
        self.lbl_info_server.config(text=f"Memuat {target} ...")
        self._token_server += 1
        token = self._token_server

        def kerja():
            baris, tersambung = self._baca_isi_server(target)
            self.after(0, lambda: self._setelah_isi_server(target, baris, token, tersambung))

        threading.Thread(target=kerja, daemon=True).start()

    # ---------- koneksi server ----------
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
                    self.browser_ftp = ftplib.FTP_TLS(
                        cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                    self.browser_ftp.prot_p()
                else:
                    self.browser_ftp = ftplib.FTP(
                        cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                self.browser_ftp.set_pasv(True)
                return True
            except Exception:
                log_queue.put("[ERROR] Koneksi ke server gagal. Periksa host, user, dan password di tab Konfigurasi.")
                return False

    def _baca_isi_server(self, jalur):
        """Ambil daftar isi folder server. Hasil: (baris, apakah tersambung)."""
        if not self._ensure_browser_ftp():
            return [], False
        try:
            with self.ftp_lock:
                try:
                    hasil = []
                    for nama, fakta in self.browser_ftp.mlsd(
                            path=jalur, facts=["type", "size", "modify"]):
                        if nama in (".", ".."):
                            continue
                        tipe = fakta.get("type", "")
                        if tipe in ("cdir", "pdir"):
                            continue
                        try:
                            ukuran = int(str(fakta.get("size", "")).strip())
                        except ValueError:
                            ukuran = None
                        if tipe == "dir":
                            jenis = TIPE_DIR
                            ukuran = None
                        else:
                            jenis = TIPE_FILE
                        w_sort = (str(fakta.get("modify", "")).strip())[:14]
                        if not w_sort.isdigit():
                            w_sort = ""
                        hasil.append({
                            "nama": nama, "path": _gabung_server(jalur, nama),
                            "jenis": jenis, "ukuran": ukuran,
                            "waktu_sort": w_sort, "waktu_tampil": _waktu_server(w_sort),
                            "tags": ()})
                    return hasil, True
                except Exception:
                    # cadangan: perintah LIST klasik bila server tanpa MLSD
                    hasil = []
                    self.browser_ftp.cwd(jalur)
                    garis = []
                    self.browser_ftp.retrlines("LIST", garis.append)
                    now_year = dt.date.today().year
                    for teks in garis:
                        if not teks.strip():
                            continue
                        potongan = teks.split()
                        if len(potongan) < 9:
                            continue
                        nama = " ".join(potongan[8:])
                        if nama in (".", ".."):
                            continue
                        jenis = TIPE_DIR if teks.startswith("d") else TIPE_FILE
                        try:
                            ukuran = int(potongan[4])
                        except (ValueError, TypeError):
                            ukuran = None
                        sisa = " ".join(potongan[5:8])
                        w_sort = ""
                        w_tampil = "-"
                        if jenis == TIPE_DIR:
                            ukuran = None
                        try:
                            d1 = dt.datetime.strptime(sisa, "%b %d %H:%M").replace(year=now_year)
                            w_sort = d1.strftime("%Y%m%d%H%M")
                            w_tampil = d1.strftime(FMT_WAKTU)
                        except ValueError:
                            try:
                                d2 = dt.datetime.strptime(sisa, "%b %d %Y")
                                w_sort = d2.strftime("%Y%m%d%H%M")
                                w_tampil = d2.strftime(FMT_WAKTU)
                            except (ValueError, IndexError):
                                w_sort = ""
                        hasil.append({
                            "nama": nama, "path": _gabung_server(jalur, nama),
                            "jenis": jenis, "ukuran": ukuran,
                            "waktu_sort": w_sort, "waktu_tampil": w_tampil,
                            "tags": ()})
                    return hasil, True
        except Exception:
            return [], False

    def _setelah_isi_server(self, jalur, baris, token, tersambung):
        if token != self._token_server:
            return  # abaikan hasil lama dari navigasi sebelumnya
        self._cache_server = baris
        self._baris_atas["server"] = True if jalur != "/" else None
        self._server_path = jalur
        self._gambar_baris("server")
        if tersambung:
            self.lbl_info_server.config(text=f"{len(baris)} item")
        else:
            self.lbl_info_server.config(text="Terputus")

    # ---------- render & sortir ----------
    def _urutkan(self, panel, kolom):
        kunci_lama, naik_lama = self._urutan[panel]
        naik_baru = (not naik_lama) if kunci_lama == kolom else True
        self._urutan[panel] = (kolom, naik_baru)
        self._gambar_baris(panel)

    def _gambar_baris(self, panel):
        tree = self.local_tree if panel == "lokal" else self.remote_tree
        daftar = self._cache_lokal if panel == "lokal" else self._cache_server
        kunci, naik = self._urutan[panel]

        def rahasia(b):
            if kunci == "ukuran":
                return b["ukuran"] or 0
            if kunci == "diubah":
                return b["waktu_sort"] or ""
            return b["nama"].lower()

        tree.delete(*tree.get_children())
        if self._baris_atas[panel]:
            tree.insert("", "end", iid="..", text="📁 ..", values=("", ""), tags=())

        tersortir = sorted(daftar, key=rahasia, reverse=not naik)
        atur = 0
        for b in tersortir:
            ikon = "📁" if b["jenis"] == TIPE_DIR else "📄"
            tree.insert("", "end", iid=b["path"],
                        text=f"{ikon} {b['nama']}",
                        values=(_fmt_ukuran(b["ukuran"]), b["waktu_tampil"]),
                        tags=(("genap",) if atur % 2 == 0 else ()) + b["tags"])
            atur += 1

        if not tersortir and not self._baris_atas[panel]:
            tree.insert("", "end", text="(kosong)", values=("", ""), tags=())

    # ---------- interaksi dasar ----------
    def _dobel_klik(self, panel):
        tree = self.local_tree if panel == "lokal" else self.remote_tree
        iid = tree.focus()
        if not iid:
            return
        if iid == "..":
            if panel == "lokal":
                self._naik_lokal()
            else:
                self._naik_server()
            return
        jenis = TIPE_DIR if tree.item(iid, "text").startswith("📁") else TIPE_FILE
        if jenis == TIPE_DIR:
            if panel == "lokal":
                self._isi_lokal(iid)
            else:
                self._nav_server(iid)
        elif panel == "lokal":
            self._unggah()
        else:
            self._buka_di_editor(iid)

    def _rows_terpilih(self, panel):
        tree = self.local_tree if panel == "lokal" else self.remote_tree
        hasil = []
        for iid in tree.selection():
            if iid == "..":
                continue
            jenis = TIPE_DIR if tree.item(iid, "text").startswith("📁") else TIPE_FILE
            hasil.append((iid, jenis))
        return hasil

    def _salin_jalur(self, panel):
        terpilih = self._rows_terpilih(panel)
        if not terpilih:
            self.lbl_browser_status.config(text="Belum ada objek yang dipilih.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(j for j, _ in terpilih))
        self.lbl_browser_status.config(text=f"{len(terpilih)} jalur tersalin ke clipboard.")

    # ---------- penanda sibuk ----------
    def _mulai_ops(self, total, teks):
        self._ops_sibuk = True
        for t in (self.btn_rail_unggah, self.btn_rail_unduh, self.btn_rail_folder,
                  self.btn_rail_nama, self.btn_rail_hapus):
            t.config(state=tk.DISABLED)
        self.prog_browser.config(value=0, maximum=max(total, 1))
        self.lbl_browser_status.config(text=teks)

    def _kemajuan_ops(self, kini, total, teks):
        self.prog_browser.config(value=kini, maximum=max(total, 1))
        self.lbl_browser_status.config(text=teks)

    def _selesai_ops(self, teks):
        self._ops_sibuk = False
        for t in (self.btn_rail_unggah, self.btn_rail_unduh, self.btn_rail_folder,
                  self.btn_rail_nama, self.btn_rail_hapus):
            t.config(state=tk.NORMAL)
        self.lbl_browser_status.config(text=teks or "Siap.")
        self.prog_browser.config(value=0)

    # ---------- unggah ----------
    def _unggah(self):
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Mohon tunggu.")
            return
        terpilih = self._rows_terpilih("lokal")
        if not terpilih:
            self.lbl_browser_status.config(text="Pilih berkas atau folder di panel kiri dulu.")
            return

        pola = self.config_data.get("EXCLUDE_PATTERNS", [])
        tugas = []       # (path_lokal, rel_dari_dir_server, ukuran)
        dilewati = []
        for jalur, jenis in terpilih:
            rel_akar = os.path.relpath(jalur, self.akar_lokal)
            if isinstance(rel_akar, str) and rel_akar.startswith(".."):
                self.lbl_browser_status.config(
                    text="Objek di luar folder proyek tidak bisa diunggah.")
                return
            if jenis == TIPE_FILE:
                if should_exclude(rel_akar, pola):
                    dilewati.append(rel_akar)
                else:
                    try:
                        ukuran = os.path.getsize(jalur)
                    except OSError:
                        ukuran = None
                    tugas.append((jalur, os.path.basename(jalur), ukuran))
            else:
                for abs_p, rel, ukuran in self._kumpulkan_lokal(jalur):
                    if should_exclude(rel, pola):
                        dilewati.append(rel)
                    else:
                        tugas.append((abs_p, rel, ukuran))

        if not tugas:
            self.lbl_browser_status.config(text="Tidak ada berkas yang bisa diunggah.")
            return

        self._mulai_ops(len(tugas), f"Mengunggah {len(tugas)} berkas ...")

        def kerja():
            berhasil = 0
            try:
                if not self._ensure_browser_ftp():
                    self.after(0, lambda: self._selesai_ops("Koneksi ke server gagal."))
                    return
                with self.ftp_lock:
                    for i, (abs_p, rel, _ukur) in enumerate(tugas, 1):
                        induk_rel = os.path.dirname(rel).replace(os.sep, "/")
                        if induk_rel:
                            self._pastikan_dir(self._server_path, induk_rel)
                        tujuan = _gabung_server(self._server_path, rel)
                        with open(abs_p, "rb") as berkas:
                            self.browser_ftp.storbinary(f"STOR {tujuan}", berkas)
                        berhasil += 1
                        self.after(0, lambda k=i, t=tujuan,
                                   n=len(tugas): self._kemajuan_ops(k, n, f"{t}"))
            except Exception:
                log_queue.put("[ERROR] Unggah manual berhenti di tengah jalan.")
                self.after(0, lambda: self._selesai_ops("Unggah gagal. Cek konsol."))
                return

            pesan = f"{berhasil} berkas terunggah."
            if dilewati:
                pesan += f" {len(dilewati)} berkas pengecualian dilewati."
            log_queue.put(f"[FTP] Unggah manual selesai: {berhasil} berkas.")
            self.after(0, lambda: (self._selesai_ops(pesan),
                                   self._nav_server(self._server_path)))

        threading.Thread(target=kerja, daemon=True).start()

    def _kumpulkan_lokal(self, folder):
        """Seluruh berkas di bawah folder lokal. Hasil: (abs, rel, ukuran)."""
        hasil = []
        acuan = folder.rstrip(os.sep)
        for akar, _nama, berkas in os.walk(acuan):
            for n in berkas:
                penuh = os.path.join(akar, n)
                try:
                    ukuran = os.path.getsize(penuh)
                except OSError:
                    continue
                hasil.append((penuh, os.path.relpath(penuh, acuan), ukuran))
        return hasil

    def _pastikan_dir(self, akar, rel_induk):
        kini = akar
        for bagian in [s for s in rel_induk.split("/") if s]:
            kini = _gabung_server(kini, bagian)
            try:
                self.browser_ftp.mkd(kini)
            except Exception:
                pass  # folder kemungkinan sudah ada

    # ---------- unduh ----------
    def _unduh(self):
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Mohon tunggu.")
            return
        terpilih = self._rows_terpilih("server")
        if not terpilih:
            self.lbl_browser_status.config(text="Pilih berkas di panel server dulu.")
            return
        dasar_lokal = self.ent_alamat_lokal.get().strip() or self.akar_lokal
        if not os.path.isdir(dasar_lokal):
            self.lbl_browser_status.config(text="Folder lokal aktif tidak ditemukan.")
            return

        self.lbl_browser_status.config(text="Menyusun daftar unduhan ...")

        def kerja_kumpul():
            tugas = []
            try:
                if not self._ensure_browser_ftp():
                    self.after(0, lambda: self._selesai_ops("Koneksi ke server gagal."))
                    return
                with self.ftp_lock:
                    for jalur, jenis in terpilih:
                        if jenis == TIPE_FILE:
                            try:
                                ukuran = self.browser_ftp.size(jalur)
                            except Exception:
                                ukuran = None
                            tugas.append((jalur, os.path.basename(jalur), ukuran))
                        else:
                            tugas.extend(self._kumpulkan_server(
                                jalur, os.path.basename(jalur)))
            except Exception:
                log_queue.put("[ERROR] Gagal membaca pilihan dari server.")
                self.after(0, lambda: self._selesai_ops("Penentuan daftar unduhan gagal. Cek konsol."))
                return
            self.after(0, lambda: self._unduh_lanjut(tugas, dasar_lokal))

        threading.Thread(target=kerja_kumpul, daemon=True).start()

    def _unduh_lanjut(self, tugas, dasar_lokal):
        if not tugas:
            self._selesai_ops("Tidak ada berkas dalam pilihan.")
            return
        bentrok = [t for t in tugas if os.path.exists(os.path.join(dasar_lokal, t[1]))]
        if bentrok and not messagebox.askyesno(
                "Konfirmasi",
                f"{len(bentrok)} berkas sudah ada di lokal dan akan ditimpa. Lanjutkan?"):
            self._selesai_ops("Unduhan dibatalkan.")
            return

        self._mulai_ops(len(tugas), f"Mengunduh {len(tugas)} berkas ...")

        def kerja():
            berhasil = 0
            try:
                if not self._ensure_browser_ftp():
                    self.after(0, lambda: self._selesai_ops("Koneksi ke server gagal."))
                    return
                with self.ftp_lock:
                    for i, (jalur, rel, _ukur) in enumerate(tugas, 1):
                        tujuan = os.path.join(dasar_lokal, rel)
                        os.makedirs(os.path.dirname(tujuan) or ".", exist_ok=True)
                        with open(tujuan, "wb") as berkas:
                            self.browser_ftp.retrbinary(f"RETR {jalur}", berkas.write)
                        berhasil += 1
                        self.after(0, lambda k=i, t=rel,
                                   n=len(tugas): self._kemajuan_ops(k, n, t))
            except Exception:
                log_queue.put("[ERROR] Unduhan berhenti di tengah jalan.")
                self.after(0, lambda: self._selesai_ops("Unduhan gagal. Cek konsol."))
                return

            log_queue.put(f"[FTP] Unduhan selesai: {berhasil} berkas.")
            self.after(0, lambda: (self._selesai_ops(f"{berhasil} berkas terunduh."),
                                   self._isi_lokal(dasar_lokal)))

        threading.Thread(target=kerja, daemon=True).start()

    def _kumpulkan_server(self, folder, nama_folder):
        """Seluruh berkas di bawah folder server, diambil secara rekursif."""
        hasil = []
        for nama, fakta in self.browser_ftp.mlsd(path=folder, facts=["type", "size"]):
            if nama in (".", ".."):
                continue
            tipe = fakta.get("type", "")
            if tipe in ("cdir", "pdir"):
                continue
            full = _gabung_server(folder, nama)
            if tipe == "dir":
                hasil.extend(self._kumpulkan_server(full, f"{nama_folder}/{nama}"))
            else:
                try:
                    ukuran = int(str(fakta.get("size", "")).strip())
                except ValueError:
                    ukuran = None
                hasil.append((full, f"{nama_folder}/{nama}", ukuran))
        return hasil

    # ---------- buat folder / ubah nama / hapus ----------
    def _buat_folder(self):
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Mohon tunggu.")
            return
        panel = self._panel_pilihan
        nama = simpledialog.askstring("Folder baru", "Nama folder:", parent=self)
        if not nama:
            return
        nama = nama.strip()
        if not nama or "/" in nama:
            self.lbl_browser_status.config(text="Nama folder tidak sah.")
            return

        if panel == "server":
            try:
                if not self._ensure_browser_ftp():
                    self.lbl_browser_status.config(text="Koneksi ke server gagal.")
                    return
                with self.ftp_lock:
                    self.browser_ftp.mkd(_gabung_server(self._server_path, nama))
                log_queue.put(f"[FTP] Folder server dibuat: {nama}")
                self._nav_server(self._server_path)
            except Exception:
                self.lbl_browser_status.config(
                    text="Gagal membuat folder. Kemungkinan sudah ada atau tidak diizinkan.")
            return

        dasar = self.ent_alamat_lokal.get().strip() or self.akar_lokal
        try:
            os.makedirs(os.path.join(dasar, nama), exist_ok=False)
            log_queue.put(f"[FTP] Folder lokal dibuat: {nama}")
            self._isi_lokal(dasar)
        except FileExistsError:
            self.lbl_browser_status.config(text="Folder dengan nama itu sudah ada.")
        except OSError:
            self.lbl_browser_status.config(text="Gagal membuat folder lokal.")

    def _ubah_nama(self):
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Mohon tunggu.")
            return
        panel = self._panel_pilihan
        terpilih = self._rows_terpilih(panel)
        if len(terpilih) != 1:
            self.lbl_browser_status.config(text="Pilih tepat satu objek untuk mengubah nama.")
            return
        jalur, _jenis = terpilih[0]
        lama = jalur.rsplit(os.sep if panel == "lokal" else "/", 1)[-1]
        baru = simpledialog.askstring("Ubah nama", f"Nama baru untuk {lama}:",
                                      initialvalue=lama, parent=self)
        if not baru:
            return
        baru = baru.strip()
        if not baru or baru == lama or "/" in baru:
            self.lbl_browser_status.config(text="Nama baru tidak sah.")
            return

        if panel == "server":
            try:
                if not self._ensure_browser_ftp():
                    self.lbl_browser_status.config(text="Koneksi ke server gagal.")
                    return
                induk = _induk_server(jalur) or "/"
                with self.ftp_lock:
                    self.browser_ftp.rename(jalur, _gabung_server(induk, baru))
                log_queue.put(f"[FTP] Nama berkas di server diubah menjadi: {baru}")
                self._nav_server(self._server_path)
            except Exception:
                self.lbl_browser_status.config(text="Gagal mengubah nama di server.")
            return

        try:
            os.rename(jalur, os.path.join(os.path.dirname(jalur), baru))
            self._isi_lokal(self.ent_alamat_lokal.get())
        except OSError:
            self.lbl_browser_status.config(text="Gagal mengubah nama lokal.")

    def _hapus(self):
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Mohon tunggu.")
            return
        panel = self._panel_pilihan
        terpilih = self._rows_terpilih(panel)
        if not terpilih:
            self.lbl_browser_status.config(text="Pilih objek yang akan dihapus.")
            return
        if panel == "server" and any(j == "/" for j, _ in terpilih):
            self.lbl_browser_status.config(text="Akar server tidak boleh dihapus.")
            return
        jumlah_folder = sum(1 for _, j in terpilih if j == TIPE_DIR)
        uraian = f"{len(terpilih)} objek"
        if jumlah_folder:
            uraian += f" (termasuk {jumlah_folder} folder beserta seluruh isinya)"
        if not messagebox.askyesno("Konfirmasi", f"Hapus permanen {uraian}?"):
            self.lbl_browser_status.config(text="Penghapusan dibatalkan.")
            return

        self._mulai_ops(len(terpilih), f"Menghapus {len(terpilih)} objek ...")

        def kerja():
            berhasil = 0
            try:
                if panel == "server" and not self._ensure_browser_ftp():
                    self.after(0, lambda: self._selesai_ops("Koneksi ke server gagal."))
                    return
                with self.ftp_lock:
                    for i, (jalur, jenis) in enumerate(terpilih, 1):
                        if panel == "server":
                            self._hapus_server(jalur)
                        elif jenis == TIPE_DIR:
                            shutil.rmtree(jalur)
                        else:
                            os.remove(jalur)
                        berhasil += 1
                        self.after(0, lambda k=i, n=len(terpilih): self._kemajuan_ops(
                            k, n, f"Menghapus {k}/{n} ..."))
            except Exception:
                log_queue.put("[ERROR] Penghapusan berhenti di tengah jalan.")
                self.after(0, lambda: self._selesai_ops("Penghapusan gagal. Cek konsol."))
                return

            log_queue.put(f"[FTP] {berhasil} objek dihapus permanen.")
            self.after(0, lambda: (self._selesai_ops(f"{berhasil} objek terhapus."),
                                   self._muat_ulang_panel(panel)))

        threading.Thread(target=kerja, daemon=True).start()

    def _hapus_server(self, jalur):
        if not jalur or jalur == "/":
            return
        try:
            isi = list(self.browser_ftp.mlsd(path=jalur, facts=["type"]))
        except Exception:
            isi = None
        if isi is None:
            try:
                self.browser_ftp.delete(jalur)
            except Exception:
                pass
            return
        for nama, fakta in isi:
            if nama in (".", "..") or fakta.get("type", "") in ("cdir", "pdir"):
                continue
            if fakta.get("type", "") == "dir":
                self._hapus_server(_gabung_server(jalur, nama))
            else:
                try:
                    self.browser_ftp.delete(_gabung_server(jalur, nama))
                except Exception:
                    pass
        try:
            self.browser_ftp.rmd(jalur)
        except Exception:
            pass

    def _muat_ulang_panel(self, panel):
        if panel == "lokal":
            self._isi_lokal(self.ent_alamat_lokal.get())
        else:
            self._nav_server(self._server_path)

    # ---------- menu konteks ----------
    def _menu_popup(self, panel, event):
        tree = self.local_tree if panel == "lokal" else self.remote_tree
        baris = tree.identify_row(event.y)
        if not baris:
            return ""
        if baris not in tree.selection():
            tree.selection_set(baris)
        tree.focus(baris)
        self._panel_pilihan = panel
        menu = self.menu_lokal if panel == "lokal" else self.menu_server
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    # ---------- editor teks bawaan (v3.0) ----------
    def _pilihan_berubah(self, panel):
        self._panel_pilihan = panel
        if panel != "server":
            return
        terpilih = self._rows_terpilih("server")
        if len(terpilih) != 1 or terpilih[0][1] != TIPE_FILE:
            return
        self._buka_di_editor(terpilih[0][0])

    def _buka_di_editor(self, jalur):
        if self._editor_memuat or self._ops_sibuk:
            return
        entri = next((b for b in self._cache_server if b["path"] == jalur), None)
        if entri is None or entri["jenis"] != TIPE_FILE:
            return
        if self._editor_dibuka and self.editor.path == jalur:
            return
        if entri["ukuran"] is not None and entri["ukuran"] > MAX_BYTES:
            self.lbl_browser_status.config(text="Berkas lebih dari 2 MB, tidak dibuka di editor.")
            return

        self._editor_memuat = True
        self.lbl_browser_status.config(text="Membuka " + entri["nama"] + " ...")

        def kerja():
            data, galat = None, None
            try:
                if not self._ensure_browser_ftp():
                    galat = "Koneksi ke server gagal."
                else:
                    buf = bytearray()
                    with self.ftp_lock:
                        self.browser_ftp.retrbinary("RETR " + jalur, buf.extend)
                    data = bytes(buf)
            except Exception:
                log_queue.put("[ERROR] Gagal membaca berkas dari server untuk editor.")
                galat = "Gagal membaca berkas dari server."
            self.after(0, lambda: self._editor_siap(jalur, data, galat))

        threading.Thread(target=kerja, daemon=True).start()

    def _editor_siap(self, jalur, data, galat):
        self._editor_memuat = False
        if galat:
            self.lbl_browser_status.config(text=galat)
            return
        self._tampilkan_editor()
        if self.editor.open_file(jalur, data):
            self._editor_server_id = (self.config_data.get("FTP_HOST"),
                                      self.config_data.get("FTP_USER"))
            self.lbl_browser_status.config(text="Mengedit " + os.path.basename(jalur))
        else:
            self.lbl_browser_status.config(text="Siap.")
            if self.editor.path is None:
                self._sembunyikan_editor()

    def _tampilkan_editor(self):
        if not self._editor_dibuka:
            self._paned_tiang.add(self.panel_editor, weight=2)
            self._editor_dibuka = True

    def _sembunyikan_editor(self):
        if self._editor_dibuka:
            try:
                self._paned_tiang.forget(self.panel_editor)
            except tk.TclError:
                pass
            self._editor_dibuka = False
        self._editor_server_id = None

    def _simpan_dari_editor(self, jalur, data):
        """Dipanggil editor saat Simpan. Mengembalikan False bila gagal."""
        sekarang = (self.config_data.get("FTP_HOST"), self.config_data.get("FTP_USER"))
        if sekarang != self._editor_server_id:
            messagebox.showwarning(
                "Editor",
                "Profil server sudah berganti sejak berkas dibuka. "
                "Berkas tidak disimpan agar tidak menimpa server yang salah.",
                parent=self)
            return False
        if self._ops_sibuk:
            self.lbl_browser_status.config(text="Ada operasi berjalan. Coba simpan lagi sebentar lagi.")
            return False
        if not self._ensure_browser_ftp():
            self.lbl_browser_status.config(text="Koneksi ke server gagal.")
            return False
        if not self.ftp_lock.acquire(timeout=8):
            self.lbl_browser_status.config(text="Server sedang sibuk. Coba lagi sebentar lagi.")
            return False
        try:
            self.browser_ftp.storbinary("STOR " + jalur, io.BytesIO(data))
        except Exception:
            log_queue.put("[ERROR] Gagal menyimpan " + jalur + " dari editor.")
            self.lbl_browser_status.config(text="Gagal menyimpan ke server. Cek konsol.")
            return False
        finally:
            self.ftp_lock.release()
        log_queue.put("[FTP] Berkas disimpan dari editor: " + jalur)
        self.lbl_browser_status.config(text="Tersimpan: " + os.path.basename(jalur))
        self._nav_server(self._server_path)
        return True
