"""Konfigurasi aplikasi: nilai bawaan, penyimpanan profil, utilitas jalur."""
import json
import os
from pathlib import Path
from queue import Queue

APP_VERSION = "2.4"


CONFIG_FILENAME = "deploy_config.json"


DEFAULT_CONFIG = {
    "FTP_HOST": "",
    "FTP_USER": "",
    "FTP_PASS": "",
    "FTP_TLS": False,
    "LOCAL_DIR": ".",
    "REMOTE_DIR": "/",
    "EXCLUDE_PATTERNS": [
        "*.git*", ".env", "node_modules", "vendor", ".idea", ".vscode", "deploy_config.json"
    ],
    "PATH_MAPPINGS": []
}


log_queue = Queue()


def load_config_store():
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME

    default_store = {
        "active_profile": "Default",
        "profiles": {
            "Default": DEFAULT_CONFIG.copy()
        }
    }

    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "profiles" in data and isinstance(data["profiles"], dict) and data["profiles"]:
                for p_name, p_cfg in data["profiles"].items():
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(p_cfg)
                    if not merged.get("EXCLUDE_PATTERNS"):
                        merged["EXCLUDE_PATTERNS"] = list(DEFAULT_CONFIG["EXCLUDE_PATTERNS"])
                    if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                        merged["EXCLUDE_PATTERNS"] = [
                            l.strip() for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()
                        ]
                    if merged.get("PATH_MAPPINGS") is None:
                        merged["PATH_MAPPINGS"] = []
                    data["profiles"][p_name] = merged

                if data.get("active_profile") not in data["profiles"]:
                    data["active_profile"] = list(data["profiles"].keys())[0]
                return data
            else:
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                if not merged.get("EXCLUDE_PATTERNS"):
                    merged["EXCLUDE_PATTERNS"] = list(DEFAULT_CONFIG["EXCLUDE_PATTERNS"])
                if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
                    merged["EXCLUDE_PATTERNS"] = [
                        l.strip() for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()
                    ]
                if merged.get("PATH_MAPPINGS") is None:
                    merged["PATH_MAPPINGS"] = []
                return {
                    "active_profile": "Default",
                    "profiles": {"Default": merged}
                }
        except Exception as e:
            log_queue.put(f"[CONFIG] Gagal memuat berkas konfigurasi: {e}")
            return default_store
    return default_store


def save_config_store(store_dict):
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir / CONFIG_FILENAME
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(store_dict, f, indent=2, ensure_ascii=False)
        os.chmod(config_path, 0o600)  # Lindungi kredensial dari akses user lain
        log_queue.put(f"[CONFIG] Konfigurasi disimpan ke {config_path}")
        return True
    except Exception as e:
        log_queue.put(f"[CONFIG] Gagal menyimpan konfigurasi: {e}")
        return False


def should_exclude(file_path, exclude_patterns):
    path_str = Path(file_path).as_posix()
    for pattern in exclude_patterns:
        if not pattern:
            continue
        if path_str.startswith(pattern) or f"/{pattern}" in path_str:
            return True
    return False


def resolve_remote_path(local_rel_path, mappings):
    posix_path = Path(local_rel_path).as_posix()
    for mapping in mappings:
        local_prefix = mapping.get("local", "").strip()
        remote_prefix = mapping.get("remote", "").strip()
        if not local_prefix:
            continue
        if not local_prefix.endswith("/"):
            local_prefix += "/"
        if posix_path.startswith(local_prefix):
            stripped = posix_path[len(local_prefix):]
            final_path = str(Path(remote_prefix) / stripped)
            return Path(final_path).as_posix()
    return posix_path
