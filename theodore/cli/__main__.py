import click
import rich_click as click

import time

from theodore.cli.config_cli import config
from theodore.cli.download_cli import downloads
from theodore.cli.file_cli import file_manager, organize
from theodore.cli.schedule_cli import schedule
from theodore.cli.server_cli import start_servers, stop_servers
from theodore.cli.task_cli import task_manager
from theodore.cli.shell_cli import shell, backup, add_git, add_commit, upgrade_migration, migrate_db
from theodore.cli.weather_cli import weather
from theodore.cli.dash_cli import dash
from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.managers.file_manager import FileManager


# ======= Theme Import instantiation ========
cli_defaults()

def load_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        val = func(*args, **kwargs)
        base_logger.internal(f"{func.__name__} took {round(time.perf_counter() - start_time, 5)}s to load.")
        return val
    return wrapper

@click.group(context_settings=dict(help_option_names=['--help', 'help']))
@click.version_option("0.1.0", prog_name="Theodore")
@click.option("--verbose", '-v', is_flag=True, help="Enable verbose output")
@click.pass_context
@load_time
def theodore(ctx: click.Context, verbose):
    """🤖 Theodore — your personal CLI Assistant"""

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj['file_manager'] = FileManager()
    base_logger.internal("Theodore Initialized")

@click.group()
@click.pass_context
def tests(ctx):
    """Test out CLI commands"""

task_manager.add_command(file_manager, name='file-manager')
theodore.add_command(dash, "dash")
theodore.add_command(shell, "shell")
theodore.add_command(file_manager, "manager")
theodore.add_command(start_servers, 'serve')
theodore.add_command(stop_servers, 'shutdown')
theodore.add_command(organize, 'organize')
theodore.add_command(tests, "tests")
theodore.add_command(task_manager, "tasks")
theodore.add_command(weather, 'weather')
theodore.add_command(config, "configs")
theodore.add_command(downloads, "download")
theodore.add_command(schedule, "schedule")
theodore.add_command(backup, "backup")
theodore.add_command(add_git, "add")
theodore.add_command(add_commit, "commit")
theodore.add_command(upgrade_migration, "upgrade")
theodore.add_command(migrate_db, "migrate")




if __name__ == "__main__":
    theodore()
