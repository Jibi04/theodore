import click
import rich_click as click

from theodore.cli.async_click import AsyncCommand
from theodore.core.dashboard import run_dashboard


@click.command(cls=AsyncCommand)
async def dash():
    """Show Dashboard"""
    await run_dashboard()