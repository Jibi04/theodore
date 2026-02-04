import json
import struct
import rich_click as click
from theodore.core.informers import user_info
from theodore.cli.async_click import AsyncCommand
from theodore.core.lazy import get_worker, Asyncio

@click.command(cls=AsyncCommand)
@click.pass_context
async def start_servers(ctx: click.Context):
    """Start Servers and processes"""
    asyncio = Asyncio()
    WORKER = get_worker()
    try:
        await WORKER.start_processes()
    except (asyncio.CancelledError, KeyboardInterrupt):
        click.echo("\nShutdown Initiated...")
        await WORKER.stop_processes()


@click.command(cls=AsyncCommand)
async def stop_servers():
    """
    Stop all servers and Processes
    """
    WORKER = get_worker()
    try:
        args = {"cmd": "STOP-PROCESSES", "file_args": {}}
        message = json.dumps(args).encode()
        header = struct.pack("!I", len(message))
        await WORKER.send_signal(header=header, message=message)
    except (ConnectionError, FileNotFoundError):
        user_info("Theodore is Offline")
    
