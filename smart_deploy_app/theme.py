"""Palet warna, keluarga huruf, dan konstanta tampilan antarmuka (tema gelap)."""
import platform


SISTEM = platform.system()

if SISTEM == "Darwin":
    NAMA_FONT = "Helvetica Neue"
    NAMA_FONT_MONO = "Menlo"
elif SISTEM == "Windows":
    NAMA_FONT = "Segoe UI"
    NAMA_FONT_MONO = "Consolas"
else:
    NAMA_FONT = "DejaVu Sans"
    NAMA_FONT_MONO = "DejaVu Sans Mono"


FONT_LABEL = (NAMA_FONT, 9)
FONT_LABEL_TEBAL = (NAMA_FONT, 9, "bold")
FONT_JUDUL = (NAMA_FONT, 10, "bold")
FONT_JUDUL_BESAR = (NAMA_FONT, 14, "bold")
FONT_LAYAR_JUDUL = (NAMA_FONT, 19, "bold")
FONT_MINI = (NAMA_FONT, 8)
FONT_MINI_TEBAL = (NAMA_FONT, 8, "bold")
FONT_NAVIGASI = (NAMA_FONT, 11)
FONT_KONSOL = (NAMA_FONT_MONO, 9)

CLR_BG = "#0D1117"
CLR_BORDER = "#30363D"
CLR_CONSOLE_BG = "#030712"
CLR_CONSOLE_TEXT = "#CBD5E1"
CLR_DANGER = "#EF4444"
CLR_PRIMARY = "#2563EB"
CLR_PRIMARY_HOVER = "#1D4ED8"
CLR_SUCCESS = "#10B981"
CLR_SURFACE = "#161B22"
CLR_SURFACE_ALT = "#21262D"
CLR_ROW_GENAP = "#10151B"
CLR_TEXT = "#E6EDF3"
CLR_TEXT_MUTED = "#8B949E"
CLR_WARNING = "#F59E0B"
CLR_ACCENT = "#7C3AED"
CLR_ACCENT_SOFT = "#34D399"
