"""Layar pembuka: identitas aplikasi singkat sebelum jendela utama tampil.

Jendela kecil tanpa bingkai di tengah layar, memudar masuk, menunggu data awal
siap, lalu memudar keluar dan menyerahkan tampilan ke jendela utama.
"""
import tkinter as tk

from .theme import CLR_ACCENT, CLR_BG, CLR_BORDER, CLR_PRIMARY, CLR_SURFACE, CLR_TEXT, CLR_TEXT_MUTED, NAMA_FONT

CLR_ACCENT_RGB = (0x7C, 0x3A, 0xED)  # nilai dasar CLR_ACCENT untuk gradasi strip

FON_JUDUL_SPLASH = (NAMA_FONT, 19, "bold")
FON_SUBJUDUL_SPLASH = (NAMA_FONT, 10)


class LayarPembuka(tk.Toplevel):

    def __init__(self, pemilik, versi, ketika_selesai):
        super().__init__(pemilik)
        self.overrideredirect(True)
        self.configure(bg=CLR_BORDER, highlightthickness=0)

        self.batas_tayang_ms = 1500
        self._waktu_terpenuhi = False
        self._utama_siap = False
        self._ketika_selesai = ketika_selesai

        lebar, tinggi = 464, 246
        x = (self.winfo_screenwidth() - lebar) // 2
        y = (self.winfo_screenheight() - tinggi) // 2 - 50
        self.geometry(f"{lebar}x{tinggi}+{x}+{y}")

        panel = tk.Frame(self, bg=CLR_BG)
        panel.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.strip = tk.Canvas(panel, height=4, bg=CLR_SURFACE, highlightthickness=0)
        self.strip.pack(fill=tk.X, padx=40, pady=(46, 30))

        tk.Label(panel, text="Smart Git-FTP Deployer", bg=CLR_BG, fg=CLR_TEXT,
                 font=FON_JUDUL_SPLASH).pack()
        tk.Label(panel, text=f"Versi {versi}", bg=CLR_BG, fg=CLR_TEXT_MUTED,
                 font=FON_SUBJUDUL_SPLASH).pack(pady=(6, 18))
        tk.Label(panel, text="created by ridzidev", bg=CLR_BG, fg=CLR_PRIMARY,
                 font=FON_SUBJUDUL_SPLASH).pack()

        kotak_muat = tk.Canvas(panel, height=4, bg=CLR_SURFACE, highlightthickness=0, bd=0)
        kotak_muat.pack(fill=tk.X, padx=40, pady=(34, 44))
        lebar_gulir = max(lebar - 80, 60)
        self._sel_senada = kotak_muat.create_rectangle(
            0, 0, int(lebar_gulir * 0.42), 4, fill=CLR_ACCENT, outline="")
        self.kotak_muat = kotak_muat
        self.lebar_gulir = lebar_gulir

        self.attributes("-alpha", 0.0)
        self.deiconify()

        try:
            self.after(30, lambda: self.attributes("-alpha", 0.55))
        except Exception:
            pass

        self.after(60, self._fade_masuk)
        self.after(110, self._gerak_muat)
        self.after(self.batas_tayang_ms, self._batas_tayang_selesai)

    # ---------- detail tampilan ----------
    def _warna_strip(self):
        lebar = max(self.strip.winfo_reqwidth(), 360)
        langkah = 3
        for kolom in range(0, lebar, langkah):
            rasio = min(kolom / lebar, 1.0)
            r = int(0x25 + (CLR_ACCENT_RGB[0] - 0x25) * rasio)
            g = int(0x63 + (CLR_ACCENT_RGB[1] - 0x63) * rasio)
            b = int(0xEB + (CLR_ACCENT_RGB[2] - 0xEB) * rasio)
            warna = f"#{r:02x}{g:02x}{b:02x}"
            self.strip.create_rectangle(kolom, 0, kolom + langkah + 1, 4, outline=warna, fill=warna)

    # ---------- animasi masuk / keluar ----------
    def _fade_masuk(self, alfa=0.55):
        tujuan = 0.97
        try:
            self.attributes("-alpha", min(alfa + 0.11, tujuan))
        except Exception:
            self.attributes("-alpha", 1.0)
            return
        if alfa + 0.11 < tujuan:
            self.after(24, lambda: self._fade_masuk(alfa + 0.11))
        else:
            try:
                self._warna_strip()
            except Exception:
                pass

    def _gerak_muat(self):
        if self._utama_siap and self._waktu_terpenuhi:
            return  # biarkan proses fade keluar yang menutup gerakan terakhir
        try:
            self.kotak_muat.move(self._sel_senada, 12, 0)
            if self.kotak_muat.coords(self._sel_senada)[0] > self.lebar_gulir:
                self.kotak_muat.move(self._sel_senada, -self.lebar_gulir - int(self.lebar_gulir * 0.42) - 12, 0)
            self.after(55, self._gerak_muat)
        except Exception:
            pass

    def _batas_tayang_selesai(self):
        self._waktu_terpenuhi = True
        self._coba_tutup()

    # ---------- sinyal dari aplikasi ----------
    def siap(self):
        """Dipanggil jendela utama ketika seluruh data awal termuat."""
        self._utama_siap = True
        self._coba_tutup()

    def _coba_tutup(self):
        if self._utama_siap and self._waktu_terpenuhi:
            self._fade_keluar()

    def _fade_keluar(self, alfa=None):
        try:
            alfa = float(self.attributes("-alpha")) if alfa is None else alfa
        except Exception:
            self._selesai()
            return
        if alfa <= 0.06:
            self._selesai()
            return
        try:
            self.attributes("-alpha", max(0.0, alfa - 0.13))
        except Exception:
            self._selesai()
            return
        self.after(18, lambda: self._fade_keluar(alfa - 0.13))

    def _selesai(self):
        try:
            self.destroy()
        except Exception:
            pass
        if self._ketika_selesai:
            self._ketika_selesai()
