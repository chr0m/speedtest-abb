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

## One-Line Quick Install

No cloning required! Just run the command below on any machine with Python 3:

### Linux & macOS (Terminal)
```bash
curl -fsSL https://raw.githubusercontent.com/chr0m/speedtest-abb/main/install.sh | bash
```

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/chr0m/speedtest-abb/main/install.ps1 | iex
```

The installer will:
1. Download the tool directly from GitHub.
2. Set up an isolated user virtual environment with `rich` (zero system pollution).
3. Put `speedtest-abb` into your PATH so it is immediately executable.

---

## Features

- **Progressive Rich Live Dashboard**: Compact, width-constrained (max 84 cols) rounded interface that updates in-place at 15 Hz and freezes cleanly on completion without duplicate output.
- **Accurate Telemetry**:
  - **Min / Avg / Max**: Tracks realistic steady-state speeds using 90th percentile peak filtering (Ookla methodology), preventing false 120+ Mbps burst readings caused by OS socket buffer fills.
  - **Live Sparklines**: Real-time unicode sparkline graph (` ▂▃▅▆▇█`) representing throughput consistency.
  - **Latency & Jitter**: Accurate TCP socket ping probe to port 8080 with automatic fallback to HTTPS.
- **Fixed Transfer Targets**: Tests **1000 MB (1 GB)** download and **100 MB** upload by default, with exact byte clamping.
- **Zero Root / Sudo Required**: Fully installs into an isolated user-space virtual environment.
- **Automation Ready**: Output clean, pipeable JSON via `--json`.

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
