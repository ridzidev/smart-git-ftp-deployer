"""Tab Panduan: tutorial penggunaan dengan daftar topik dan isi terkait."""
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext

from .theme import (CLR_BG, CLR_BORDER, CLR_DANGER, CLR_PRIMARY, CLR_SURFACE,
                    CLR_SURFACE_ALT, CLR_TEXT, CLR_TEXT_MUTED,
                    FONT_JUDUL_BESAR, FONT_LABEL, FONT_LABEL_TEBAL, NAMA_FONT)

FON_BAHAN_JUDUL = (NAMA_FONT, 12, "bold")
FON_BAHAN_POIN = (NAMA_FONT, 10)

TOPIK = [
    ("Mulai Cepat", "mulai"),
    ("Menyiapkan Profil Server", "profil"),
    ("Memilih Commit dan Rentang", "pilih"),
    ("Saring Rentang Tanggal", "tanggal"),
    ("Mode Deployment", "mode"),
    ("Jalankan dan Batalkan", "jalankan"),
    ("Peramban Berkas", "peramban"),
    ("Ekspor Riwayat ke SQL", "ekspor"),
    ("Keamanan Data Anda", "aman"),
    ("Pintasan Keyboard", "pintasan"),
]

BAHAN = {
    "mulai": (
        "Mulai Cepat",
        [
            ("p", "Empat langkah dari nol sampai deployment berjalan:"),
            ("poin", "Pasang dependensi: python3 -m pip install --user cryptography"),
            ("poin", "Jalankan aplikasi: python3 app.py"),
            ("poin", "Buka tab Konfigurasi, isi server FTP Anda, lalu tekan Simpan."),
            ("poin", "Kembali ke tab Deployment Engine, pilih komit yang ingin dikirim, tekan Mulai Deployment."),
            ("p", "Aplikasi menghitung sendiri berkas yang perlu diunggah atau dihapus di server "
                  "berdasarkan perbedaan antar komit, sehingga hanya berkas yang memang berubah yang terkirim."),
        ],
    ),
    "profil": (
        "Menyiapkan Profil Server",
        [
            ("p", "Di tab Konfigurasi isikan beberapa kolom ini per profil terpisah, jadi satu perangkat "
                  "bisa melayani banyak server:"),
            ("poin", "Host, User, dan Password FTP dari penyedia hosting Anda."),
            ("poin", "Direktori Lokal: folder proyek yang berisi folder .git."),
            ("poin", "Direktori Remote: jalur tujuan di server, misal /public_html."),
            ("poin", "FTP over TLS (FTPS): aktifkan bila server mendukung, selalu disarankan."),
            ("poin", "Pemetaan Jalur: bila folder hasil build berbeda dari folder kode, contoh dist/ tujuan public_html/app/."),
            ("p", "Password tersimpan aman secara otomatis; tidak perlu repot mengaturnya sendiri."),
        ],
    ),
    "pilih": (
        "Memilih Commit dan Rentang",
        [
            ("p", "Tabel di kiri menampilkan seluruh riwayat komit, nomor 1 adalah komit pertama di repositori."),
            ("poin", "Cara cepat layak pengeluaran bulanan: isi Dari No dan Sampai No, lalu tekan Pilih Rentang."),
            ("poin", "Tombol Komit Terbaru menyelesaikan komit paling baru dalam sekali klik."),
            ("poin", "Klik beberapa baris sambil menahan Cmd (macOS) atau Ctrl (Windows) untuk memilih sewenang-wenang."),
            ("poin", "Kolom Filter di bawah membantu mencari berdasarkan pesan komit, penulis, atau nomor."),
            ("p", "Daftar berkas di kanan bergerak mengikuti pilihan Anda: label UP berarti unggah, DEL berarti hapus di server."),
        ],
    ),
    "tanggal": (
        "Saring Rentang Tanggal",
        [
            ("p", "Bila ingin mengirim komit minggu ini saja atau semua komit bulan lalu, pakai saringan tanggal "
                  "di atas tabel komit:"),
            ("poin", "Preset siap pakai: Hari Ini, 3 Hari Terakhir, 7 Hari Terakhir, 14 Hari, 30 Hari, 90 Hari, "
                     "Minggu Ini, Bulan Ini, Bulan Lalu, Tahun Ini, Tahun Lalu."),
            ("poin", "Klik kali kalender melalui tombol 📅 di samping kolom Dari dan Sampai untuk pilih tanggal persis, "
                     "termasuk menelusuri bulan lama lewat tombol navigasi."),
            ("poin", "Hitungan hasil saringan tampil seketika, contoh 12 dari 84 komit."),
            ("poin", "Tekan Pilih Rentang Ini untuk lompat: kolom Dari No dan Sampai No terisi otomatis mengikuti hasil saringan."),
            ("p", "Preset Semua Komit mengembalikan tampilan ke kondisi penuh tanpa menyaring apa pun."),
        ],
    ),
    "mode": (
        "Mode Deployment",
        [
            ("p", "Dua cara menerapkan pilihan komit ke server:"),
            ("poin", "Mode Bertahap (Per Komit): setiap komit disinkronkan berurutan satu per satu. "
                     "Cocok saat riwayat server perlu mengikuti riwayat Git dari awal."),
            ("poin", "Mode Akumulatif: hitung seluruh perbedaan antar rentang, lalu kirimkan dalam satu batch. "
                     "Lebih cepat saat server sudah dekat dengan kondisi terbaru."),
            ("poin", "Hentikan jika ada galat: opsi keamanan, deployment berhenti segera saat satu opsi gagal."),
        ],
    ),
    "jalankan": (
        "Jalankan dan Batalkan",
        [
            ("p", "Tekan Mulai Deployment, tinjau konfirmasi, dan lihat kemajuan berjalan di baris progres "
                  "dan konsol di bawah."),
            ("poin", "Tombol Batalkan aktif saat proses berjalan; tugas yang sedang berjalan berhenti dan tidak "
                     "melanjutkan berkas berikutnya."),
            ("poin", "Konsol menampilkan warna berbeda per kejadian: biru untuk info, ungu untuk unggah, "
                     "pink untuk hapus, merah untuk galat."),
            ("poin", "Tekan F5 kapan saja untuk memuat ulang data komit dari repositori."),
        ],
    ),
    "peramban": (
        "Peramban Berkas",
        [
            ("p", "Tab ini menampilkan struktur folder lokal di kiri dan folder server di kanan."),
            ("poin", "Klik folder untuk membukanya; server dibukakan lewat koneksi FTP terpisah."),
            ("poin", "Gunakan ini untuk memeriksa hasil deployment atau sekadar mencocokkan struktur folder."),
        ],
    ),
    "ekspor": (
        "Ekspor Riwayat ke SQL",
        [
            ("p", "Tab Ekspor SQL menyusun riwayat komit menjadi pernyataan INSERT yang siap dijalankan "
                  "di basis data aplikasi Anda."),
            ("poin", "Atur App ID dan nama Branch sesuai tabel tujuan."),
            ("poin", "Pilih rentang nomor, atau gunakan saring tanggal lalu tekan Pilih Rentang Ini."),
            ("poin", "Salin Query SQL ke clipboard, atau Simpan Berkas .sql untuk dibagikan."),
        ],
    ),
    "aman": (
        "Keamanan Data Anda",
        [
            ("p", "Beberapa hal yang dijaga aplikasi tanpa perlu Anda pikirkan:"),
            ("poin", "Data konfigurasi tersimpan terenkripsi di komputer Anda; siapa pun yang menyalin "
                     "berkasnya saja tidak bisa membaca password."),
            ("poin", "Berkas .git, .env, dan berkas build dikecualikan dari proses unggah secara default."),
            ("poin", "Konfigurasi aplikasi tidak pernah ikut terunggah walau berada di folder proyek."),
            ("poin", "Aktifkan FTPS supaya jalur transfer pun terenkripsi."),
        ],
    ),
    "pintasan": (
        "Pintasan Keyboard",
        [
            ("poin", "F5: muat ulang data komit dari repositori."),
            ("poin", "Cmd/Ctrl + klik: memilih beberapa komit sekaligus di tabel."),
            ("poin", "Shift + klik: memilih rentang baris dalam sekali klik."),
            ("poin", "Esc: menutup kalender atau dropdown pilihan yang terbuka."),
            ("poin", "Di kalender: panah untuk pindah hari, Enter untuk memilih, Page Up/Down untuk ganti bulan."),
        ],
    ),
}


class PanduanTabMixin:

    # ---------- setup_tutorial_tab ----------
    def setup_tutorial_tab(self):
        wadah = ttk.Frame(self.tab_tutorial, padding=(24, 18))
        wadah.pack(fill=tk.BOTH, expand=True)

        kepala = tk.Frame(wadah, bg=CLR_BG)
        kepala.pack(fill=tk.X)
        tk.Label(kepala, text="Panduan Penggunaan", bg=CLR_BG, fg=CLR_TEXT,
                 font=FONT_JUDUL_BESAR).pack(side=tk.LEFT)
        tk.Label(kepala, text="Pilih topik di kiri untuk melihat langkahnya",
                 bg=CLR_BG, fg=CLR_TEXT_MUTED, font=FONT_LABEL).pack(side=tk.LEFT, padx=(14, 0), pady=(6, 0))

        panel_tampil = tk.Frame(wadah, bg=CLR_BORDER)
        panel_tampil.pack(fill=tk.BOTH, expand=True, pady=(14, 10))
        isi_panel = tk.Frame(panel_tampil, bg=CLR_SURFACE)
        isi_panel.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        kolom_topik = tk.Frame(isi_panel, bg=CLR_SURFACE, width=236)
        kolom_topik.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))

        gulir_topik = tk.Scrollbar(kolom_topik, orient=tk.VERTICAL)
        gulir_topik.pack(side=tk.RIGHT, fill=tk.Y)

        self.daftar_topik = tk.Listbox(
            kolom_topik,
            bg=CLR_SURFACE,
            fg=CLR_TEXT,
            selectbackground=CLR_PRIMARY,
            selectforeground="#FFFFFF",
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            font=FONT_LABEL,
            exportselection=False,
            yscrollcommand=gulir_topik.set
        )
        self.daftar_topik.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        gulir_topik.config(command=self.daftar_topik.yview)

        for judul, _kode in TOPIK:
            self.daftar_topik.insert(tk.END, f"  {judul}")

        panel_isi = tk.Frame(isi_panel, bg=CLR_SURFACE)
        panel_isi.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.teks_bahan = scrolledtext.ScrolledText(
            panel_isi,
            bg=CLR_SURFACE,
            fg=CLR_TEXT,
            insertbackground=CLR_TEXT,
            font=FONT_LABEL,
            relief="flat",
            borderwidth=0,
            wrap="word",
            padx=24,
            pady=20,
            state="disabled"
        )
        self.teks_bahan.pack(fill=tk.BOTH, expand=True)

        self.teks_bahan.tag_config("kanan", foreground=CLR_TEXT_MUTED)
        self.teks_bahan.tag_config("judul_bahan", foreground=CLR_TEXT, font=FON_BAHAN_JUDUL, spacing3=8)
        self.teks_bahan.tag_config("poin", foreground=CLR_TEXT, font=FON_BAHAN_POIN,
                                   lmargin1=26, lmargin2=44, spacing3=6)
        self.teks_bahan.tag_config("tegu", foreground=CLR_TEXT_MUTED, font=FON_BAHAN_POIN)
        self.teks_bahan.tag_config("garis", foreground=CLR_BORDER, font=FON_BAHAN_POIN)

        self.daftar_topik.bind("<<ListboxSelect>>", self._peristiwa_topik)

        # baris aksi cepat di bawah
        aksi = ttk.Frame(wadah)
        aksi.pack(fill=tk.X)
        ttk.Button(aksi, text="Buka tab Konfigurasi", style="Secondary.TButton",
                   command=self._lompak_konfigurasi).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(aksi, text="Muat Ulang Data Komit", style="Secondary.TButton",
                   command=self.refresh_git_data).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(aksi, text="Halaman Proyek di GitHub", style="Secondary.TButton",
                   command=self._buka_github).pack(side=tk.LEFT)

        self.daftar_topik.selection_set(0)
        self._tampilkan_bahan("mulai")

    # ---------- _peristiwa_topik ----------
    def _peristiwa_topik(self, event=None):
        pilih = self.daftar_topik.curselection()
        if not pilih:
            return
        self._tampilkan_bahan(TOPIK[pilih[0]][1])

    # ---------- _tampilkan_bahan ----------
    def _tampilkan_bahan(self, kode):
        judul, baris = BAHAN[kode]
        segmen = [(judul, "judul_bahan"), ("\n\n", "poin")]
        for jenis, isian in baris:
            if jenis == "poin":
                segmen.append(("  •  ", "tegu"))
                segmen.append((isian + "\n", "poin"))
            else:
                segmen.append((isian + "\n\n", "poin"))
        self.teks_bahan.config(state="normal")
        self.teks_bahan.delete("1.0", tk.END)
        for teks, tanda in segmen:
            self.teks_bahan.insert(tk.END, teks, tanda)
        self.teks_bahan.config(state="disabled")

    # ---------- aksi cepat ----------
    def _lompak_konfigurasi(self):
        try:
            self.notebook.select(self.tab_config)
        except Exception:
            pass

    def _buka_github(self):
        webbrowser.open("https://github.com/ridzidev/smart-git-ftp-deployer")
