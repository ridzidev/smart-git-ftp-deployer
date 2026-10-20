"""Pembaca repositori Git: riwayat kronologis dan berkas berubah antar commit."""
import subprocess
from pathlib import Path

from .config import log_queue, should_exclude

class GitManager:

    # ---------- __init__ ----------
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").is_dir():
            raise FileNotFoundError(f"Direktori .git tidak ditemukan pada '{self.repo_path}'.")

    # ---------- get_total_commit_count ----------
    def get_total_commit_count(self):
        command = ["git", "rev-list", "--count", "HEAD"]
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding="utf-8")
            return int(result.stdout.strip())
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Gagal menghitung komit: {e}")
            return 0

    # ---------- get_all_commits_chronological ----------
    def get_all_commits_chronological(self):
        """Mengambil seluruh komit dari awal (#1) hingga terkini (#N)."""
        command = ["git", "log", "--reverse", "--pretty=format:%H|%an|%ad|%s", "--date=format:%Y-%m-%d %H:%M:%S"]
        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, check=True, encoding="utf-8")
            commits = []
            idx = 1
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "index": idx,
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "subject": parts[3]
                    })
                    idx += 1
            return commits
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Gagal membaca riwayat kronologis: {e}")
            return []

    # ---------- get_changed_files ----------
    def get_changed_files(self, older_hash, newer_hash, exclude_patterns):
        if older_hash == newer_hash:
            command = ["git", "show", "--pretty=", "--name-status", newer_hash]
        else:
            parent_check = subprocess.run(
                ["git", "rev-parse", "--verify", f"{older_hash}^"],
                cwd=self.repo_path, capture_output=True, text=True
            )
            if parent_check.returncode == 0:
                base_ref = f"{older_hash}^"
            else:
                base_ref = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            command = ["git", "diff", "--name-status", base_ref, newer_hash]

        try:
            result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True, encoding="utf-8")
        except Exception as e:
            log_queue.put(f"[GIT ERROR] Diff gagal: {e}")
            return {"added_modified": [], "deleted": []}

        files = {"added_modified": [], "deleted": []}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0][0].upper()
            file_path_str = parts[-1]
            if should_exclude(file_path_str, exclude_patterns):
                continue
            if status in ["A", "M", "C", "R"]:
                files["added_modified"].append(file_path_str)
            elif status == "D":
                files["deleted"].append(file_path_str)
        return files
