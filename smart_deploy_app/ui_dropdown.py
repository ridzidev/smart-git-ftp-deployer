"""Widget dropdown pilihan yang digambar sendiri.

Pengganti ttk.Combobox untuk dropdown yang daftar pilihannya harus pasti tampil.
Popdown milik ttk combobox dilayani Tk secara native dan pada sebagian build
Tk 9 macOS (aqua) daftarnya tidak muncul atau tak dapat dipilih. Widget ini
menampilkan daftar sebagai tk.Listbox di jendela kecil yang posisi dan warnanya
tentukan sendiri, sehingga aman di semua platform.
"""
import tkinter as tk
from tkinter import ttk

from .theme import CLR_BORDER, CLR_PRIMARY, CLR_SURFACE, CLR_SURFACE_ALT, CLR_TEXT, CLR_TEXT_MUTED, FONT_LABEL


class TombolDropdown(ttk.Frame):

    def __init__(self, master, pilihan=None, nilai="", on_pilih=None, lebar=24):
        super().__init__(master)

        self._pilihan = list(pilihan or [])
        self._nilai = nilai
        self.on_pilih = on_pilih      # hanya dipanggil bila pilihan datang dari pengguna
        self._dropdown = None

        self.tombol = ttk.Button(self, text=self._teks(nilai), width=lebar,
                                 style="Secondary.TButton", command=self._buka)
        self.tombol.pack(fill=tk.X, expand=True)

    # ---------- _teks ----------
    def _teks(self, nilai):
        tampil = str(nilai) or "-"
        return f"{tampil}   ▾"

    # ---------- API ----------
    def get(self):
        return self._nilai

    def atur(self, nilai, panggil=False):
        """Ganti nilai tampilan. panggil=True menyalakan lewat on_pilih juga."""
        self._nilai = nilai
        self.tombol.config(text=self._teks(nilai))
        if panggil and self.on_pilih:
            self.on_pilih()

    @property
    def pilihan(self):
        return self._pilihan

    @pilihan.setter
    def pilihan(self, daftar):
        self.atur_pilihan(daftar)

    def atur_pilihan(self, daftar):
        """Ganti isi daftar; bila nilai saat ini tak ada lagi, pakai jatah pertama."""
        self._pilihan = list(daftar)
        if self._pilihan and self._nilai not in self._pilihan:
            self.atur(self._pilihan[0])

    # ---------- Tampilkan daftar ----------
    def _buka(self):
        if self._dropdown is not None and self._dropdown.winfo_exists():
            self._tutup_dropdown()
            return
        if not self._pilihan:
            return

        dd = tk.Toplevel(self)
        dd.withdraw()
        dd.overrideredirect(True)
        dd.configure(bg=CLR_BORDER)
        dd.transient(self.winfo_toplevel())
        self._dropdown = dd

        inner = tk.Frame(dd, bg=CLR_SURFACE, padx=1, pady=1)
        inner.pack(fill=tk.BOTH, expand=True)

        daftar = tk.Listbox(
            inner,
            bg=CLR_SURFACE,
            fg=CLR_TEXT,
            selectbackground=CLR_PRIMARY,
            selectforeground="#FFFFFF",
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            font=FONT_LABEL,
            exportselection=False,
            height=min(len(self._pilihan), 12),
        )
        daftar.pack(fill=tk.BOTH, expand=True)
        for nilai in self._pilihan:
            daftar.insert(tk.END, self._teks(nilai))

        indeks_saat = self._pilihan.index(self._nilai) if self._nilai in self._pilihan else -1
        if indeks_saat >= 0:
            daftar.selection_set(indeks_saat)
            daftar.see(indeks_saat)

        dd.bind("<Escape>", lambda e: self._tutup_dropdown())
        dd.bind("<Return>", lambda e: self._terapkan(daftar))
        dd.bind("<Up>", lambda e: self._geser(daftar, -1))
        dd.bind("<Down>", lambda e: self._geser(daftar, 1))
        dd.bind("<Button-1>", self._klik_di_luar)
        daftar.bind("<ButtonRelease-1>", lambda e: self._terapkan(daftar))
        for anak in inner.winfo_children():
            anak.bind("<Button-1>", self._klik_di_luar)

        self._posisikan_lebar(dd, daftar)
        dd.deiconify()
        dd.lift()
        try:
            daftar.focus_set()
        except Exception:
            pass
        try:
            dd.grab_set()
        except Exception:
            pass
        dd.bind("<FocusOut>", lambda e: self._tutup_dropdown())

    # ---------- _posisikan_lebar ----------
    def _posisikan_lebar(self, dd, daftar):
        dd.update_idletasks()
        lebar = max(self.winfo_reqwidth(), daftar.winfo_reqwidth() + 24, 210)
        tinggi = min(len(self._pilihan), 12) * 24 + 8
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        if y + tinggi > self.winfo_screenheight() - 40:
            y = max(20, self.winfo_rooty() - tinggi - 6)
        x = min(x, max(10, self.winfo_screenwidth() - lebar - 10))
        daftar.config(height=min(len(self._pilihan), 12))
        dd.geometry(f"{lebar}x{tinggi}+{x}+{y}")

    # ---------- _geser ----------
    def _geser(self, daftar, langkah):
        saat = daftar.curselection()
        idx = (saat[0] + langkah) if saat else (0 if langkah > 0 else len(self._pilihan) - 1)
        idx = max(0, min(idx, daftar.size() - 1))
        daftar.selection_clear(0, tk.END)
        daftar.selection_set(idx)
        daftar.see(idx)

    # ---------- _terapkan ----------
    def _terapkan(self, daftar):
        saat = daftar.curselection()
        if not saat:
            return
        nilai = self._pilihan[saat[0]]
        self._tutup_dropdown()
        self.atur(nilai)
        if self.on_pilih:
            self.on_pilih()

    # ---------- _klik_di_luar ----------
    def _klik_di_luar(self, event):
        px, py = self._dropdown.winfo_rootx(), self._dropdown.winfo_rooty()
        lebar, tinggi = self._dropdown.winfo_width(), self._dropdown.winfo_height()
        dalam = (px <= event.x_root < px + lebar) and (py <= event.y_root < py + tinggi)
        if not dalam:
            self._tutup_dropdown()
            return "break"   # klik di luar: tangani di sini, jangan meneruskan
        return None          # klik di dalam: biarkan widget daftar memproses seleksi

    # ---------- _tutup_dropdown ----------
    def _tutup_dropdown(self):
        if self._dropdown is not None:
            try:
                self._dropdown.grab_release()
            except Exception:
                pass
            try:
                self._dropdown.destroy()
            except Exception:
                pass
        self._dropdown = None
