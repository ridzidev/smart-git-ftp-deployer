"""Widget penyaring rentang tanggal: preset cepat, isian manual, dan kalender popup."""
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk

from .theme import (CLR_BORDER, CLR_DANGER, CLR_PRIMARY, CLR_PRIMARY_HOVER,
    CLR_SURFACE, CLR_SURFACE_ALT, CLR_TEXT, CLR_TEXT_MUTED)
from .ui_dropdown import TombolDropdown


NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
              "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

LABEL_HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]

# Format isian manual yang diterima selain preset
FORMAT_ISIAN = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
                "%d-%b-%Y", "%d %b %Y", "%d %B %Y")

KOSONG = "kosong"        # isian kosong -> batas tidak aktif
SAH = "sah"              # teks berhasil diurai menjadi tanggal
TIDAK_SAH = "tidak_sah"  # teks tidak dapat dipahami

DAFTAR_PRESET = [
    "Semua Komit", "Hari Ini", "3 Hari Terakhir", "7 Hari Terakhir",
    "14 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir",
    "Minggu Ini", "Bulan Ini", "Bulan Lalu", "Tahun Ini", "Tahun Lalu", "Kustom",
]


# ---------- parse_isian_tanggal ----------
def parse_isian_tanggal(teks):
    """Ubah teks bebas menjadi tanggal. Hasil: (status, date|None)."""
    bersih = (teks or "").strip()
    if not bersih:
        return KOSONG, None
    for fmt in FORMAT_ISIAN:
        try:
            return SAH, datetime.strptime(bersih, fmt).date()
        except ValueError:
            continue
    return TIDAK_SAH, None


# ---------- tanggal_komit ----------
def tanggal_komit(commit):
    """Ambil bagian tanggal (date) dari kamus komit format 'YYYY-MM-DD HH:MM:SS'."""
    try:
        return datetime.strptime(commit["date"], "%Y-%m-%d %H:%M:%S").date()
    except (KeyError, TypeError, ValueError):
        return None


class CalendarPopup(tk.Toplevel):
    """Kalender dropdown gelap: navigasi bulan/tahun, sorot rentang, dan pintasan."""

    def __init__(self, widget_jangkar, tanggal_isi, callback_pilih, ambil_endpoint, ambil_pasangan):
        super().__init__(widget_jangkar)
        self.withdraw()
        self.configure(bg=CLR_BORDER)  # kelas luar tipis sebagai bingkai

        self.callback_pilih = callback_pilih
        self.ambil_endpoint = ambil_endpoint
        self.ambil_pasangan = ambil_pasangan
        self.tanggal_fokus = tanggal_isi or date.today()
        self.bulan_tampil = date(self.tanggal_fokus.year, self.tanggal_fokus.month, 1)

        self._bangun_tampilan()
        self.overrideredirect(True)
        self.transient(widget_jangkar.winfo_toplevel())
        self._posisikan(widget_jangkar)
        self._gambar_grid()

        self.bind("<Escape>", lambda e: self._tutup())
        self.bind("<Return>", lambda e: self._pilih(self.tanggal_fokus))
        self.bind("<Left>", lambda e: self._geser_fokus(-1, 0))
        self.bind("<Right>", lambda e: self._geser_fokus(1, 0))
        self.bind("<Up>", lambda e: self._geser_fokus(0, -1))
        self.bind("<Down>", lambda e: self._geser_fokus(0, 1))
        self.bind("<Prior>", lambda e: self._nav_bulan(-1))
        self.bind("<Next>", lambda e: self._nav_bulan(1))
        self.bind("<Button-1>", self._klik_umum)
        self.bind("<FocusOut>", lambda e: self._tutup())

        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass
        try:
            self.grab_set()
        except Exception:
            pass

    # ---------- _bangun_tampilan ----------
    def _bangun_tampilan(self):
        konten = tk.Frame(self, bg=CLR_SURFACE, padx=8, pady=8)
        konten.pack(fill=tk.BOTH, expand=True)

        kepala = tk.Frame(konten, bg=CLR_SURFACE)
        kepala.pack(fill=tk.X)

        def tombol_nav(teks, sisi, perintah):
            b = tk.Label(kepala, text=teks, bg=CLR_SURFACE, fg=CLR_TEXT,
                         font=("Segoe UI", 11), padx=7, cursor="hand2")
            b.pack(side=sisi)
            b.bind("<Button-1>", lambda e: perintah())
            b.bind("<Enter>", lambda e: b.config(fg=CLR_PRIMARY))
            b.bind("<Leave>", lambda e: b.config(fg=CLR_TEXT))
            return b

        tombol_nav("‹", tk.LEFT, lambda: self._nav_bulan(-1))
        tombol_nav("«", tk.LEFT, lambda: self._nav_bulan(-12))
        tombol_nav("›", tk.RIGHT, lambda: self._nav_bulan(1))
        tombol_nav("»", tk.RIGHT, lambda: self._nav_bulan(12))

        self.lbl_judul = tk.Label(kepala, text="", bg=CLR_SURFACE, fg=CLR_TEXT,
                                  font=("Segoe UI Bold", 10))
        self.lbl_judul.pack(side=tk.LEFT, expand=True)

        self.kotak_grid = tk.Frame(konten, bg=CLR_SURFACE)
        self.kotak_grid.pack(fill=tk.X, pady=(6, 0))
        for kolom, nama in enumerate(LABEL_HARI):
            tk.Label(self.kotak_grid, text=nama, bg=CLR_SURFACE, fg=CLR_TEXT_MUTED,
                     font=("Segoe UI", 8)).grid(row=0, column=kolom, sticky="nsew", pady=(0, 2))
        self.kotak_grid.columnconfigure(tuple(range(7)), weight=1)

        self.lbl_ringkas = tk.Label(konten, text="", bg=CLR_SURFACE, fg=CLR_TEXT_MUTED,
                                    font=("Segoe UI", 8), anchor="w")
        self.lbl_ringkas.pack(fill=tk.X, pady=(8, 0))

        kaki = tk.Frame(konten, bg=CLR_SURFACE)
        kaki.pack(fill=tk.X, pady=(6, 0))

        def tombol_aksi(teks, sisi, perintah, warna=CLR_TEXT):
            b = tk.Label(kaki, text=teks, bg=CLR_SURFACE_ALT, fg=warna,
                         font=("Segoe UI", 8), padx=8, pady=3, cursor="hand2")
            b.pack(side=sisi, padx=2)
            b.bind("<Button-1>", lambda e: perintah())
            return b

        tombol_aksi("Hari ini", tk.LEFT, lambda: self._pilih(date.today()), CLR_PRIMARY)
        tombol_aksi("Hapus batas", tk.LEFT, lambda: self._pilih(None))
        tombol_aksi("Tutup", tk.RIGHT, self._tutup, CLR_TEXT_MUTED)

    # ---------- _posisikan ----------
    def _posisikan(self, jangkar):
        self.update_idletasks()
        lebar = max(self.winfo_reqwidth(), 260)
        tinggi = self.winfo_reqheight()
        x = jangkar.winfo_rootx()
        y = jangkar.winfo_rooty() + jangkar.winfo_height() + 2

        if y + tinggi > jangkar.winfo_screenheight() - 40:
            y = max(20, jangkar.winfo_rooty() - tinggi - 6)
        x = min(x, max(10, jangkar.winfo_screenwidth() - lebar - 10))
        self.geometry(f"{lebar}x{tinggi}+{x}+{y}")

    # ---------- _gambar_grid ----------
    def _gambar_grid(self):
        tahun, bulan = self.bulan_tampil.year, self.bulan_tampil.month
        for anak in self.kotak_grid.winfo_children():
            if anak.grid_info().get("row", 0) > 0:
                anak.destroy()

        self.lbl_judul.config(text=f"{NAMA_BULAN[bulan - 1]} {tahun}")

        d_edit = self.ambil_endpoint()
        d_pasangan = self.ambil_pasangan()
        batas_awal, batas_akhir = (d_edit, d_pasangan) if (d_edit and d_pasangan) else (None, None)
        if batas_awal and batas_akhir and batas_awal > batas_akhir:
            batas_awal, batas_akhir = batas_akhir, batas_awal

        hari_ini = date.today()
        pertama = date(tahun, bulan, 1)
        posisi = pertama - timedelta(days=pertama.weekday())  # mulai dari Senin

        for baris in range(6):
            for kolom in range(7):
                d = posisi + timedelta(days=baris * 7 + kolom)
                dalam_bulan = d.month == bulan

                warna_latar = CLR_SURFACE
                warna_teks = CLR_TEXT
                tebal = 0
                tebal_teks = ("Segoe UI", 9)

                if batas_awal and batas_awal <= d <= batas_akhir:
                    warna_latar = CLR_SURFACE_ALT
                if d in (d_edit, d_pasangan):
                    warna_latar = CLR_PRIMARY
                    warna_teks = "#FFFFFF"
                    tebal_teks = ("Segoe UI Bold", 9)
                if d == hari_ini:
                    if warna_latar == CLR_SURFACE:
                        warna_teks = CLR_PRIMARY_HOVER
                    tebal_teks = ("Segoe UI Bold", 9)
                if kolom == 6 and d not in (d_edit, d_pasangan):  # kolom Minggu
                    warna_teks = "#F87171"
                if not dalam_bulan:
                    if warna_latar == CLR_SURFACE:
                        warna_teks = "#48515B"

                sel = tk.Label(self.kotak_grid, text=str(d.day), width=4, pady=2,
                               bg=warna_latar, fg=warna_teks, font=tebal_teks,
                               highlightthickness=1 if d == hari_ini else 0,
                               highlightbackground=CLR_PRIMARY)
                sel.grid(row=baris + 1, column=kolom, sticky="nsew", padx=1, pady=1)
                sel.bind("<Button-1>", lambda e, dd=d: self._pilih(dd))

                if dalam_bulan and d not in (d_edit, d_pasangan):
                    latar_dasar = warna_latar
                    sel.bind("<Enter>", lambda e, w=sel: w.config(bg=CLR_PRIMARY_HOVER))
                    sel.bind("<Leave>", lambda e, w=sel, b=latar_dasar: w.config(bg=b))

        self.lbl_ringkas.config(text=self._teks_ringkas(d_edit, d_pasangan))

    # ---------- _teks_ringkas ----------
    def _teks_ringkas(self, a, b):
        fmt = lambda d: d.strftime("%d %b %Y") if d else "—"
        return f"Endpoint diedit: {fmt(a)}   •   Pasangan: {fmt(b)}"

    # ---------- _nav_bulan ----------
    def _nav_bulan(self, lonjakan):
        bulan_idx = self.bulan_tampil.month - 1 + lonjakan
        tahun, bulan_kini = divmod(bulan_idx, 12)
        tahun = self.bulan_tampil.year + tahun
        self.bulan_tampil = date(tahun, bulan_kini + 1, 1)
        self._gambar_grid()

    # ---------- _geser_fokus ----------
    def _geser_fokus(self, dx, dy):
        langkah = dx if dx else dy * 7
        self.tanggal_fokus = self.tanggal_fokus + timedelta(days=langkah)
        self.bulan_tampil = date(self.tanggal_fokus.year, self.tanggal_fokus.month, 1)
        self._gambar_grid()

    # ---------- _klik_umum ----------
    def _klik_umum(self, event):
        """Dengan grab aktif, klik di luar popup diarahkan ke jendela ini."""
        px, py = self.winfo_rootx(), self.winfo_rooty()
        lebar, tinggi = self.winfo_width(), self.winfo_height()
        dalam = (px <= event.x_root < px + lebar) and (py <= event.y_root < py + tinggi)
        if not dalam:
            self._tutup()
        return "break"

    # ---------- _pilih ----------
    def _pilih(self, nilai):
        callback = self.callback_pilih
        self._tutup()
        callback(nilai)

    # ---------- _tutup ----------
    def _tutup(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class DateRangeFilter(ttk.Frame):
    """Saringan rentang tanggal: preset cepat + dua isian tanggal (dengan kalender)."""

    def __init__(self, master, on_change=None, on_apply=None, teks_tombol="Pilih Rentang Ini"):
        super().__init__(master)

        self.on_change = on_change
        self.on_apply = on_apply
        self._rentang = (None, None)   # (dari, sampai) sebagai objek date
        self._dari_preset = False      # penanda agar dropdown tidak ditimpa "Kustom"
        self._galat_aktif = False      # status galat isian sedang ditampilkan
        self._popup = None

        ttk.Label(self, text="Rentang Tanggal:", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        self.cmb_preset = TombolDropdown(self, pilihan=DAFTAR_PRESET, nilai=DAFTAR_PRESET[0],
                                         on_pilih=self._peristiwa_preset, lebar=18)
        self.cmb_preset.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(self, text="Dari:").pack(side=tk.LEFT, padx=(0, 3))
        self.var_dari = tk.StringVar()
        self.ent_dari = ttk.Entry(self, textvariable=self.var_dari, width=11)
        self.ent_dari.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(self, text="📅", width=3, style="Secondary.TButton",
                   command=lambda: self._buka_kalender(self.ent_dari, "dari")).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(self, text="Sampai:").pack(side=tk.LEFT, padx=(0, 3))
        self.var_sampai = tk.StringVar()
        self.ent_sampai = ttk.Entry(self, textvariable=self.var_sampai, width=11)
        self.ent_sampai.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(self, text="📅", width=3, style="Secondary.TButton",
                   command=lambda: self._buka_kalender(self.ent_sampai, "sampai")).pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_status = ttk.Label(self, text="Semua komit ditampilkan.", style="Muted.TLabel")
        self.lbl_status.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        if on_apply:
            ttk.Button(self, text=teks_tombol, style="Primary.TButton",
                       command=self._panggil_terapkan).pack(side=tk.LEFT, padx=2)

        self.ent_dari.bind("<KeyRelease>", lambda e: self._perbarui())
        self.ent_sampai.bind("<KeyRelease>", lambda e: self._perbarui())
        self.ent_dari.bind("<FocusOut>", lambda e: self._perbarui())
        self.ent_sampai.bind("<FocusOut>", lambda e: self._perbarui())

    # ---------- Pemanggilan luar ----------
    def get_range(self):
        """Kembalikan (date|None, date|None) hasil saringan aktif."""
        return self._rentang

    def set_hitung(self, tampil, total, aktif):
        """Perbarui teks ringkasan hasil saringan; jangan menimpa pesan galat isian."""
        if self._galat_aktif:
            return
        if not aktif:
            self.lbl_status.config(text=f"Semua komit ({total}).", foreground=CLR_TEXT_MUTED)
        else:
            self.lbl_status.config(text=f"{tampil} dari {total} komit.", foreground=CLR_PRIMARY_HOVER)

    def set_status(self, teks, galat=False):
        self._galat_aktif = bool(galat)
        self.lbl_status.config(text=teks, foreground=CLR_DANGER if galat else CLR_TEXT_MUTED)

    def terapkan_valid(self):
        """Sinkronkan isian terbaru lalu kembalikan True bila tidak ada galat isian."""
        self._perbarui()
        return not self._galat_aktif

    def kosongkan(self):
        """Hapus seluruh batas tanggal (kembali menampilkan semua komit)."""
        self.cmb_preset.atur("Semua Komit")
        self._peristiwa_preset()

    # ---------- Penangan peristiwa ----------
    def _peristiwa_preset(self, event=None):
        hasil = self._hitung_preset(self.cmb_preset.get())
        if hasil is None:
            return  # pilihan "Kustom": biarkan isian tetap
        self._dari_preset = True
        d1, d2 = hasil
        self.var_dari.set(d1.strftime("%Y-%m-%d") if d1 else "")
        self.var_sampai.set(d2.strftime("%Y-%m-%d") if d2 else "")
        self._perbarui()

    def _hitung_preset(self, nama):
        """Kembalikan (dari, sampai) untuk preset; None untuk 'Kustom'."""
        hari = date.today()
        if nama == "Semua Komit":
            return (None, None)
        if nama == "Hari Ini":
            return (hari, hari)
        if nama == "3 Hari Terakhir":
            return (hari - timedelta(days=2), hari)
        if nama == "7 Hari Terakhir":
            return (hari - timedelta(days=6), hari)
        if nama == "14 Hari Terakhir":
            return (hari - timedelta(days=13), hari)
        if nama == "30 Hari Terakhir":
            return (hari - timedelta(days=29), hari)
        if nama == "90 Hari Terakhir":
            return (hari - timedelta(days=89), hari)
        if nama == "Minggu Ini":
            return (hari - timedelta(days=hari.weekday()), hari)
        if nama == "Bulan Ini":
            return (hari.replace(day=1), hari)
        if nama == "Bulan Lalu":
            akhir = hari.replace(day=1) - timedelta(days=1)
            return (akhir.replace(day=1), akhir)
        if nama == "Tahun Ini":
            return (date(hari.year, 1, 1), hari)
        if nama == "Tahun Lalu":
            return (date(hari.year - 1, 1, 1), date(hari.year - 1, 12, 31))
        return None

    def _perbarui(self):
        """Baca kedua isian, validasi, simpan rentang, lalu umpan balik ke pemilik."""
        st_d, d1 = parse_isian_tanggal(self.var_dari.get())
        st_s, d2 = parse_isian_tanggal(self.var_sampai.get())

        if st_d == TIDAK_SAH or st_s == TIDAK_SAH:
            self.set_status("Format tak dikenal — gunakan YYYY-MM-DD atau DD/MM/YYYY.", galat=True)
            return

        pesan = ""
        if d1 and d2 and d1 > d2:
            d1, d2 = d2, d1
            pesan = "Awal melebihi akhir — dibalik otomatis. "

        aktif = bool(d1 or d2)
        self._rentang = (d1, d2) if aktif else (None, None)

        if aktif:
            self.set_status(pesan or "Rentang aktif.", galat=bool(pesan))
        else:
            self.set_status("Semua komit ditampilkan.")

        if not aktif:
            self.cmb_preset.atur("Semua Komit")
        elif not self._dari_preset and self.cmb_preset.get() != "Kustom":
            self.cmb_preset.atur("Kustom")
        self._dari_preset = False

        if self.on_change:
            self.on_change()

    def _buka_kalender(self, entri, jenis):
        st, tgl = parse_isian_tanggal(entri.get())
        if st != SAH:
            tgl = date.today()  # isian belum valid: mulai kalender dari hari ini

        def ambil_endpoint():
            return tgl

        def ambil_pasangan():
            return self._rentang[1] if jenis == "dari" else self._rentang[0]

        def terima(nilai):
            if nilai is None:
                if jenis == "dari":
                    self.var_dari.set("")
                else:
                    self.var_sampai.set("")
            else:
                teks = nilai.strftime("%Y-%m-%d")
                if jenis == "dari":
                    self.var_dari.set(teks)
                else:
                    self.var_sampai.set(teks)
            try:
                entri.focus_set()
            except Exception:
                pass
            self._perbarui()

        self._tutup_kalender()
        popup = CalendarPopup(entri, tgl, terima, ambil_endpoint, ambil_pasangan)
        popup.bind("<Destroy>", self._peristiwa_tutup_popup, add="+")
        self._popup = popup

    def _peristiwa_tutup_popup(self, event):
        if self._popup is not None and event.widget is self._popup:
            self._popup = None

    def _tutup_kalender(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._popup._tutup()
        self._popup = None

    def _panggil_terapkan(self):
        if self.terapkan_valid() and self.on_apply:
            self.on_apply()
