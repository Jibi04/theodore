import asyncio
import click
import json
import struct
import rich_click as click
from theodore.cli.async_click import AsyncCommand
from theodore.core.utils import user_info
from theodore.tests.daemon_manager import Worker

WORKER = Worker()

@click.command(cls=AsyncCommand)
@click.pass_context
async def start_servers(ctx: click.Context):
    """Start Servers and processes"""
    try:
        await WORKER.start_processes()
    except (asyncio.CancelledError, KeyboardInterrupt):
        click.echo("\nShutdown Initiated...")
        await WORKER.stop_processes()


@click.command(cls=AsyncCommand)
@click.pass_context
async def stop_servers(ctx: click.Context):
    """
    Stop all servers and Processes
    """
    try:
        args = {"cmd": "STOP-PROCESSES", "file_args": {}}
        message = json.dumps(args).encode()
        header = struct.pack("!I", len(message))
        await WORKER.send_signal(header=header, message=message)
    except ConnectionRefusedError:
        user_info("Servers Currently not running")
    
