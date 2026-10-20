"""Tab Peramban Berkas: penjelajahan direktori lokal dan server FTP."""
import ftplib
import os
import threading
import tkinter as tk
from tkinter import ttk
from .config import log_queue

class BrowserTabMixin:

    # ---------- setup_browser_tab ----------
    def setup_browser_tab(self):
        paned = ttk.PanedWindow(self.tab_browser, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        local_frame = ttk.LabelFrame(paned, text=" Direktori Lokal ", padding=6)
        paned.add(local_frame, weight=1)

        self.local_tree = ttk.Treeview(local_frame, show="tree")
        self.local_tree.pack(fill=tk.BOTH, expand=True)
        self.local_tree.bind("<<TreeviewOpen>>", self.on_local_expand)

        remote_frame = ttk.LabelFrame(paned, text=" Server FTP ", padding=6)
        paned.add(remote_frame, weight=1)

        btn_box = ttk.Frame(remote_frame)
        btn_box.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_box, text="Hubungkan & Jelajahi", command=self.refresh_remote_tree, style="Secondary.TButton").pack(fill=tk.X)

        self.remote_tree = ttk.Treeview(remote_frame, show="tree")
        self.remote_tree.pack(fill=tk.BOTH, expand=True)
        self.remote_tree.bind("<<TreeviewOpen>>", self.on_remote_expand)

        self.after(100, self.refresh_local_root)

    # ---------- refresh_local_root ----------
    def refresh_local_root(self):
        self.local_tree.delete(*self.local_tree.get_children())
        p = os.path.abspath(self.config_data.get("LOCAL_DIR", "."))
        node = self.local_tree.insert("", "end", text=f"[DIR] {os.path.basename(p)}", values=(p, "dir"), open=True)
        self._populate_local_node(node, p)

    # ---------- _populate_local_node ----------
    def _populate_local_node(self, parent_node, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                tag = "[DIR]" if entry.is_dir() else "[FILE]"
                node = self.local_tree.insert(parent_node, "end", text=f"{tag} {entry.name}",
                                             values=(entry.path, "dir" if entry.is_dir() else "file"))
                if entry.is_dir():
                    self.local_tree.insert(node, "end", text="memuat...")
        except Exception:
            pass

    # ---------- on_local_expand ----------
    def on_local_expand(self, event):
        node = self.local_tree.focus()
        if not node:
            return
        path, n_type = self.local_tree.item(node, "values")
        if n_type == "dir":
            children = self.local_tree.get_children(node)
            if children and self.local_tree.item(children[0], "text") == "memuat...":
                self.local_tree.delete(*children)
                self._populate_local_node(node, path)

    # ---------- _ensure_browser_ftp ----------
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
                    self.browser_ftp = ftplib.FTP_TLS(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                    self.browser_ftp.prot_p()
                else:
                    self.browser_ftp = ftplib.FTP(cfg["FTP_HOST"], cfg["FTP_USER"], cfg["FTP_PASS"], timeout=15)
                self.browser_ftp.set_pasv(True)
                return True
            except Exception as e:
                log_queue.put(f"[ERROR] Koneksi FTP browser gagal: {e}")
                return False

    # ---------- refresh_remote_tree ----------
    def refresh_remote_tree(self):
        self.remote_tree.delete(*self.remote_tree.get_children())
        root_path = self.config_data.get("REMOTE_DIR", "/")
        if not root_path:
            root_path = "/"

        root_id = self.remote_tree.insert("", "end", text=f"[ROOT] {root_path}", values=(root_path, "dir"), open=True)
        self.remote_tree.insert(root_id, "end", text="memuat...")
        self._fetch_remote_content(root_id, root_path)

    # ---------- _fetch_remote_content ----------
    def _fetch_remote_content(self, parent_node, path):
        def worker():
            try:
                if not self._ensure_browser_ftp():
                    self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))
                    return

                with self.ftp_lock:
                    target_path = "/" + path.strip("/")
                    target_path = target_path.replace("//", "/")
                    log_queue.put(f"[FTP] Membuka: {target_path}")

                    items = []
                    try:
                        self.browser_ftp.cwd(target_path)
                        for name, facts in self.browser_ftp.mlsd():
                            if name in [".", ".."]:
                                continue
                            is_dir = facts.get("type") in ["dir", "pdir", "cdir"]
                            items.append((name, is_dir))
                    except Exception:
                        try:
                            lines = []
                            self.browser_ftp.retrlines("LIST", lines.append)
                            for line in lines:
                                if not line:
                                    continue
                                parts = line.split()
                                if len(parts) < 9:
                                    continue
                                name = " ".join(parts[8:])
                                if name in [".", ".."]:
                                    continue
                                is_dir = line.startswith("d") or "<DIR>" in line.upper()
                                items.append((name, is_dir))
                        except Exception as e2:
                            log_queue.put(f"[FTP ERROR] Gagal membaca direktori: {e2}")

                    items.sort(key=lambda x: (not x[1], x[0].lower()))

                    def fill_ui():
                        self.remote_tree.delete(*self.remote_tree.get_children(parent_node))
                        if not items:
                            self.remote_tree.insert(parent_node, "end", text="(Kosong)", values=("", "file"))
                            return

                        for name, is_dir in items:
                            tag = "[DIR]" if is_dir else "[FILE]"
                            new_path = (target_path.rstrip("/") + "/" + name).replace("//", "/")
                            node = self.remote_tree.insert(
                                parent_node,
                                "end",
                                text=f"{tag} {name}",
                                values=(new_path, "dir" if is_dir else "file")
                            )
                            if is_dir:
                                self.remote_tree.insert(node, "end", text="memuat...")

                        self.remote_tree.item(parent_node, open=True)

                    self.after(0, fill_ui)
            except Exception as e:
                log_queue.put(f"[FTP ERROR] Pembacaan gagal: {e}")
                self.after(0, lambda: self.remote_tree.delete(*self.remote_tree.get_children(parent_node)))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- on_remote_expand ----------
    def on_remote_expand(self, event):
        node = self.remote_tree.focus()
        if not node:
            return
        vals = self.remote_tree.item(node, "values")
        if not vals or len(vals) < 2:
            return

        path, n_type = vals
        if n_type == "dir":
            children = self.remote_tree.get_children(node)
            if children:
                first_text = self.remote_tree.item(children[0], "text").strip()
                if first_text == "memuat...":
                    self._fetch_remote_content(node, path)
