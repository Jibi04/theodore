# create a watcher daemon service that uses PSUTIll for CPU Monitoring with logging, 
# it should also start the the client-server IPC socket. 
# use asyncio.sleep() so the CPU isn't constantly bombarded with function calls
import asyncio
import click
import json
import struct
import rich_click as click
from theodore.cli.async_click import AsyncCommand
from theodore.managers.daemon_manager import Worker

WORKER = Worker()

@click.group()
@click.pass_context
def servers(ctx: click.Context):
    """Manage Servers and processes"""

@servers.command(cls=AsyncCommand)
@click.pass_context
async def start_servers(ctx: click.Context):
    """Start Servers and processes"""
    try:
        await WORKER.start_processes()
    except (asyncio.CancelledError, KeyboardInterrupt):
        click.echo("\nShutdown Initiated...")
        await WORKER.stop_processes()


@servers.command(cls=AsyncCommand)
@click.pass_context
async def stop_servers(ctx: click.Context):
    """
    Stop all servers and Processes
    """
    args = {"cmd": "STOP-PROCESSES", "file_args": {}}
    message = json.dumps(args).encode()
    header = struct.pack("!I", len(message))
    await WORKER.send_signal(header=header, message=message)
    
