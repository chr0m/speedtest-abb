# Aussie Broadband Real-Time Speed Test (`speedtest-abb`)

A modern, fast CLI speed test client designed specifically for testing network performance against official **Aussie Broadband** Ookla speedtest servers across Australia (Melbourne, Sydney, Brisbane, Adelaide, and Perth).

Works cross-platform across **Linux**, **macOS**, and **Windows**.

```text
╭───────────────────────  Aussie Broadband Speed Test  ────────────────────────╮
│                                                                              │
│  Server:     Melbourne, VIC (ID: 14670 · speed.mel.aussiebroadband.com.au)   │
│  Client IP:  159.196.76.66 (IPv4)                                            │
│              2403:5814:89a3:0:2983:351a:3dc8:bbd4 (IPv6)                     │
│                                                                              │
│  ✓ Latency:   10.3 ms  |  Min: 8.9 ms  |  Max: 12.1 ms  |  Jitter: 1.2 ms    │
│                                                                              │
│  ✓ Download: 860.90 Mbps (Avg)  |  Min: 826.6  |  Max: 909.3 Mbps            │
│              1000.0 MB / 1000 MB (100%) in 9.8s  |  Stability: ▇▇█▇▇▇▇▇▇▇    │
│                                                                              │
│  ✓ Upload:   91.14 Mbps (Avg)  |  Min: 86.2  |  Max: 96.3 Mbps               │
│              100.0 MB / 100 MB (100%) in 9.2s  |  Stability: █▇▇▇▇▇▇▇▇▇      │
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
- **Dual-Stack WAN IP Detection**: Concurrently discovers both public IPv4 and IPv6 client addresses directly from the speed test server in < 50ms, with clean single-stack fallback when IPv6 or IPv4 is disabled (e.g. VPNs).
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
