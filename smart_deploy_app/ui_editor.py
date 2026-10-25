"""Editor teks buatan sendiri untuk Peramban Berkas (v3.0).

Hanya memakai Tkinter. Fitur: nomor baris, sorot sintaks, cari dan ganti,
indentasi otomatis, Tab/Shift+Tab untuk blok, undo/redo, dan simpan
(Ctrl/Cmd+S) lewat callback on_save(path, data_bytes).
"""

import bisect
import codecs
import os
import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

MAX_BYTES = 2 * 1024 * 1024
HIGHLIGHT_LIMIT = 400000

PAL = {
    "bg": "#0d1117", "bar": "#161b22", "border": "#30363d",
    "gutter_fg": "#6e7681", "gutter_cur": "#e6edf3",
    "fg": "#e6edf3", "muted": "#8b949e", "input": "#0d1117",
    "sel": "#264f78", "curline": "#161b22", "accent": "#58a6ff",
    "accent_bg": "#238636", "btn": "#21262d", "btn_hover": "#30363d",
    "warn": "#d29922", "match": "#9e6a03",
    "keyword": "#ff7b72", "string": "#a5d6ff", "comment": "#8b949e",
    "number": "#79c0ff", "variable": "#ffa657", "tag": "#7ee787",
}

TOKEN_TAGS = ("comment", "string", "keyword", "number", "variable", "tag")

_DQ = r'"(?:\\.|[^"\\\n])*"'
_SQ = r"'(?:\\.|[^'\\\n])*'"
_STR = _DQ + "|" + _SQ
_NUM = r"\b\d+(?:\.\d+)?\b"


def _kw(words):
    return r"\b(?:%s)\b" % "|".join(words)


_PY_KW = ("False None True and as assert async await break class continue def del "
          "elif else except finally for from global if import in is lambda nonlocal "
          "not or pass raise return try while with yield self").split()
_JS_KW = ("break case catch class const continue default delete do else export extends "
          "finally for function if import in instanceof let new return static super "
          "switch this throw try typeof var void while with yield async await of "
          "true false null undefined").split()
_PHP_KW = ("abstract and array as break case catch class clone const continue declare "
           "default do echo else elseif empty extends final finally fn for foreach "
           "function global if implements include include_once instanceof interface "
           "isset list namespace new or print private protected public require "
           "require_once return static switch throw trait try unset use var while "
           "true false null TRUE FALSE NULL").split()
_SQL_KW = ("select insert into values update set delete from where and or not null "
           "create table alter drop index primary key foreign references join left right "
           "inner outer on group by order having limit offset as distinct union all "
           "default unique auto_increment if exists in like between").split()
_SH_KW = ("if then else elif fi for while do done case esac function in return exit "
          "export local echo cd set unset").split()

SYNTAX = {
    "python": ([("comment", r"#[^\n]*"),
                ("string", r'""".*?"""|' + r"'''.*?'''|" + _STR),
                ("keyword", _kw(_PY_KW)), ("number", _NUM)], 0),
    "js": ([("comment", r"//[^\n]*|/\*.*?\*/"),
            ("string", _STR + r"|`[^`]*`"),
            ("keyword", _kw(_JS_KW)), ("number", _NUM)], 0),
    "php": ([("comment", r"//[^\n]*|#[^\n]*|/\*.*?\*/"),
             ("string", _STR), ("variable", r"\$\w+"),
             ("keyword", _kw(_PHP_KW)), ("number", _NUM)], 0),
    "html": ([("comment", r"<!--.*?-->"),
              ("string", r"(?<==)(?:\"[^\"\n]*\"|'[^'\n]*')"),
              ("tag", r"</?[A-Za-z][\w:.-]*|/?>")], 0),
    "css": ([("comment", r"/\*.*?\*/"), ("string", _STR),
             ("variable", r"[\w-]+(?=\s*:)"),
             ("number", r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms)?\b")], 0),
    "json": ([("string", _DQ), ("keyword", r"\b(?:true|false|null)\b"),
              ("number", r"-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b")], 0),
    "sql": ([("comment", r"--[^\n]*|/\*.*?\*/"), ("string", _SQ),
             ("keyword", _kw(_SQL_KW)), ("number", _NUM)], re.I),
    "shell": ([("comment", r"#[^\n]*"), ("string", _STR),
               ("variable", r"\$\{?\w+\}?"),
               ("keyword", _kw(_SH_KW)), ("number", _NUM)], 0),
    "config": ([("comment", r"[#;][^\n]*"), ("string", _STR), ("number", _NUM)], 0),
}

LANG_BY_EXT = {
    ".py": "python", ".js": "js", ".mjs": "js", ".ts": "js", ".jsx": "js",
    ".php": "php", ".phtml": "php", ".html": "html", ".htm": "html",
    ".xml": "html", ".vue": "html", ".css": "css", ".scss": "css",
    ".json": "json", ".sql": "sql", ".sh": "shell", ".bash": "shell",
    ".env": "config", ".ini": "config", ".conf": "config", ".yml": "config",
    ".yaml": "config", ".toml": "config", ".htaccess": "config",
}
LANG_LABEL = {
    "python": "Python", "js": "JavaScript", "php": "PHP", "html": "HTML",
    "css": "CSS", "json": "JSON", "sql": "SQL", "shell": "Shell",
    "config": "Konfigurasi", None: "Teks biasa",
}


def _language_for(path):
    name = os.path.basename(path or "").lower()
    if name.startswith(".env") or name in (".htaccess", ".gitignore", ".editorconfig"):
        return "config"
    return LANG_BY_EXT.get(os.path.splitext(name)[1])


def _compile(lang):
    spec = SYNTAX.get(lang)
    if not spec:
        return None
    rules, flags = spec
    parts = ["(?P<%s>%s)" % (tag, pat) for tag, pat in rules]
    return re.compile("|".join(parts), re.S | flags)


def _mono_family():
    fams = set(tkfont.families())
    for name in ("Menlo", "SF Mono", "Consolas", "DejaVu Sans Mono", "Courier New"):
        if name in fams:
            return name
    return "Courier"


def _make_button(parent, text, command, accent=False, font=None):
    base = PAL["accent_bg"] if accent else PAL["btn"]
    hover = "#2ea043" if accent else PAL["btn_hover"]
    lbl = tk.Label(parent, text=text, bg=base, fg=PAL["fg"], padx=12, pady=3,
                   cursor="hand2", font=font)
    lbl.bind("<Button-1>", lambda _e: command())
    lbl.bind("<Enter>", lambda _e: lbl.configure(bg=hover))
    lbl.bind("<Leave>", lambda _e: lbl.configure(bg=base))
    return lbl


class CodeEditor(tk.Frame):
    """Panel editor. on_save(path, data_bytes) dipanggil saat Simpan;
    kembalikan False bila gagal agar penanda 'belum disimpan' tetap ada."""

    def __init__(self, master, on_save=None, on_close=None):
        super().__init__(master, bg=PAL["bg"])
        self.on_save = on_save
        self.on_close = on_close
        self.path = None
        self.language = None
        self.encoding = "utf-8"
        self.newline = "\n"
        self._dirty = False
        self._suppress = False
        self._hl_job = None
        self._regex = None
        self._find_visible = False
        self._font = tkfont.Font(family=_mono_family(), size=12)
        self._ui = tkfont.nametofont("TkDefaultFont").copy()
        self._ui_bold = self._ui.copy()
        self._ui_bold.configure(weight="bold")
        self._build()
        self._show_empty()

    # ------------------------------------------------------------ UI
    def _build(self):
        self.bar = tk.Frame(self, bg=PAL["bar"])
        self.bar.pack(fill="x")
        self.title_var = tk.StringVar(value="Editor")
        tk.Label(self.bar, textvariable=self.title_var, bg=PAL["bar"], fg=PAL["fg"],
                 font=self._ui_bold, anchor="w").pack(side="left", padx=(10, 4), pady=6)
        self.dirty_lbl = tk.Label(self.bar, text="", bg=PAL["bar"], fg=PAL["warn"],
                                  font=self._ui)
        self.dirty_lbl.pack(side="left")
        _make_button(self.bar, "Tutup", self.close, font=self._ui).pack(side="right", padx=(4, 10), pady=5)
        _make_button(self.bar, "Cari", self.toggle_find, font=self._ui).pack(side="right", padx=4, pady=5)
        _make_button(self.bar, "Simpan", self.save, accent=True, font=self._ui).pack(side="right", padx=4, pady=5)

        # Bilah cari dan ganti (disembunyikan sampai dipanggil)
        self.find_bar = tk.Frame(self, bg=PAL["bar"])
        self.find_var = tk.StringVar()
        self.repl_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=False)
        self.find_info = tk.StringVar(value="")
        row1 = tk.Frame(self.find_bar, bg=PAL["bar"])
        row1.pack(fill="x", padx=8, pady=(6, 2))
        self.find_entry = self._entry(row1, self.find_var)
        self.find_entry.pack(side="left", fill="x", expand=True)
        self.find_entry.bind("<Return>", lambda _e: self.find_next())
        self.find_entry.bind("<Shift-Return>", lambda _e: self.find_next(backwards=True))
        self.find_entry.bind("<Escape>", lambda _e: self.hide_find())
        _make_button(row1, "▲", lambda: self.find_next(backwards=True), font=self._ui).pack(side="left", padx=(6, 0))
        _make_button(row1, "▼", self.find_next, font=self._ui).pack(side="left", padx=(4, 0))
        tk.Checkbutton(row1, text="Aa", variable=self.case_var, bg=PAL["bar"], fg=PAL["fg"],
                       selectcolor=PAL["input"], activebackground=PAL["bar"],
                       activeforeground=PAL["fg"], highlightthickness=0, bd=0,
                       font=self._ui).pack(side="left", padx=6)
        row2 = tk.Frame(self.find_bar, bg=PAL["bar"])
        row2.pack(fill="x", padx=8, pady=(2, 6))
        self.repl_entry = self._entry(row2, self.repl_var)
        self.repl_entry.pack(side="left", fill="x", expand=True)
        self.repl_entry.bind("<Escape>", lambda _e: self.hide_find())
        _make_button(row2, "Ganti", self.replace_one, font=self._ui).pack(side="left", padx=(6, 0))
        _make_button(row2, "Semua", self.replace_all, font=self._ui).pack(side="left", padx=(4, 0))
        tk.Label(row2, textvariable=self.find_info, bg=PAL["bar"], fg=PAL["muted"],
                 font=self._ui).pack(side="left", padx=8)

        # Badan editor
        self.body = tk.Frame(self, bg=PAL["bg"])
        self.body.pack(fill="both", expand=True)
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=1)
        self.gutter = tk.Canvas(self.body, width=48, bg=PAL["bg"], highlightthickness=0, bd=0)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text = tk.Text(
            self.body, wrap="none", undo=True, maxundo=-1, autoseparators=True,
            font=self._font, bg=PAL["bg"], fg=PAL["fg"], insertbackground=PAL["fg"],
            selectbackground=PAL["sel"], selectforeground=PAL["fg"],
            inactiveselectbackground=PAL["sel"], relief="flat", bd=0,
            highlightthickness=0, padx=8, pady=4, exportselection=False,
            tabs=(self._font.measure(" " * 4),),
        )
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vsb = tk.Scrollbar(self.body, orient="vertical", command=self.text.yview)
        self.hsb = tk.Scrollbar(self.body, orient="horizontal", command=self.text.xview)
        self.vsb.grid(row=0, column=2, sticky="ns")
        self.hsb.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.text.configure(yscrollcommand=self._on_yscroll, xscrollcommand=self.hsb.set)

        self.empty_lbl = tk.Label(self.body, text="Pilih berkas remote untuk mengedit",
                                  bg=PAL["bg"], fg=PAL["muted"], font=self._ui)

        # Status
        status = tk.Frame(self, bg=PAL["bar"])
        status.pack(fill="x")
        self.pos_var = tk.StringVar(value="")
        self.info_var = tk.StringVar(value="")
        tk.Label(status, textvariable=self.pos_var, bg=PAL["bar"], fg=PAL["muted"],
                 font=self._ui).pack(side="left", padx=10, pady=3)
        tk.Label(status, textvariable=self.info_var, bg=PAL["bar"], fg=PAL["muted"],
                 font=self._ui).pack(side="right", padx=10, pady=3)

        # Tag warna
        for tag in TOKEN_TAGS:
            self.text.tag_configure(tag, foreground=PAL[tag])
        self.text.tag_configure("comment", foreground=PAL["comment"])
        self.text.tag_configure("curline", background=PAL["curline"])
        self.text.tag_configure("match", background=PAL["match"])
        self.text.tag_lower("curline")
        self.text.tag_raise("sel")

        # Bindings
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_cursor)
        self.text.bind("<ButtonRelease-1>", self._on_cursor)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<Tab>", self._on_tab)
        for seq in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            try:
                self.text.bind(seq, self._on_shift_tab)
            except tk.TclError:
                pass
        self.text.bind("<Escape>", lambda _e: self.hide_find() if self._find_visible else None)
        for mod in ("Control", "Command"):
            self._bind_key("<%s-s>" % mod, self.save)
            self._bind_key("<%s-f>" % mod, self.show_find)

    def _entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, bg=PAL["input"], fg=PAL["fg"],
                        insertbackground=PAL["fg"], relief="flat", highlightthickness=1,
                        highlightbackground=PAL["border"], highlightcolor=PAL["accent"],
                        font=self._ui)

    def _bind_key(self, seq, fn):
        def handler(_e):
            fn()
            return "break"
        try:
            self.text.bind(seq, handler)
        except tk.TclError:
            pass

    # ------------------------------------------------------ keadaan
    def _show_empty(self):
        self._suppress = True
        self.path = None
        self.language = None
        self._regex = None
        self._dirty = False
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.edit_modified(False)
        self.text.edit_reset()
        self.text.configure(state="disabled")
        self.empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.title_var.set("Editor")
        self.dirty_lbl.configure(text="")
        self.pos_var.set("")
        self.info_var.set("")
        self._redraw_gutter()
        self.after_idle(self._end_suppress)

    def _end_suppress(self):
        self._suppress = False

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "Editor"
        self.title_var.set(name)
        self.dirty_lbl.configure(text="● belum disimpan" if self._dirty else "")

    def is_dirty(self):
        return self._dirty

    def confirm_discard(self):
        if not self._dirty:
            return True
        return messagebox.askyesno(
            "Editor",
            "Perubahan pada %s belum disimpan. Buang perubahan?" % os.path.basename(self.path or ""),
            parent=self, icon="warning")

    def mark_saved(self):
        self._dirty = False
        self._update_title()

    # ------------------------------------------------- buka / simpan
    def open_file(self, path, data):
        """Buka isi berkas (bytes). Mengembalikan True bila berhasil dibuka."""
        if len(data) > MAX_BYTES:
            messagebox.showwarning("Editor", "Berkas lebih dari 2 MB, tidak dibuka di editor.", parent=self)
            return False
        if b"\x00" in data[:8192]:
            messagebox.showinfo("Editor", "Berkas biner tidak dapat dibuka di editor.", parent=self)
            return False
        if not self.confirm_discard():
            return False
        enc = "utf-8-sig" if data.startswith(codecs.BOM_UTF8) else "utf-8"
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            enc = "latin-1"
            text = data.decode(enc)
        newline = "\r\n" if "\r\n" in text else "\n"
        if newline == "\r\n":
            text = text.replace("\r\n", "\n")
        self.encoding, self.newline, self.path = enc, newline, path
        self.language = _language_for(path)
        self._regex = _compile(self.language)
        self._suppress = True
        self.empty_lbl.place_forget()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_modified(False)
        self.text.edit_reset()
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")
        self._dirty = False
        self.after_idle(self._end_suppress)
        self._update_title()
        enc_label = {"utf-8-sig": "UTF-8 BOM", "utf-8": "UTF-8", "latin-1": "Latin-1"}[enc]
        self.info_var.set("%s · %s · %s" % (enc_label, "CRLF" if newline == "\r\n" else "LF",
                                           LANG_LABEL.get(self.language, "Teks biasa")))
        self._highlight()
        self._on_cursor()
        self.text.focus_set()
        return True

    def get_bytes(self):
        text = self.text.get("1.0", "end-1c")
        if self.newline != "\n":
            text = text.replace("\n", self.newline)
        return text.encode(self.encoding)

    def save(self):
        if self.path is None or self.on_save is None:
            return
        try:
            data = self.get_bytes()
        except UnicodeEncodeError as exc:
            messagebox.showerror("Editor", "Karakter tidak bisa disandikan sebagai %s:\n%s" % (self.encoding, exc),
                                 parent=self)
            return
        if self.on_save(self.path, data) is not False:
            self.mark_saved()

    def close(self):
        if not self.confirm_discard():
            return
        self._show_empty()
        if self.on_close:
            self.on_close()

    # ----------------------------------------------- event dan gambar
    def _on_yscroll(self, first, last):
        self.vsb.set(first, last)
        self._redraw_gutter()

    def _on_modified(self, _e=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self._suppress:
            return
        if not self._dirty:
            self._dirty = True
            self._update_title()
        self._schedule_highlight()
        self._on_cursor()

    def _on_cursor(self, _e=None):
        if self.path is None:
            return
        line, col = self.text.index("insert").split(".")
        self.pos_var.set("Baris %s, Kolom %d" % (line, int(col) + 1))
        self.text.tag_remove("curline", "1.0", "end")
        self.text.tag_add("curline", "insert linestart", "insert lineend+1c")
        self._redraw_gutter()

    def _redraw_gutter(self):
        c = self.gutter
        c.delete("all")
        total = int(self.text.index("end-1c").split(".")[0])
        width = self._font.measure("0") * max(3, len(str(total))) + 18
        if int(c.cget("width")) != width:
            c.configure(width=width)
        if self.path is None:
            return
        cur = int(self.text.index("insert").split(".")[0])
        idx = self.text.index("@0,0")
        last = 0
        while True:
            info = self.text.dlineinfo(idx)
            if info is None:
                break
            ln = int(idx.split(".")[0])
            if ln == last:
                break
            last = ln
            c.create_text(width - 8, info[1], anchor="ne", text=str(ln), font=self._font,
                          fill=PAL["gutter_cur"] if ln == cur else PAL["gutter_fg"])
            idx = self.text.index("%s+1line" % idx)

    def _schedule_highlight(self, delay=120):
        if self._hl_job is not None:
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(delay, self._highlight)

    def _highlight(self):
        self._hl_job = None
        for tag in TOKEN_TAGS:
            self.text.tag_remove(tag, "1.0", "end")
        if not self._regex:
            return
        data = self.text.get("1.0", "end-1c")
        if len(data) > HIGHLIGHT_LIMIT:
            return
        starts = [0]
        for m in re.finditer("\n", data):
            starts.append(m.end())

        def pos(off):
            ln = bisect.bisect_right(starts, off) - 1
            return "%d.%d" % (ln + 1, off - starts[ln])

        for m in self._regex.finditer(data):
            tag = m.lastgroup
            if tag:
                self.text.tag_add(tag, pos(m.start()), pos(m.end()))

    # ------------------------------------------------------- penyuntingan
    def _on_return(self, _e):
        if self.text.tag_ranges("sel"):
            return None
        line = self.text.get("insert linestart", "insert")
        indent = re.match(r"[ \t]*", line).group(0)
        stripped = line.rstrip()
        openers = ("{", "(", "[")
        if self.language in ("python", "config"):
            openers = openers + (":",)
        extra = "    " if stripped.endswith(openers) else ""
        self.text.insert("insert", "\n" + indent + extra)
        self.text.see("insert")
        return "break"

    def _selected_lines(self):
        try:
            first = int(self.text.index("sel.first").split(".")[0])
            end = self.text.index("sel.last")
        except tk.TclError:
            return None
        last = int(end.split(".")[0])
        if end.endswith(".0") and last > first:
            last -= 1
        return first, last

    def _on_tab(self, _e):
        rng = self._selected_lines()
        if rng is None:
            self.text.insert("insert", "    ")
            return "break"
        first, last = rng
        for ln in range(first, last + 1):
            self.text.insert("%d.0" % ln, "    ")
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", "%d.0" % first, "%d.end" % last)
        return "break"

    def _on_shift_tab(self, _e):
        rng = self._selected_lines()
        if rng is None:
            first = last = int(self.text.index("insert").split(".")[0])
        else:
            first, last = rng
        for ln in range(first, last + 1):
            head = self.text.get("%d.0" % ln, "%d.0+4c" % ln)
            if head.startswith("\t"):
                self.text.delete("%d.0" % ln, "%d.0+1c" % ln)
            else:
                n = len(head) - len(head.lstrip(" "))
                if n:
                    self.text.delete("%d.0" % ln, "%d.0+%dc" % (ln, n))
        return "break"

    # -------------------------------------------------- cari dan ganti
    def toggle_find(self):
        if self._find_visible:
            self.hide_find()
        else:
            self.show_find()

    def show_find(self):
        if not self._find_visible:
            self.find_bar.pack(fill="x", after=self.bar)
            self._find_visible = True
        try:
            sel = self.text.get("sel.first", "sel.last")
            if sel and "\n" not in sel:
                self.find_var.set(sel)
        except tk.TclError:
            pass
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")

    def hide_find(self):
        self.find_bar.pack_forget()
        self._find_visible = False
        self.find_info.set("")
        self.text.focus_set()

    def _has_sel(self):
        return bool(self.text.tag_ranges("sel"))

    def find_next(self, backwards=False):
        needle = self.find_var.get()
        if not needle or self.path is None:
            return False
        nocase = not self.case_var.get()
        if backwards:
            start = self.text.index("sel.first") if self._has_sel() else self.text.index("insert")
            idx = self.text.search(needle, start, stopindex="1.0", backwards=True, nocase=nocase)
            if not idx:
                idx = self.text.search(needle, "end", stopindex="1.0", backwards=True, nocase=nocase)
        else:
            start = self.text.index("sel.last") if self._has_sel() else self.text.index("insert")
            idx = self.text.search(needle, start, stopindex="end", nocase=nocase)
            if not idx:
                idx = self.text.search(needle, "1.0", stopindex="end", nocase=nocase)
        if not idx:
            self.find_info.set("Tidak ditemukan")
            return False
        end = "%s+%dc" % (idx, len(needle))
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", idx, end)
        self.text.mark_set("insert", idx if backwards else end)
        self.text.see(idx)
        self.find_info.set("")
        self._on_cursor()
        return True

    def replace_one(self):
        needle = self.find_var.get()
        if not needle or self.path is None:
            return
        if self._has_sel():
            chosen = self.text.get("sel.first", "sel.last")
            same = chosen == needle if self.case_var.get() else chosen.lower() == needle.lower()
            if same:
                start = self.text.index("sel.first")
                self.text.delete("sel.first", "sel.last")
                self.text.insert(start, self.repl_var.get())
        self.find_next()

    def replace_all(self):
        needle = self.find_var.get()
        if not needle or self.path is None:
            return
        repl = self.repl_var.get()
        nocase = not self.case_var.get()
        count = 0
        idx = "1.0"
        self.text.edit_separator()
        while count < 100000:
            idx = self.text.search(needle, idx, stopindex="end", nocase=nocase)
            if not idx:
                break
            self.text.delete(idx, "%s+%dc" % (idx, len(needle)))
            self.text.insert(idx, repl)
            idx = "%s+%dc" % (idx, len(repl))
            count += 1
        self.text.edit_separator()
        self.find_info.set("%d diganti" % count)
