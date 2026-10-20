#!/usr/bin/env python3
"""Smart Git-FTP Deployer — titik masuk aplikasi.

Jalankan dengan: python app.py
Berkas smart_deploy.py tetap tersedia sebagai pemanggil kompatibilitas.
"""
from smart_deploy_app.ui_app import App


def main():
    application = App()
    application.mainloop()


if __name__ == "__main__":
    main()
