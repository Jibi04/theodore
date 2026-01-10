# create a watcher daemon service that uses PSUTIll for CPU Monitoring with logging, 
# it should also start the the client-server IPC socket. 
# use asyncio.sleep() so the CPU isn't constantly bombarded with function calls
import asyncio
import click
import rich_click as click
import json
from theodore.cli.async_click import AsyncCommand
from theodore.core.utils import user_info
from theodore.managers.daemon_manager import Worker

_worker = Worker()

@click.group()
@click.pass_context
def servers(ctx: click.Context):
    """Manage Servers and processes"""
    ctx.obj['worker'] = Worker()

@servers.command(cls=AsyncCommand)
@click.pass_context
async def start_servers(ctx: click.Context):
    """Start Servers and processes"""
    worker: Worker =  _worker
    try:
        tasks = await worker.start_processes()
        tasks = await asyncio.gather(*tasks, return_exceptions=True)
        print(tasks)
    except (asyncio.CancelledError, KeyboardInterrupt) as e:
        click.echo(f"\nShutdown signal received... {e}")
    finally:
        await worker.stop_processes()

@servers.command(cls=AsyncCommand)
@click.pass_context
async def stop_servers(ctx: click.Context):
    """
    Stop all servers and Processes
    """
    worker: Worker =  _worker
    args = {"cmd": "SHUTDOWN"}
    args = json.encoder.JSONEncoder().encode(args)
    response = await worker.send_signal(args.encode())
    user_info(response)
