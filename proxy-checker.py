import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

# Configuration
TIMEOUT = 5
THREADS = 50

live_http = []
live_socks5 = []
dead = []
pings = []
logs = []
lock = threading.Lock()
console = Console()

def fetch_proxies():
    proxies = []

    urls = [
        ("SOCKS5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
        ("HTTP",   "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
        ("HTTP",   "https://raw.githubusercontent.com/mmpx12/proxy-list/refs/heads/master/http.txt"),
        ("SOCKS5",   "https://raw.githubusercontent.com/mmpx12/proxy-list/refs/heads/master/socks5.txt"),
        ("MIXED",   "https://raw.githubusercontent.com/mmpx12/proxy-list/refs/heads/master/proxies.txt"),
        ("MIXED",  "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text")
    ]

    for proto, url in urls:
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            lines = res.text.strip().splitlines()

            for line in lines:
                clean = line.strip()
                if not clean:
                    continue
                if proto == "SOCKS5":
                    proxies.append(f"socks5://{clean}")
                elif proto == "HTTP":
                    proxies.append(f"http://{clean}")
                elif proto == "MIXED":
                    if "://" in clean:
                        proxies.append(clean)
                    else:
                        proxies.append(f"http://{clean}")
        except Exception as e:
            console.print(f"[bold red]⚠️ Failed to fetch from {url}: {e}[/]")

    return proxies

def check_proxy(proxy):
    proxy = proxy.strip()
    if proxy.startswith("socks5://"):
        clean = proxy.replace("socks5://", "")
        proxies = {"http": proxy, "https": proxy}
        proto = "SOCKS5"
    else:
        clean = proxy.replace("http://", "")
        proxies = {"http": f"http://{clean}", "https": f"http://{clean}"}
        proto = "HTTP"

    spinner = "|/-\\"
    for frame in spinner:
        with lock:
            logs.append((f"[cyan][SCAN][/cyan] {frame} {clean:<22} | {proto}"))
        time.sleep(0.05)

    start = time.time()
    try:
        res = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=TIMEOUT)
        elapsed = round((time.time() - start) * 1000, 2)
        if res.status_code == 200:
            with lock:
                (live_socks5 if proto == "SOCKS5" else live_http).append(clean)
                with open(f"live_{proto.lower()}.txt", "a") as f:
                    f.write(clean + "\n")
                pings.append(elapsed)
                logs.append((f"[green][LIVE][/green] {clean:<22} | {proto} | {elapsed} ms"))
        else:
            with lock:
                dead.append(clean)
                logs.append((f"[yellow][BAD ][/yellow] {clean:<22} | {proto} | Status {res.status_code}"))
    except Exception as e:
        with lock:
            dead.append(clean)
            err = str(e).split(":")[0][:18]
            logs.append((f"[red][DEAD][/red] {clean:<22} | {proto} | {err}"))

def build_panel():
    total = len(live_http) + len(live_socks5) + len(dead)
    avg_ping = f"{sum(pings)/len(pings):.2f} ms" if pings else "N/A"

    table = Table.grid()
    table.add_row(f"🟢 Live: {len(live_http)+len(live_socks5)}", f"🔴 Dead: {len(dead)}", f"⏱ Avg Ping: {avg_ping}")
    table.add_row("")

    log_table = Table(show_header=True, header_style="bold magenta")
    log_table.add_column("Status", justify="left")
    for log in logs[-20:]:
        log_table.add_row(log)

    return Panel.fit(
        renderable=log_table,
        title=f"Proxy Checker - Total: {total}",
        border_style="bold cyan"
    )

def main():
    console.print("[bold magenta]🌐 Fetching proxies from various sources...[/]")
    proxies = fetch_proxies()
    if not proxies:
        try:
            with open("proxies.txt", "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
            proxies = [f"http://{p}" if not p.startswith("http") and not p.startswith("socks5") else p for p in proxies]
            console.print(f"[yellow]⚠️ Using fallback from file proxies.txt ({len(proxies)} proxy)[/]")
        except:
            console.print("[bold red]❌ No proxy available.[/]")
            return

    open("live_http.txt", "w").close()
    open("live_socks5.txt", "w").close()

    console.print(f"[bold green]✅ Total proxies to be tested: {len(proxies)}[/]")
    time.sleep(1)

    with Live(build_panel(), refresh_per_second=10, console=console) as live:
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            for proxy in proxies:
                executor.submit(check_proxy, proxy)

            while len(live_http) + len(live_socks5) + len(dead) < len(proxies):
                live.update(build_panel())
                time.sleep(0.1)

        live.update(build_panel())
        console.print("\n[bold green]✅ Done! The active proxy is saved in live_http.txt and live_socks5.txt[/]")

if __name__ == "__main__":
    main()
