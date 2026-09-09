#!/usr/bin/env bash
set -e

BIN_DIR="$HOME/.local/bin"
SHARE_DIR="$HOME/.local/share/speedtest-abb"
VENV_DIR="$SHARE_DIR/venv"
TARGET_SCRIPT="$BIN_DIR/speedtest-abb.py"
TARGET_EXEC="$BIN_DIR/speedtest-abb"
RAW_URL="https://raw.githubusercontent.com/chr0m/speedtest-abb/main/speedtest_abb.py"

mkdir -p "$BIN_DIR"
mkdir -p "$SHARE_DIR"

echo -e "\033[1;36m==>\033[0m \033[1mInstalling Aussie Broadband Speed Test CLI...\033[0m"

# 1. Obtain speedtest_abb.py
if [ -n "$BASH_SOURCE" ] && [ -f "$(dirname "$BASH_SOURCE")/speedtest_abb.py" ]; then
    echo -e "\033[1;36m==>\033[0m Installing local speedtest_abb.py..."
    cp "$(dirname "$BASH_SOURCE")/speedtest_abb.py" "$TARGET_SCRIPT"
else
    echo -e "\033[1;36m==>\033[0m Downloading speedtest_abb.py from GitHub..."
    curl -fsSL "$RAW_URL" -o "$TARGET_SCRIPT"
fi
chmod 755 "$TARGET_SCRIPT"

# 2. Setup venv & install rich
if [ ! -f "$VENV_DIR/bin/python3" ]; then
    echo -e "\033[1;36m==>\033[0m Setting up isolated environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
else
    echo -e "\033[1;36m==>\033[0m Found existing environment in $VENV_DIR."
fi

echo -e "\033[1;36m==>\033[0m Ensuring Rich is installed in user environment..."
"$VENV_DIR/bin/pip" install --quiet --upgrade rich

# 3. Create launcher
cat << 'LAUNCHER' > "$TARGET_EXEC"
#!/bin/sh
exec "$HOME/.local/share/speedtest-abb/venv/bin/python3" "$HOME/.local/bin/speedtest-abb.py" "$@"
LAUNCHER
chmod 755 "$TARGET_EXEC"

echo -e "\033[1;32m✓\033[0m \033[1mInstalled successfully: $TARGET_EXEC\033[0m"

# PATH check
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo -e "\033[1;33m!\033[0m Note: $BIN_DIR is not in your \$PATH."
        echo -e "\033[1;33m!\033[0m Add this line to your shell profile (~/.bashrc or ~/.zshrc):"
        echo -e "    export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
        ;;
esac

echo -e "\033[1;32mAll set!\033[0m Run: \033[1mspeedtest-abb\033[0m\n"
