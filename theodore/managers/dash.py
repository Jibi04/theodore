import numpy as np, json, asyncio

from datetime import datetime as dt
from tzlocal import get_localzone
from pathlib import Path
from typing import List, Tuple
from rich.table import Table
from rich import box
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.console import Group
from rich.rule import Rule
from rich.align import Align

from theodore.managers.daemon_manager import SYS_VECTOR_FILE, DF_CHANNEL
from theodore.managers.log_search import LogSearch
from theodore.core.utils import user_info

# Main purpose is log search but future searches could extend data & logs
BASEPATH = Path(__file__).parent.parent


ctxManager = {
    "success": [BASEPATH/"data"/"logs"/"theodore.log", ["success", "internal", "timeout", "created", "deleted"]],
    "error": [BASEPATH/"data"/"logs"/"errors.log", ["timeout", "nonetype", "connection", "brokenpipe", "permission"]],
}

def getStyle(value: int | float, middle_mark, threshold: int | float):
    if value <= middle_mark:
        return "bold green" 
    elif value < threshold:
        return  "bold yellow"
    else:
        return "bold red"

def runMath():
    success = ctxManager["success"]
    error = ctxManager["error"]
    
    instances = {
        "success": LogSearch(filepath=success[0], keywords=success[1]),
        "error": LogSearch(filepath=error[0], keywords=error[1])
    }

    return instances["success"].getLogs(), instances["error"].getLogs()

label = "cyan dim"
units = "dim"
title = "bold cyan"
_default = "default"

def logHealthTable(keywords: List[str], logName: str, matrix: np.ndarray) -> Table:
    header_style = "bold cyan" if logName == "success" else "bold red"

    table = Table(
        leading=1,
        box=box.MINIMAL,
        padding=(0,2),
        expand=True,
        header_style=header_style
    )

    table.add_column("Keywords", header_style=header_style)
    table.add_column("Freq", justify="right", header_style=header_style, min_width=50)

    colSum = np.sum(matrix, axis=0)
    for kw, freq in zip(keywords, colSum):
        table.add_row(f"[cyan dim]{kw}[/]", f"[default]{str(int(freq))}[/]")
    return table

def sysHealthPanel() -> Panel | None:
    if not SYS_VECTOR_FILE.exists():
        return None
    
    (cpu, ram, disk, sent, recv, threads) = np.load(SYS_VECTOR_FILE)


    status = "[bold green]✓ Healthy[/]"
    if 50 < cpu <= 75 or 1024 < ram:
        status = "[bold yellow]Stressed[/]"
    elif cpu > 75 or ram > 2048:
        status = "[bold red]Unstable[/]"

    t = Text()
    c_style = getStyle(cpu, 50, 75)
    d_style = getStyle(disk, 50, 75)
    r_style = getStyle(ram, 500, 700)



    content = Group(
        Rule("THEODORE SYSTEM HEALTH", style=title),
        f"\nStatus: {status}\n",
        f"Date: {dt.now(get_localzone()).date()}\n",
        f"Threads: {threads}\n",
        Panel(
            Group(
                f"[{label}]CPU[/]: [{c_style}]{cpu}[/][{units}] %[/{units}]\n\n",
                f"[{label}]Disk[/]: [{d_style}]{disk}[/][{units}] %[/{units}]\n\n",
                f"[{label}]RAM[/]: [{r_style}]{ram}[/][{units}] mb[/{units}]\n\n",
                f"[{label}]Net Sent[/{label}]: {sent}[{units}] mb/s[/][yellow]↑[/]\n\n",
                f"[{label}]Net Recv[/{label}]: {recv}[{units}] mb/s[/][{units}]↓[/{units}]\n"
            ),
            padding=(1,1)
        )
    )
    system_health = Panel(content, border_style="cyan dim")
    return system_health

def newDataTable() -> Tuple[Panel, Panel] | None:
    # dataframe overview
    if not DF_CHANNEL.exists():
        return None
    
    df_profile = json.loads(DF_CHANNEL.read_text())
    general = json.loads(df_profile["general"])

    t = Text(tab_size=20, no_wrap=False)
    t2 = Text(tab_size=20, no_wrap=False)
    t.append(f"\nMemory:\t", style=label)
    t.append(f"{general['size']//1024**2} mb\n\n", style=_default)
    t.append(f"Rows:\t", style=label)
    t.append(f"{general['row_count']}\n\n", style=_default)
    t.append(f"Columns:\t",style=label)
    t.append(f"{general['col_count']}\n\n", style=_default)
    t.append(f"Numbers dtypes:\t",style=label)
    t.append(f"{general['num_count']}\n\n", style=_default)

    t2.append(f"Objects dtypes:\t", style=label)
    t2.append(f"{general['obj_count']}\n\n", style=label)
    t2.append(f"Null count:\t", style=label)
    t2.append(f"{general['null_count']}\n\n", style="bold red")
    t2.append(f"Duplicate count:\t", style=label)
    t2.append(f"{general['duplicated_count']}\n\n", style="bold green")
    t2.append(f"Unique:\t", style=label)
    t2.append(f"{general['unique_count']}\n", style=_default)

    
    general_group = Panel(
        Group(t, t2), 
        box=box.MINIMAL, 
        border_style=label,
        expand=True
    )


    # Numeric Analysis
    numeric = json.loads(df_profile["numeric"])
    numeric_content = Align.center("[dim]No Numeric Columns Detected[/]", vertical="middle")
    if numeric:
        table = Table(leading=1, box=box.MINIMAL)
        def outlier(value):
            if value == 0:
                return "default"
            elif value < 3:
                return "yellow dim"
            else:
                return "red dim"

        table.add_column("Column", header_style=label, justify="center")
        table.add_column("Mean", header_style=label, justify="center")
        table.add_column("std", header_style=label, justify="center")
        table.add_column("Max", header_style=label, justify="center")
        table.add_column("Min", header_style=label, justify="center")
        table.add_column("Outliers", header_style="red dim", justify="center")

        for col, mean, max, min, std, out in zip(*numeric.values()):
            table.add_row(
                str(col), str(mean), str(std), str(max), str(min),
                f"[{outlier(out)}]{out}[/]",
                style=label
            )
        numeric_content = table

    numeric_group = Panel(Group(Rule("Numeric Analysis", style=title), numeric_content), box=box.MINIMAL, border_style=label, expand=True)

    return general_group, numeric_group

        
async def runDashboard():
    if not SYS_VECTOR_FILE.exists():
        return user_info("Cannot run dash Server not running.")
    
    layout = Layout()

    layout.split_row(
        Layout(name="sidebar", ratio=1),
        Layout(name="main", ratio=3)
    )

    layout["sidebar"].split_column(
        Layout(name="systemMonitor", ratio=4),
        Layout(name="logActivity", ratio=1)
    )

    layout["main"].split_column(
        Layout(name="table1", ratio=1),
        Layout(name="table2", ratio=2),
    )


    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            layout["table1"].ratio = 1
            layout["table2"].ratio = 1

            successMatrix, errorMatrix = runMath()
            if (data:=newDataTable()):
                generalPanel, numericPanel = data


                layout["table1"].update(Align(generalPanel, vertical="bottom"))
                layout["table2"].update(Align(numericPanel, vertical="bottom"))
            else:

                error = ctxManager["error"]
                success = ctxManager["success"]

                layout["table1"].update(
                    Panel(
                        Align(
                            Group(
                                Rule(title=f"[{title}]Error Info[/]"),
                                logHealthTable(logName="success", keywords=error[1], matrix=errorMatrix)
                            ),
                            vertical="bottom",
                            align="center"),
                        expand=True
                        )
                    )
                
                layout["table2"].update(
                    Panel(
                        Align(
                            Group(
                                Rule(title=f"[{title}]Success Info[/]"),
                                logHealthTable(logName="success", keywords=success[1], matrix=successMatrix)
                            ),
                            vertical="bottom",
                            align="center"),
                        expand=True
                        )
                    )
            
            monitor = sysHealthPanel()
            if monitor is None:
                layout["systemMonitor"].update(
                Panel(Align(
                    Group(f"[{label}]Theodore Offline[/]"),
                    align="center",
                    vertical="middle"
                ),
                border_style=label
                )
            )
            else:
                layout["systemMonitor"].update(monitor)

            layout["logActivity"].update(Panel(
                Group(
                    f"\n[red dim]Log Errors:\t{np.sum(errorMatrix.sum(axis=1), axis=0)}\n",
                    f"Success Logs:\t{np.sum(successMatrix.sum(axis=1), axis=0)}\n"
                ),
                title="Log Summary",
                title_align="center",
                style=label,
                padding=(0, 1),
                )
            )
            await asyncio.sleep(0.5)