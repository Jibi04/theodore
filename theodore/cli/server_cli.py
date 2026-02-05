import rich_click as click
from theodore.core.lazy import Asyncio
from theodore.core.informers import user_info
from theodore.cli.async_click import AsyncCommand


@click.command(cls=AsyncCommand)
async def start_servers():
    """Start Servers and processes"""
    from theodore.core.state import TheodoreStateManager

    worker = TheodoreStateManager()._get_worker()
    asyncio = Asyncio()
    try:
        await worker.start_processes()
    except (asyncio.CancelledError, KeyboardInterrupt):
        click.echo("\nShutdown Initiated...")
        await worker.stop_processes()


@click.command(cls=AsyncCommand)
async def stop_servers():
    """
    Stop all servers and Processes
    """
    from theodore.core.transporter import send_command

    try:
        args = {"intent": "STOP-PROCESSES", "file_args": {}}
        response = await send_command(**args)
        user_info(response)
    except (ConnectionError, FileNotFoundError):
        user_info("Theodore is Offline")
    
