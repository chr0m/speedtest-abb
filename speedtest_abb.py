#!/usr/bin/env python3
"""
speedtest-abb: Real-Time Speed Test for Aussie Broadband Servers

Performs live-updating network latency, download, and upload tests against
official Aussie Broadband Ookla speedtest servers across Australia.
Features a progressive Rich live dashboard with min/avg/max telemetry and sparklines,
testing 1000MB download and 100MB upload targets by default.
"""

import argparse
import atexit
import collections
import glob
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Ensure Rich from local user environment is importable if available
for venv_path in glob.glob(os.path.expanduser("~/.local/share/speedtest-abb/venv/lib/python*/site-packages")):
    if venv_path not in sys.path:
        sys.path.insert(0, venv_path)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.live import Live
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

ABB_SERVERS = {
    "melbourne": {
        "id": "14670",
        "city": "Melbourne, VIC",
        "host": "speed.mel.aussiebroadband.com.au",
        "port": 8080,
        "base_url": "https://server-14670.prod.hosts.ooklaserver.net:8080/speedtest",
    },
    "sydney": {
        "id": "15132",
        "city": "Sydney, NSW",
        "host": "speed.syd.aussiebroadband.com.au",
        "port": 8080,
        "base_url": "https://server-15132.prod.hosts.ooklaserver.net:8080/speedtest",
    },
    "brisbane": {
        "id": "15134",
        "city": "Brisbane, QLD",
        "host": "speed.bne.aussiebroadband.com.au",
        "port": 8080,
        "base_url": "https://server-15134.prod.hosts.ooklaserver.net:8080/speedtest",
    },
    "adelaide": {
        "id": "15135",
        "city": "Adelaide, SA",
        "host": "speed.ade.aussiebroadband.com.au",
        "port": 8080,
        "base_url": "https://server-15135.prod.hosts.ooklaserver.net:8080/speedtest",
    },
    "perth": {
        "id": "15136",
        "city": "Perth, WA",
        "host": "speed.per.aussiebroadband.com.au",
        "port": 8080,
        "base_url": "https://server-15136.prod.hosts.ooklaserver.net:8080/speedtest",
    },
}

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"
COLOR_CYAN = "\033[38;5;39m"
COLOR_GREEN = "\033[38;5;82m"
COLOR_BLUE = "\033[38;5;75m"
COLOR_YELLOW = "\033[38;5;220m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR_LINE = "\r\033[K"
ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def visible_len(s):
    return len(ANSI_REGEX.sub("", s))


def restore_cursor():
    if sys.stdout.isatty():
        sys.stdout.write(SHOW_CURSOR + COLOR_RESET)
        sys.stdout.flush()


atexit.register(restore_cursor)


def generate_sparkline(values, width=10, max_rate=None):
    """Generate a unicode sparkline string representing throughput consistency over time."""
    if not values:
        return " " * width
    blocks = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    # Resample or stretch values to fill exactly `width` characters
    if len(values) >= width:
        bucket_size = len(values) / width
        sampled = []
        for i in range(width):
            start = int(i * bucket_size)
            end = int((i + 1) * bucket_size)
            chunk = values[start:end] or [values[start]]
            sampled.append(sum(chunk) / len(chunk))
    elif len(values) == 1:
        sampled = values * width
    else:
        # Interpolate across width so the graph smoothly spans the full width
        sampled = []
        n = len(values)
        for i in range(width):
            idx = (i / (width - 1)) * (n - 1)
            i0 = int(idx)
            i1 = min(n - 1, i0 + 1)
            frac = idx - i0
            sampled.append(values[i0] * (1.0 - frac) + values[i1] * frac)

    high = max_rate if (max_rate and max_rate > 0) else (max(sampled) if sampled else 1.0)
    if high <= 0:
        return blocks[0] * width

    chars = []
    for v in sampled:
        ratio = max(0.0, min(1.0, v / high))
        idx = min(len(blocks) - 1, int(ratio * (len(blocks) - 1)))
        chars.append(blocks[idx])

    return "".join(chars)


class SpeedTracker:
    """Thread-safe byte tracker calculating cumulative, instantaneous, and percentile min/max rates."""

    def __init__(self, window_seconds=1.0, warmup_seconds=1.0):
        self._lock = threading.Lock()
        self.total_bytes = 0
        self.window_seconds = window_seconds
        self.warmup_seconds = warmup_seconds
        self.history = collections.deque()
        self.rate_samples = []
        self.sparkline_samples = []
        self.start_time = None
        self.end_time = None

    def start(self):
        self.start_time = time.perf_counter()

    def stop(self):
        self.end_time = time.perf_counter()

    def add_bytes(self, n):
        now = time.perf_counter()
        with self._lock:
            self.total_bytes += n
            self.history.append((now, n))
            cutoff = now - self.window_seconds
            while self.history and self.history[0][0] < cutoff:
                self.history.popleft()

    def get_stats(self):
        now = self.end_time or time.perf_counter()
        with self._lock:
            total_b = self.total_bytes
            cutoff = now - self.window_seconds
            while self.history and self.history[0][0] < cutoff:
                self.history.popleft()
            window_b = sum(b for _, b in self.history)
            history_len = len(self.history)
            oldest = self.history[0][0] if history_len > 0 else now

        elapsed = max(0.001, now - (self.start_time or now))
        avg_mbps = (total_b * 8) / (elapsed * 1_000_000) if elapsed >= 0.05 else 0.0

        if elapsed < self.window_seconds:
            # Before the sliding window has populated, use cumulative rate to avoid microsecond chunk interval spikes
            inst_mbps = avg_mbps
        else:
            window_duration = max(0.1, now - oldest)
            inst_mbps = (window_b * 8) / (window_duration * 1_000_000)

        with self._lock:
            # Capture throughput sample for the sparkline / history profile
            if not self.end_time and inst_mbps > 0.1:
                self.sparkline_samples.append(inst_mbps)

            # Capture steady-state rates after warmup period while actively running
            if not self.end_time and elapsed >= self.warmup_seconds and inst_mbps > 5.0:
                self.rate_samples.append(inst_mbps)

            if self.rate_samples:
                min_mbps = min(self.rate_samples)
                max_mbps = max(self.rate_samples)
            elif self.end_time:
                # Test finished before warmup elapsed (e.g. very small test payload)
                min_mbps = avg_mbps
                max_mbps = avg_mbps
            else:
                # Live warmup in progress: Min and Max are not yet established
                min_mbps = None
                max_mbps = None

            spark_rates = list(self.sparkline_samples) if self.sparkline_samples else [avg_mbps]

        return {
            "total_bytes": total_b,
            "elapsed": elapsed,
            "avg_mbps": avg_mbps,
            "inst_mbps": inst_mbps,
            "min_mbps": min_mbps,
            "max_mbps": max_mbps,
            "rates": spark_rates,
        }


class MeteredUploadChunk:
    """Stream reader for upload chunks that tracks bytes pushed in real time."""

    def __init__(self, payload, on_bytes, stop_event, target_bytes, tracker):
        self.payload = payload
        self.total = len(payload)
        self.offset = 0
        self.on_bytes = on_bytes
        self.stop_event = stop_event
        self.target_bytes = target_bytes
        self.tracker = tracker
        self.chunk_size = 65536

    def read(self, n=-1):
        if self.stop_event.is_set() or self.offset >= self.total:
            return b""
        rem_target = self.target_bytes - self.tracker.total_bytes
        if rem_target <= 0:
            self.stop_event.set()
            return b""
        rem_chunk = self.total - self.offset
        to_read = min(self.chunk_size, rem_chunk, rem_target)
        if n > 0:
            to_read = min(to_read, n)
        chunk = self.payload[self.offset : self.offset + to_read]
        self.offset += len(chunk)
        self.on_bytes(len(chunk))
        if self.tracker.total_bytes >= self.target_bytes:
            self.stop_event.set()
        return chunk

    def __len__(self):
        return self.total


def measure_single_ping_tcp(host, port=8080, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(b"HI\n")
            s.recv(512)
            t0 = time.perf_counter()
            s.sendall(f"PING {int(time.time() * 1000)}\n".encode("utf-8"))
            s.recv(512)
            return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None


def measure_single_ping_http(base_url, timeout=2.0):
    url = f"{base_url}/latency.txt"
    try:
        t0 = time.perf_counter()
        req = urllib.request.Request(url, headers={"User-Agent": "speedtest-abb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None


def find_best_server():
    results = {}
    for key, server in ABB_SERVERS.items():
        lat = measure_single_ping_tcp(server["host"], server["port"], timeout=1.5)
        if lat is None:
            lat = measure_single_ping_http(server["base_url"], timeout=2.0)
        if lat is not None:
            results[key] = lat
    if not results:
        return "melbourne", 0.0
    best_key = min(results, key=results.get)
    return best_key, results[best_key]


def make_ascii_bar(progress, width=12):
    filled = int(round(progress * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


# ============================================================================
# Rich Dashboard Renderer
# ============================================================================

class RichDashboard:
    """Manages the progressive live dashboard layout with fixed width."""

    def __init__(self, server, download_target_mb=1000.0, upload_target_mb=100.0):
        self.server = server
        self.console = Console()
        self.download_target_mb = download_target_mb
        self.upload_target_mb = upload_target_mb
        self.stage = "init"
        self.ping_data = None
        self.ping_live = None
        self.download_data = None
        self.download_live = None
        self.upload_data = None
        self.upload_live = None
        self.spinner_idx = 0
        self.live = Live(self.render(), console=self.console, refresh_per_second=15, transient=False)

    def start(self):
        self.live.start()

    def stop(self):
        self.live.update(self.render())
        self.live.stop()

    def update_ping_live(self, current, avg, min_l, max_l, jitter, cur_probe, total_probes):
        self.stage = "ping"
        self.spinner_idx += 1
        self.ping_live = {
            "current": current,
            "avg": avg,
            "min": min_l,
            "max": max_l,
            "jitter": jitter,
            "probe": cur_probe,
            "total": total_probes,
            "spin": SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)],
        }
        self.live.update(self.render())

    def set_ping_done(self, final_stats):
        self.ping_data = final_stats
        self.ping_live = None
        self.live.update(self.render())

    def update_download_live(self, stats, progress):
        self.stage = "download"
        self.spinner_idx += 1
        self.download_live = {
            "stats": stats,
            "progress": progress,
            "spin": SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)],
        }
        self.live.update(self.render())

    def set_download_done(self, final_stats, sparkline_rates):
        self.download_data = final_stats
        self.download_data["rates"] = sparkline_rates
        self.download_live = None
        self.live.update(self.render())

    def update_upload_live(self, stats, progress):
        self.stage = "upload"
        self.spinner_idx += 1
        self.upload_live = {
            "stats": stats,
            "progress": progress,
            "spin": SPINNER_FRAMES[self.spinner_idx % len(SPINNER_FRAMES)],
        }
        self.live.update(self.render())

    def set_upload_done(self, final_stats, sparkline_rates):
        self.upload_data = final_stats
        self.upload_data["rates"] = sparkline_rates
        self.upload_live = None
        self.stage = "done"
        self.live.update(self.render())

    def render(self):
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold", no_wrap=True)
        table.add_column(no_wrap=True)

        # 1. Server Row
        server_str = f"[bold cyan]{self.server['city']}[/bold cyan] [dim](ID: {self.server['id']} · {self.server['host']})[/dim]"
        table.add_row("[dim]Server:[/dim]", server_str)
        table.add_row("", "")

        # 2. Ping Row
        if self.ping_data:
            p = self.ping_data
            ping_val = f"[bold yellow]{p['avg']:5.1f} ms[/bold yellow]  [dim]|[/dim]  Min: {p['min']:.1f} ms  [dim]|[/dim]  Max: {p['max']:.1f} ms  [dim]|[/dim]  Jitter: [yellow]{p['jitter']:.1f} ms[/yellow]"
            table.add_row("[bold green]✓ Latency:[/bold green]", ping_val)
        elif self.ping_live:
            pl = self.ping_live
            ping_val = (
                f"[yellow]{pl['spin']} Measuring...[/yellow]  [bold yellow]{pl['current']:5.1f} ms[/bold yellow]  "
                f"[dim]|[/dim]  Avg: {pl['avg']:5.1f} ms  [dim]|[/dim]  Jitter: {pl['jitter']:4.1f} ms  "
                f"[dim]({pl['probe']}/{pl['total']})[/dim]"
            )
            table.add_row("[yellow]⠋ Latency:[/yellow]", ping_val)
        else:
            table.add_row("[dim]○ Latency:[/dim]", "[dim]Waiting...[/dim]")
        table.add_row("", "")

        # 3. Download Row
        if self.download_data:
            d = self.download_data
            raw_mb = d["bytes"] / (1024 * 1024)
            mb = min(self.download_target_mb, raw_mb)
            spark = generate_sparkline(d.get("rates", []), width=10, max_rate=d.get("max_mbps"))
            pct = 100.0 if raw_mb >= self.download_target_mb else (mb / self.download_target_mb) * 100.0
            dl_l1 = (
                f"[bold green]{d['avg_mbps']:7.2f} Mbps[/bold green] [dim](Avg)[/dim]  [dim]|[/dim]  "
                f"Min: {d['min_mbps']:5.1f}  [dim]|[/dim]  Max: {d['max_mbps']:5.1f} Mbps"
            )
            dl_l2 = (
                f"[dim]{mb:.1f} MB / {self.download_target_mb:.0f} MB ({pct:.0f}%) in {d['elapsed_sec']:.1f}s[/dim]  "
                f"[dim]|[/dim]  [dim]Stability:[/dim] [bold green]{spark}[/bold green]"
            )
            table.add_row("[bold green]✓ Download:[/bold green]", f"{dl_l1}\n{dl_l2}")
        elif self.download_live:
            dl = self.download_live
            st = dl["stats"]
            raw_mb = st["total_bytes"] / (1024 * 1024)
            mb = min(self.download_target_mb, raw_mb)
            bar = make_ascii_bar(dl["progress"], width=8)
            spark = generate_sparkline(st.get("rates", []), width=10, max_rate=st.get("max_mbps"))
            pct = dl["progress"] * 100.0
            min_str = f"Min: {st['min_mbps']:5.1f}" if st["min_mbps"] is not None else "Min:    --"
            max_str = f"Max: {st['max_mbps']:5.1f}" if st["max_mbps"] is not None else "Max:    --"
            dl_l1 = (
                f"[bold green]{st['inst_mbps']:7.2f} Mbps[/bold green] [dim](Avg {st['avg_mbps']:5.1f})[/dim]  "
                f"[dim]|[/dim]  {min_str}  [dim]|[/dim]  {max_str}"
            )
            dl_l2 = (
                f"[{bar}] {pct:4.1f}% [dim]({mb:.0f}/{self.download_target_mb:.0f} MB)[/dim]  "
                f"[dim]|[/dim]  [dim]Stability:[/dim] [green]{spark}[/green]"
            )
            table.add_row(f"[green]{dl['spin']} Download:[/green]", f"{dl_l1}\n{dl_l2}")
        else:
            table.add_row("[dim]○ Download:[/dim]", f"[dim]Target: {self.download_target_mb:.0f} MB[/dim]")
        table.add_row("", "")

        # 4. Upload Row
        if self.upload_data:
            u = self.upload_data
            raw_mb = u["bytes"] / (1024 * 1024)
            mb = min(self.upload_target_mb, raw_mb)
            spark = generate_sparkline(u.get("rates", []), width=10, max_rate=u.get("max_mbps"))
            pct = 100.0 if raw_mb >= self.upload_target_mb else (mb / self.upload_target_mb) * 100.0
            ul_l1 = (
                f"[bold blue]{u['avg_mbps']:7.2f} Mbps[/bold blue] [dim](Avg)[/dim]  [dim]|[/dim]  "
                f"Min: {u['min_mbps']:5.1f}  [dim]|[/dim]  Max: {u['max_mbps']:5.1f} Mbps"
            )
            ul_l2 = (
                f"[dim]{mb:.1f} MB / {self.upload_target_mb:.0f} MB ({pct:.0f}%) in {u['elapsed_sec']:.1f}s[/dim]  "
                f"[dim]|[/dim]  [dim]Stability:[/dim] [bold blue]{spark}[/bold blue]"
            )
            table.add_row("[bold green]✓ Upload:[/bold green]", f"{ul_l1}\n{ul_l2}")
        elif self.upload_live:
            ul = self.upload_live
            st = ul["stats"]
            raw_mb = st["total_bytes"] / (1024 * 1024)
            mb = min(self.upload_target_mb, raw_mb)
            bar = make_ascii_bar(ul["progress"], width=8)
            spark = generate_sparkline(st.get("rates", []), width=10, max_rate=st.get("max_mbps"))
            pct = ul["progress"] * 100.0
            min_str = f"Min: {st['min_mbps']:5.1f}" if st["min_mbps"] is not None else "Min:    --"
            max_str = f"Max: {st['max_mbps']:5.1f}" if st["max_mbps"] is not None else "Max:    --"
            ul_l1 = (
                f"[bold blue]{st['inst_mbps']:7.2f} Mbps[/bold blue] [dim](Avg {st['avg_mbps']:5.1f})[/dim]  "
                f"[dim]|[/dim]  {min_str}  [dim]|[/dim]  {max_str}"
            )
            ul_l2 = (
                f"[{bar}] {pct:4.1f}% [dim]({mb:.0f}/{self.upload_target_mb:.0f} MB)[/dim]  "
                f"[dim]|[/dim]  [dim]Stability:[/dim] [blue]{spark}[/blue]"
            )
            table.add_row(f"[blue]{ul['spin']} Upload:[/blue]", f"{ul_l1}\n{ul_l2}")
        else:
            table.add_row("[dim]○ Upload:[/dim]", f"[dim]Target: {self.upload_target_mb:.0f} MB[/dim]")

        # Subtitle state
        if self.stage == "done":
            sub_text = "[bold green]● Test Complete[/bold green]"
        elif self.stage == "init":
            sub_text = "[dim]Connecting to speedtest server...[/dim]"
        else:
            sub_text = "[cyan]Testing throughput... (Ctrl+C to abort)[/cyan]"

        # Standardize fixed width to 80 columns (locked across all test phases)
        panel_width = min(80, max(40, self.console.width))

        panel = Panel(
            table,
            title="[bold cyan] Aussie Broadband Speed Test [/bold cyan]",
            subtitle=sub_text,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
            width=panel_width,
            expand=True,
        )
        return panel


# ============================================================================
# Testing Routines
# ============================================================================

def run_ping_phase(server, count=10, dashboard=None, is_tty=True, quiet=False):
    pings = []
    host = server["host"]
    port = server["port"]
    base_url = server["base_url"]

    use_tcp = False
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=2.5)
        sock.sendall(b"HI\n")
        sock.recv(512)
        use_tcp = True
    except Exception:
        sock = None
        use_tcp = False

    for i in range(count):
        lat = None
        if use_tcp and sock:
            try:
                t0 = time.perf_counter()
                sock.sendall(f"PING {int(time.time() * 1000)}\n".encode("utf-8"))
                sock.recv(512)
                lat = (time.perf_counter() - t0) * 1000.0
            except Exception:
                use_tcp = False
                if sock:
                    sock.close()
                    sock = None

        if lat is None:
            lat = measure_single_ping_http(base_url)

        if lat is not None:
            pings.append(lat)

        current_lat = lat if lat is not None else 0.0
        avg_lat = sum(pings) / len(pings) if pings else 0.0
        min_lat = min(pings) if pings else 0.0
        max_lat = max(pings) if pings else 0.0
        jitter = (
            sum(abs(pings[j] - pings[j - 1]) for j in range(1, len(pings))) / (len(pings) - 1)
            if len(pings) > 1
            else 0.0
        )

        if dashboard:
            dashboard.update_ping_live(current_lat, avg_lat, min_lat, max_lat, jitter, i + 1, count)
        elif not quiet:
            if is_tty:
                spin = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
                sys.stdout.write(
                    f"{CLEAR_LINE}{COLOR_CYAN}{spin}{COLOR_RESET} "
                    f"{COLOR_BOLD}Ping:{COLOR_RESET} {current_lat:5.1f} ms  "
                    f"{COLOR_DIM}|{COLOR_RESET}  Avg: {COLOR_CYAN}{avg_lat:5.1f} ms{COLOR_RESET}  "
                    f"{COLOR_DIM}|{COLOR_RESET}  Min: {min_lat:5.1f} ms  "
                    f"{COLOR_DIM}|{COLOR_RESET}  Max: {max_lat:5.1f} ms  "
                    f"{COLOR_DIM}|{COLOR_RESET}  Jitter: {COLOR_YELLOW}{jitter:4.1f} ms{COLOR_RESET} "
                    f"{COLOR_DIM}({i+1}/{count}){COLOR_RESET}"
                )
                sys.stdout.flush()
            else:
                print(f"Ping probe {i+1}/{count}: {current_lat:.1f} ms (jitter: {jitter:.1f} ms)")

        time.sleep(0.10)

    if sock:
        try:
            sock.close()
        except Exception:
            pass

    avg_final = sum(pings) / len(pings) if pings else 0.0
    min_final = min(pings) if pings else 0.0
    max_final = max(pings) if pings else 0.0
    jitter_final = (
        sum(abs(pings[j] - pings[j - 1]) for j in range(1, len(pings))) / (len(pings) - 1)
        if len(pings) > 1
        else 0.0
    )

    final_res = {
        "avg": round(avg_final, 2),
        "min": round(min_final, 2),
        "max": round(max_final, 2),
        "jitter": round(jitter_final, 2),
        "probes": len(pings),
    }

    if dashboard:
        dashboard.set_ping_done(final_res)
    elif not quiet and is_tty:
        sys.stdout.write(
            f"{CLEAR_LINE}{COLOR_GREEN}✓{COLOR_RESET} "
            f"{COLOR_BOLD}Ping:{COLOR_RESET} {COLOR_CYAN}{avg_final:5.1f} ms{COLOR_RESET}  "
            f"{COLOR_DIM}|{COLOR_RESET}  Min: {min_final:5.1f} ms  "
            f"{COLOR_DIM}|{COLOR_RESET}  Max: {max_final:5.1f} ms  "
            f"{COLOR_DIM}|{COLOR_RESET}  Jitter: {COLOR_YELLOW}{jitter_final:4.1f} ms{COLOR_RESET}\n"
        )
        sys.stdout.flush()

    return final_res


def run_download_phase(
    server, target_mb=1000.0, max_duration=60.0, threads=4, dashboard=None, is_tty=True, quiet=False
):
    target_bytes = int(target_mb * 1024 * 1024)
    tracker = SpeedTracker(window_seconds=1.0, warmup_seconds=0.8)
    stop_event = threading.Event()
    tracker.start()

    download_url = f"{server['base_url']}/random4000x4000.jpg"
    ctx = ssl.create_default_context()

    def worker(worker_id):
        while not stop_event.is_set():
            try:
                url = f"{download_url}?t={time.time()}_{worker_id}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 speedtest-abb/1.0",
                        "Accept-Encoding": "identity",
                    },
                )
                with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                    while not stop_event.is_set():
                        rem = target_bytes - tracker.total_bytes
                        if rem <= 0:
                            stop_event.set()
                            break
                        to_read = min(65536, rem)
                        chunk = resp.read(to_read)
                        if not chunk:
                            break
                        tracker.add_bytes(len(chunk))
                        if tracker.total_bytes >= target_bytes:
                            stop_event.set()
                            break
            except Exception:
                if stop_event.is_set():
                    break
                time.sleep(0.05)

    worker_threads = []
    for w in range(threads):
        t = threading.Thread(target=worker, args=(w,), daemon=True)
        worker_threads.append(t)
        t.start()

    t0 = time.perf_counter()
    step = 0

    while not stop_event.is_set():
        elapsed = time.perf_counter() - t0
        if elapsed >= max_duration:
            stop_event.set()
            break

        stats = tracker.get_stats()
        progress = min(1.0, stats["total_bytes"] / target_bytes)

        if dashboard:
            dashboard.update_download_live(stats, progress)
        elif not quiet and is_tty:
            spin = SPINNER_FRAMES[step % len(SPINNER_FRAMES)]
            step += 1
            bar = make_ascii_bar(progress, width=12)
            cur_mb = min(target_mb, stats["total_bytes"] / (1024 * 1024))
            min_str = f"Min: {stats['min_mbps']:5.1f}" if stats["min_mbps"] is not None else "Min:    --"
            max_str = f"Max: {stats['max_mbps']:5.1f}" if stats["max_mbps"] is not None else "Max:    --"
            sys.stdout.write(
                f"{CLEAR_LINE}{COLOR_GREEN}{spin}{COLOR_RESET} "
                f"{COLOR_BOLD}Download:{COLOR_RESET} [{bar}] {progress*100:4.1f}%  "
                f"{COLOR_DIM}|{COLOR_RESET} Current: {COLOR_GREEN}{COLOR_BOLD}{stats['inst_mbps']:7.2f} Mbps{COLOR_RESET}  "
                f"{COLOR_DIM}|{COLOR_RESET} Avg: {COLOR_GREEN}{stats['avg_mbps']:7.2f} Mbps{COLOR_RESET}  "
                f"{COLOR_DIM}|{COLOR_RESET} {min_str} {max_str}  "
                f"{COLOR_DIM}|{COLOR_RESET} {cur_mb:.1f} / {target_mb:.0f} MB"
            )
            sys.stdout.flush()

        time.sleep(0.06)

    stop_event.set()
    tracker.stop()
    for t in worker_threads:
        t.join(timeout=0.3)

    final_stats = tracker.get_stats()
    mb_final = min(target_mb, final_stats["total_bytes"] / (1024 * 1024))
    res = {
        "avg_mbps": round(final_stats["avg_mbps"], 2),
        "min_mbps": round(final_stats["min_mbps"], 2),
        "max_mbps": round(final_stats["max_mbps"], 2),
        "bytes": min(target_bytes, final_stats["total_bytes"]),
        "target_mb": target_mb,
        "elapsed_sec": round(final_stats["elapsed"], 2),
    }

    if dashboard:
        dashboard.set_download_done(res, final_stats.get("rates", []))
    elif not quiet:
        if is_tty:
            sys.stdout.write(
                f"{CLEAR_LINE}{COLOR_GREEN}✓{COLOR_RESET} "
                f"{COLOR_BOLD}Download:{COLOR_RESET} {COLOR_GREEN}{COLOR_BOLD}{final_stats['avg_mbps']:7.2f} Mbps{COLOR_RESET} (Avg)  "
                f"{COLOR_DIM}| Min: {final_stats['min_mbps']:.1f} Max: {final_stats['max_mbps']:.1f}  "
                f"({mb_final:.1f} MB in {final_stats['elapsed']:.1f}s){COLOR_RESET}\n"
            )
            sys.stdout.flush()
        else:
            print(
                f"Download: {final_stats['avg_mbps']:.2f} Mbps (Min: {final_stats['min_mbps']:.1f}, Max: {final_stats['max_mbps']:.1f}) - {mb_final:.1f} MB in {final_stats['elapsed']:.1f}s"
            )

    return res


def run_upload_phase(
    server, target_mb=100.0, max_duration=60.0, threads=4, dashboard=None, is_tty=True, quiet=False
):
    target_bytes = int(target_mb * 1024 * 1024)
    # 1.2s rolling window and 1.5s warmup to avoid local kernel socket buffer fill spikes
    tracker = SpeedTracker(window_seconds=1.2, warmup_seconds=1.5)
    stop_event = threading.Event()
    tracker.start()

    upload_url = f"{server['base_url']}/upload.php"
    payload = b"0" * (1024 * 1024)
    ctx = ssl.create_default_context()

    def worker(worker_id):
        while not stop_event.is_set():
            try:
                stream = MeteredUploadChunk(
                    payload=payload,
                    on_bytes=tracker.add_bytes,
                    stop_event=stop_event,
                    target_bytes=target_bytes,
                    tracker=tracker,
                )
                req = urllib.request.Request(
                    upload_url,
                    data=stream,
                    headers={
                        "Content-Length": str(len(stream)),
                        "Content-Type": "application/octet-stream",
                        "User-Agent": "Mozilla/5.0 speedtest-abb/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                    resp.read()
            except Exception:
                if stop_event.is_set():
                    break
                time.sleep(0.05)

    worker_threads = []
    for w in range(threads):
        t = threading.Thread(target=worker, args=(w,), daemon=True)
        worker_threads.append(t)
        t.start()

    t0 = time.perf_counter()
    step = 0

    while not stop_event.is_set():
        elapsed = time.perf_counter() - t0
        if elapsed >= max_duration:
            stop_event.set()
            break

        stats = tracker.get_stats()
        progress = min(1.0, stats["total_bytes"] / target_bytes)

        if dashboard:
            dashboard.update_upload_live(stats, progress)
        elif not quiet and is_tty:
            spin = SPINNER_FRAMES[step % len(SPINNER_FRAMES)]
            step += 1
            bar = make_ascii_bar(progress, width=12)
            cur_mb = min(target_mb, stats["total_bytes"] / (1024 * 1024))
            min_str = f"Min: {stats['min_mbps']:5.1f}" if stats["min_mbps"] is not None else "Min:    --"
            max_str = f"Max: {stats['max_mbps']:5.1f}" if stats["max_mbps"] is not None else "Max:    --"
            sys.stdout.write(
                f"{CLEAR_LINE}{COLOR_BLUE}{spin}{COLOR_RESET} "
                f"{COLOR_BOLD}Upload:  {COLOR_RESET} [{bar}] {progress*100:4.1f}%  "
                f"{COLOR_DIM}|{COLOR_RESET} Current: {COLOR_BLUE}{COLOR_BOLD}{stats['inst_mbps']:7.2f} Mbps{COLOR_RESET}  "
                f"{COLOR_DIM}|{COLOR_RESET} Avg: {COLOR_BLUE}{stats['avg_mbps']:7.2f} Mbps{COLOR_RESET}  "
                f"{COLOR_DIM}|{COLOR_RESET} {min_str} {max_str}  "
                f"{COLOR_DIM}|{COLOR_RESET} {cur_mb:.1f} / {target_mb:.0f} MB"
            )
            sys.stdout.flush()

        time.sleep(0.06)

    stop_event.set()
    tracker.stop()
    for t in worker_threads:
        t.join(timeout=0.3)

    final_stats = tracker.get_stats()
    mb_final = min(target_mb, final_stats["total_bytes"] / (1024 * 1024))
    res = {
        "avg_mbps": round(final_stats["avg_mbps"], 2),
        "min_mbps": round(final_stats["min_mbps"], 2),
        "max_mbps": round(final_stats["max_mbps"], 2),
        "bytes": min(target_bytes, final_stats["total_bytes"]),
        "target_mb": target_mb,
        "elapsed_sec": round(final_stats["elapsed"], 2),
    }

    if dashboard:
        dashboard.set_upload_done(res, final_stats.get("rates", []))
    elif not quiet:
        if is_tty:
            sys.stdout.write(
                f"{CLEAR_LINE}{COLOR_GREEN}✓{COLOR_RESET} "
                f"{COLOR_BOLD}Upload:  {COLOR_RESET} {COLOR_BLUE}{COLOR_BOLD}{final_stats['avg_mbps']:7.2f} Mbps{COLOR_RESET} (Avg)  "
                f"{COLOR_DIM}| Min: {final_stats['min_mbps']:.1f} Max: {final_stats['max_mbps']:.1f}  "
                f"({mb_final:.1f} MB in {final_stats['elapsed']:.1f}s){COLOR_RESET}\n"
            )
            sys.stdout.flush()
        else:
            print(
                f"Upload:   {final_stats['avg_mbps']:.2f} Mbps (Min: {final_stats['min_mbps']:.1f}, Max: {final_stats['max_mbps']:.1f}) - {mb_final:.1f} MB in {final_stats['elapsed']:.1f}s"
            )

    return res


def format_box_line(content, width, center=False, border_color=COLOR_CYAN, reset=COLOR_RESET):
    vlen = visible_len(content)
    if center:
        lpad = (width - vlen) // 2
        rpad = width - vlen - lpad
        return f"{border_color}║{reset}{' ' * lpad}{content}{' ' * rpad}{border_color}║{reset}"
    rpad = max(0, width - vlen)
    return f"{border_color}║{reset}{content}{' ' * rpad}{border_color}║{reset}"


def print_fallback_summary(server, ping_res, dl_res, ul_res):
    width = 72
    top = f"{COLOR_CYAN}╔" + "═" * width + f"╗{COLOR_RESET}"
    mid = f"{COLOR_CYAN}╠" + "═" * width + f"╣{COLOR_RESET}"
    bot = f"{COLOR_CYAN}╚" + "═" * width + f"╝{COLOR_RESET}"

    title = f"{COLOR_BOLD}Aussie Broadband Speed Test Results{COLOR_RESET}"
    server_line = f"  Server:    {server['city']} (ID: {server['id']} · {server['host']})"

    print()
    print(top)
    print(format_box_line(title, width, center=True))
    print(mid)
    print(format_box_line(server_line, width))

    if ping_res:
        ping_line = (
            f"  Latency:   {COLOR_CYAN}{ping_res['avg']} ms{COLOR_RESET} "
            f"{COLOR_DIM}(jitter: {ping_res['jitter']} ms, min: {ping_res['min']} ms, max: {ping_res['max']} ms){COLOR_RESET}"
        )
        print(format_box_line(ping_line, width))

    if dl_res:
        dl_mb = min(dl_res["target_mb"], dl_res["bytes"] / (1024 * 1024))
        dl_line = (
            f"  Download:  {COLOR_GREEN}{COLOR_BOLD}{dl_res['avg_mbps']:>7.2f} Mbps{COLOR_RESET} (Avg) "
            f"{COLOR_DIM}| Min: {dl_res['min_mbps']:.1f} Max: {dl_res['max_mbps']:.1f} ({dl_mb:.1f} MB in {dl_res['elapsed_sec']:.1f}s){COLOR_RESET}"
        )
        print(format_box_line(dl_line, width))

    if ul_res:
        ul_mb = min(ul_res["target_mb"], ul_res["bytes"] / (1024 * 1024))
        ul_line = (
            f"  Upload:    {COLOR_BLUE}{COLOR_BOLD}{ul_res['avg_mbps']:>7.2f} Mbps{COLOR_RESET} (Avg) "
            f"{COLOR_DIM}| Min: {ul_res['min_mbps']:.1f} Max: {ul_res['max_mbps']:.1f} ({ul_mb:.1f} MB in {ul_res['elapsed_sec']:.1f}s){COLOR_RESET}"
        )
        print(format_box_line(ul_line, width))

    print(bot)
    print()


def list_servers():
    print(f"{COLOR_BOLD}Probing Aussie Broadband Servers...{COLOR_RESET}\n")
    print(f"{'Location':<18} {'Host':<38} {'Port':<6} {'Latency':<10}")
    print("-" * 75)
    for key, s in ABB_SERVERS.items():
        lat = measure_single_ping_tcp(s["host"], s["port"], timeout=2.0)
        if lat is None:
            lat = measure_single_ping_http(s["base_url"], timeout=2.5)
        lat_str = f"{lat:5.1f} ms" if lat is not None else "Timeout"
        print(f"{s['city']:<18} {s['host']:<38} {s['port']:<6} {lat_str:<10}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Aussie Broadband Real-Time Speed Test CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s",
        "--server",
        help="Server city: melbourne, sydney, brisbane, adelaide, perth (or auto-detect)",
    )
    parser.add_argument(
        "-l",
        "--list-servers",
        action="store_true",
        help="List all Aussie Broadband servers and measure latency",
    )
    parser.add_argument(
        "--download-mb",
        type=float,
        default=1000.0,
        help="Target download data size in MB (default: 1000 MB)",
    )
    parser.add_argument(
        "--upload-mb",
        type=float,
        default=100.0,
        help="Target upload data size in MB (default: 100 MB)",
    )
    parser.add_argument(
        "-d",
        "--max-duration",
        type=float,
        default=60.0,
        help="Maximum timeout in seconds per phase (default: 60.0)",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=4,
        help="Number of concurrent download/upload connections (default: 4)",
    )
    parser.add_argument(
        "-p",
        "--pings",
        type=int,
        default=10,
        help="Number of ping probes to send (default: 10)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip download test",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip upload test",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Plain text output mode without Rich animations",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output final results formatted as JSON",
    )

    args = parser.parse_args()

    if args.list_servers:
        list_servers()
        return 0

    quiet = args.json
    is_tty = sys.stdout.isatty() and not args.simple and not args.json
    use_rich = RICH_AVAILABLE and is_tty and not args.simple and not args.json

    if args.server:
        match_key = None
        user_input = args.server.lower().strip()
        for k in ABB_SERVERS:
            if user_input in k:
                match_key = k
                break
        if not match_key:
            print(f"Error: Unknown server '{args.server}'. Available: {', '.join(ABB_SERVERS.keys())}")
            return 1
        selected_key = match_key
        server = ABB_SERVERS[selected_key]
    else:
        if not quiet and not use_rich:
            if is_tty:
                sys.stdout.write(f"{COLOR_DIM}Finding closest Aussie Broadband server...{COLOR_RESET}")
                sys.stdout.flush()
            else:
                print("Finding closest Aussie Broadband server...")
        selected_key, _ = find_best_server()
        server = ABB_SERVERS[selected_key]
        if is_tty and not quiet and not use_rich:
            sys.stdout.write(f"{CLEAR_LINE}")
            sys.stdout.flush()

    dashboard = None
    if use_rich:
        dashboard = RichDashboard(server, download_target_mb=args.download_mb, upload_target_mb=args.upload_mb)
        dashboard.start()
    elif not quiet:
        print(f"\n{COLOR_BOLD}Aussie Broadband Speed Test{COLOR_RESET}")
        print(f"Testing against: {COLOR_CYAN}{server['city']}{COLOR_RESET} ({server['host']})\n")
        if is_tty:
            sys.stdout.write(HIDE_CURSOR)
            sys.stdout.flush()

    ping_results = None
    dl_results = None
    ul_results = None

    try:
        # 1. Ping Phase
        ping_results = run_ping_phase(server, count=args.pings, dashboard=dashboard, is_tty=is_tty, quiet=quiet)

        # 2. Download Phase
        if not args.no_download:
            dl_results = run_download_phase(
                server,
                target_mb=args.download_mb,
                max_duration=args.max_duration,
                threads=args.threads,
                dashboard=dashboard,
                is_tty=is_tty,
                quiet=quiet,
            )

        # 3. Upload Phase
        if not args.no_upload:
            ul_results = run_upload_phase(
                server,
                target_mb=args.upload_mb,
                max_duration=args.max_duration,
                threads=args.threads,
                dashboard=dashboard,
                is_tty=is_tty,
                quiet=quiet,
            )

    except KeyboardInterrupt:
        if dashboard:
            dashboard.stop()
        if is_tty and not quiet:
            sys.stdout.write(f"\n{COLOR_YELLOW}Test interrupted by user.{COLOR_RESET}\n")
            sys.stdout.flush()
        elif not quiet:
            print("\nTest interrupted.")
        return 130
    finally:
        if dashboard and dashboard.live.is_started:
            dashboard.stop()
        restore_cursor()

    if args.json:
        output_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "server": {
                "key": selected_key,
                "city": server["city"],
                "host": server["host"],
                "id": server["id"],
            },
            "ping": ping_results,
            "download": dl_results,
            "upload": ul_results,
        }
        print(json.dumps(output_data, indent=2))
    elif not use_rich:
        print_fallback_summary(server, ping_results, dl_results, ul_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
