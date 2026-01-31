import rich_click as click

from theodore.cli.async_click import AsyncCommand
from theodore.managers.dash import runDashboard


@click.command(cls=AsyncCommand)
async def dash():
    """Show Dashboard"""
    await runDashboard()
