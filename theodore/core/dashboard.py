import asyncio
import numpy as np
import concurrent.futures

from rich import box
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from pathlib import Path
from typing import List

from theodore.core.utils import user_info
from theodore.math.log_vectorizer import LogSearch
from theodore.managers.daemon_manager import npy_file, server_state_file

KEYWORDS = {
    "success": ["internal", "info", "success", "created", "deleted", "moved"],
    "error": ["timeout", "nonetype", "connection", "brokenpipe", "permission"]
}

def run_math():
    split_size = 15

    files = {
        "success": Path("~/scripts/theodore/theodore/data/logs/theodore.log"),
        "error": Path("~/scripts/theodore/theodore/data/logs/errors.log")
    }

    log_searches = {
        "success": LogSearch(keywords=KEYWORDS["success"], filepath=files['success'], split_size=split_size),
        "error": LogSearch(keywords=KEYWORDS["error"], filepath=files['error'], split_size=split_size)
    }

    matrices = []
    with concurrent.futures.ThreadPoolExecutor(2) as executor:
        futures = {
            executor.submit(func): label
            for label, func in [("success", log_searches["success"].get_logs), ("error", log_searches["error"].get_logs)]
        }

        for future in concurrent.futures.as_completed(futures):
            label = futures[future]
            matrix = future.result()

            matrices.append((label, matrix))
    return matrices

def get_style(value, threshold):
    return "bold green" if value < threshold else "bold red"

# sys monitor logs
def sys_monitor_table(vectors: List[int]) -> Table:
    table = Table(title="THEODORE SYSTEM MONITOR", expand=True, style="bold green", pad_edge=True, box=box.MINIMAL, leading=1)
    table.title_style = "bold green"

    table.add_column("Metric")
    table.add_column("Value")

    (cpu, ram, disk, sent, recv, threads) = vectors

    v_style = get_style(ram, 1024)
    c_style = get_style(cpu, 70)
    d_style = get_style(disk, 85)

    metrics = [
        "CPU",
        "Disk Usage (MB)",
        "RAM (MB)",
        "network sent (MB)",
        "network recieved (MB)",
        "Threads",
        "Status"
    ]

    values = [
        f"[{c_style}]{cpu}%[/{c_style}]",
        f"[{d_style}]{disk}(MB)[{d_style}]",
        f"[{v_style}]{ram}(MB)[/{v_style}]",
        f"{sent} mb/s",
        f"{recv} mb/s",
        f"{str(threads)}",
        f"[{c_style}]Healthy[/{c_style}]" if cpu < 70 else f"[{c_style}]Stressed[/{c_style}]"
    ]

    for metric, value in zip(metrics, values):
        table.add_row(metric, value)

    return table

# errors and success logs
def get_health_table(label: str, matrix: np.matrix, keywords: list[str]) -> Table:
    table = Table(title=f"{label.upper()} Logs", title_style="bold green", box=box.SIMPLE, leading=1, expand=True, style="green" if label == 'success' else "red")
    table.add_column("KEYWORD", style="cyan")
    table.add_column("FREQ", style="bold", justify="right")

    column_sum = np.sum(matrix, axis=0)
    for col, freq in zip(keywords, column_sum):
        table.add_row(col.capitalize(), str(int(freq)))
    return table

# Run dashboard
async def run_dashboard():

    if not server_state_file.exists():
        user_info("Cannot display Dash server not running!")
        return


    layout = Layout(name='body')

    layout["body"].split_row(
        Layout(name="sidebar", ratio=1),
        Layout(name="main", ratio=2)
    )
        
    
    layout['main'].split_column(
        Layout(name="success"),
        Layout(name="error")
        )

    with Live(layout, screen=True, refresh_per_second=4):
        while True:
            # layout['header'].update(Panel("THEODORE DASHBOARD", style="bold on white"))
            
            if npy_file.exists(): 
                vectors = np.load(npy_file)
                layout['sidebar'].update(Panel(sys_monitor_table(vectors=vectors)))
            else:
                layout['sidebar'].update(Panel("System Monitor not running!"))

            stats = run_math()
            for label, matrix in stats:
                layout[label].update(Panel(get_health_table(label=label, matrix=matrix, keywords=KEYWORDS[label])))
                
            await asyncio.sleep(3)
