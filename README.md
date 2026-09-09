# Aussie Broadband Real-Time Speed Test (`speedtest-abb`)

A modern, fast CLI speed test client designed specifically for testing network performance against official **Aussie Broadband** Ookla speedtest servers across Australia (Melbourne, Sydney, Brisbane, Adelaide, and Perth).

Works cross-platform across **Linux**, **macOS**, and **Windows**.

```text
╭───────────────────────  Aussie Broadband Speed Test  ────────────────────────╮
│                                                                              │
│  Server:      Melbourne, VIC (ID: 14670 · speed.mel.aussiebroadband.com.au)  │
│                                                                              │
│  ✓ Latency:    10.3 ms  |  Min: 9.7 ms  |  Max: 11.0 ms  |  Jitter: 1.2 ms   │
│                                                                              │
│  ✓ Download:   886.01 Mbps (Avg)  |  Min: 740.2  |  Max: 895.4 Mbps           │
│               1000.0 MB / 1000 MB (100%) in 9.4s  |   ▂▄▆▇█▇▇▇               │
│                                                                              │
│  ✓ Upload:     95.33 Mbps (Avg)  |  Min: 90.8   |  Max: 97.7 Mbps             │
│                100.0 MB / 100 MB (100%) in 8.4s   |   ▇█▇▆▃    ▂             │
│                                                                              │
╰────────────────────────────── ● Test Complete ───────────────────────────────╯
```

---

## Key Features

- **Progressive Rich Live Dashboard**: Compact, width-constrained (max 84 cols) rounded interface that updates in-place at 15 Hz and freezes cleanly on completion without duplicate output.
- **Accurate Telemetry**:
  - **Min / Avg / Max**: Tracks realistic steady-state speeds using 90th percentile peak filtering (Ookla methodology), preventing false 120+ Mbps burst readings caused by OS socket buffer fills.
  - **Live Sparklines**: Real-time unicode sparkline graph (` ▂▃▅▆▇█`) representing throughput consistency.
  - **Latency & Jitter**: Accurate TCP socket ping probe to port 8080 with automatic fallback to HTTPS.
- **Fixed Transfer Targets**: Tests **1000 MB (1 GB)** download and **100 MB** upload by default, with exact byte clamping.
- **Zero Root / Sudo Required**: Fully installs into an isolated user-space virtual environment.
- **Automation Ready**: Output clean, pipeable JSON via `--json`.

---

## Installation Across Machines

### 1. Linux & macOS
Prerequisite: Python 3.8+ and Git.

```bash
# Clone the repository
git clone git@github.com:chr0m/speedtest-abb.git
cd speedtest-abb

# Run installer
./install.sh
```

The installer will:
1. Create an isolated virtual environment at `~/.local/share/speedtest-abb/venv`.
2. Install `rich` inside that environment (zero system package pollution).
3. Install the executable launcher to `~/.local/bin/speedtest-abb`.

*Ensure `~/.local/bin` is in your `$PATH`.*

---

### 2. Windows (PowerShell)
Prerequisite: Python 3.8+ and Git for Windows.

```powershell
# Clone the repository
git clone git@github.com:chr0m/speedtest-abb.git
cd speedtest-abb

# Run installer
.\install.ps1
```

The installer will:
1. Create an isolated virtual environment at `%LOCALAPPDATA%\speedtest-abb\venv`.
2. Install `rich` in user-space.
3. Place `speedtest-abb.cmd` in `%LOCALAPPDATA%\Microsoft\WindowsApps` (in your user PATH by default).

---

## Initializing Your Private GitHub Repository

From this machine, push the project to your private GitHub repo:

```bash
cd ~/Projects/speedtest-abb

# Option A: Using the GitHub CLI (gh)
gh repo create speedtest-abb --private --source=. --remote=origin --push

# Option B: Using standard Git
git init
git add .
git commit -m "Initial commit of speedtest-abb"
git branch -M main
git remote add origin git@github.com:chr0m/speedtest-abb.git
git push -u origin main
```

---

## Usage

```bash
# 1. Run standard test (auto-detects fastest Aussie Broadband server)
speedtest-abb

# 2. Test against a specific city (Melbourne, Sydney, Brisbane, Adelaide, Perth)
speedtest-abb --server sydney
speedtest-abb --server brisbane

# 3. List all Aussie Broadband servers and measure latency
speedtest-abb --list-servers

# 4. Custom target sizes (e.g. 500 MB download, 50 MB upload)
speedtest-abb --download-mb 500 --upload-mb 50

# 5. Output clean JSON (for cron jobs, Home Assistant, scripts)
speedtest-abb --json

# 6. Plain text output (no rich terminal animation)
speedtest-abb --simple
```

---

## License
MIT License.
