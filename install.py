#!/usr/bin/env python3
"""
Universal Cross-Platform Installer for speedtest-abb
Supports Linux, macOS, and Windows.
"""

import os
import shutil
import subprocess
import sys
import venv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_SCRIPT = os.path.join(SCRIPT_DIR, "speedtest_abb.py")


def print_step(msg):
    print(f"\033[1;36m==>\033[0m \033[1m{msg}\033[0m")


def print_success(msg):
    print(f"\033[1;32m✓\033[0m {msg}")


def print_warn(msg):
    print(f"\033[1;33m!\033[0m {msg}")


def install_unix():
    home = os.path.expanduser("~")
    venv_dir = os.path.join(home, ".local", "share", "speedtest-abb", "venv")
    bin_dir = os.path.join(home, ".local", "bin")
    target_exec = os.path.join(bin_dir, "speedtest-abb")
    python_bin = os.path.join(venv_dir, "bin", "python3")
    pip_bin = os.path.join(venv_dir, "bin", "pip")

    os.makedirs(os.path.dirname(venv_dir), exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)

    if not os.path.isfile(python_bin):
        print_step(f"Setting up isolated virtual environment in {venv_dir}...")
        builder = venv.EnvBuilder(with_pip=True, symlinks=True)
        builder.create(venv_dir)
    else:
        print_step(f"Found existing virtual environment in {venv_dir}.")

    print_step("Ensuring Rich is installed in user environment...")
    subprocess.check_call([pip_bin, "install", "--upgrade", "rich"])

    print_step(f"Installing speedtest-abb executable to {target_exec}...")
    target_script = os.path.join(bin_dir, "speedtest-abb.py")
    shutil.copy2(SOURCE_SCRIPT, target_script)
    os.chmod(target_script, 0o755)

    wrapper_content = f"""#!/bin/sh
exec "{python_bin}" "{target_script}" "$@"
"""
    with open(target_exec, "w") as f:
        f.write(wrapper_content)
    os.chmod(target_exec, 0o755)

    print_success(f"Installed successfully: {target_exec}")

    current_path = os.environ.get("PATH", "").split(":")
    if bin_dir not in current_path and os.path.realpath(bin_dir) not in [os.path.realpath(p) for p in current_path if os.path.exists(p)]:
        print_warn(f"Note: {bin_dir} is not in your $PATH.")
        print_warn("Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):")
        print(f"    export PATH=\"{bin_dir}:$PATH\"\n")


def install_windows():
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    app_dir = os.path.join(local_appdata, "speedtest-abb")
    venv_dir = os.path.join(app_dir, "venv")
    target_script = os.path.join(app_dir, "speedtest_abb.py")
    python_bin = os.path.join(venv_dir, "Scripts", "python.exe")
    pip_bin = os.path.join(venv_dir, "Scripts", "pip.exe")

    os.makedirs(app_dir, exist_ok=True)

    if not os.path.isfile(python_bin):
        print_step(f"Setting up isolated virtual environment in {venv_dir}...")
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_dir)
    else:
        print_step(f"Found existing virtual environment in {venv_dir}.")

    print_step("Ensuring Rich is installed in user environment...")
    subprocess.check_call([pip_bin, "install", "--upgrade", "rich"])

    shutil.copy2(SOURCE_SCRIPT, target_script)

    windows_apps = os.path.join(local_appdata, "Microsoft", "WindowsApps")
    user_bin = os.path.join(os.path.expanduser("~"), "bin")

    target_bin_dir = windows_apps if os.path.isdir(windows_apps) else user_bin
    os.makedirs(target_bin_dir, exist_ok=True)

    cmd_wrapper = os.path.join(target_bin_dir, "speedtest-abb.cmd")
    with open(cmd_wrapper, "w") as f:
        f.write(f'@echo off\n"{python_bin}" "{target_script}" %*\n')

    print_success(f"Installed speedtest-abb command to {cmd_wrapper}")


def main():
    print(f"\n\033[1;36mInstalling Aussie Broadband Speed Test CLI...\033[0m\n")

    if not os.path.isfile(SOURCE_SCRIPT):
        print(f"Error: {SOURCE_SCRIPT} not found!")
        sys.exit(1)

    if sys.platform == "win32":
        install_windows()
    else:
        install_unix()

    print(f"\n\033[1;32mInstallation Complete!\033[0m")
    print(f"You can now run: \033[1mspeedtest-abb\033[0m\n")


if __name__ == "__main__":
    main()
