"""Vendor script to copy repo-root report_module into backend during Vercel build."""

import shutil
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
repo_root = backend_dir.parent

root_report_module = repo_root / "report_module"
target_app = backend_dir / "app" / "report_module"
target_direct = backend_dir / "report_module"

if root_report_module.exists():
    shutil.copytree(root_report_module, target_app, dirs_exist_ok=True)
    shutil.copytree(root_report_module, target_direct, dirs_exist_ok=True)
    print(f"Successfully vendored {root_report_module} into backend.")
else:
    print("Root report_module not found; using existing app/report_module.")
