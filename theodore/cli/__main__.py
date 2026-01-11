import click
import rich_click as click

from theodore.cli.config_cli import config
from theodore.cli.file_cli import file_manager
from theodore.cli.task_cli import task_manager
from theodore.cli.weather_cli import weather
from theodore.cli.download_cli import downloads
from theodore.cli.server_cli import servers
from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.tests.tasks_test import tasks_test
from theodore.managers.daemon_manager import Worker
from theodore.managers.configs_manager import ConfigManager
from theodore.managers.file_manager import FileManager
from theodore.managers.download_manager import DownloadManager
from theodore.managers.tasks_manager import TaskManager
from theodore.managers.weather_manager import WeatherManager


# ======= Theme Import instantiation ========
cli_defaults()


@click.group(context_settings=dict(help_option_names=['--help', 'help']))
@click.version_option("0.1.0", prog_name="Theodore")
@click.option("--verbose", '-v', is_flag=True, help="Enable verbose output")
@click.pass_context
def theodore(ctx: click.Context, verbose):
    """🤖 Theodore — your personal CLI Assistant"""

    ctx.ensure_object(dict)
    ctx.obj['worker'] = Worker()
    ctx.obj["verbose"] = verbose
    ctx.obj['task_manager'] = TaskManager()
    ctx.obj['config_manager'] = ConfigManager()
    ctx.obj['weather_manager'] = WeatherManager()
    ctx.obj['download_manager'] = DownloadManager()
    ctx.obj['file_manager'] = FileManager()

    base_logger.internal("Theodore Initialized")

@click.group()
@click.pass_context
def tests(ctx):
    """Test out CLI commands"""

    

tests.add_command(tasks_test, name="tasks")
task_manager.add_command(file_manager, name='file-manager')

theodore.add_command(file_manager, name="file-manager")
theodore.add_command(servers, name='servers')
theodore.add_command(tests, name="tests")
theodore.add_command(task_manager, name="tasks")
theodore.add_command(weather, name='weather')
theodore.add_command(config, name="configs")
theodore.add_command(downloads, name="download")

if __name__ == "__main__":
    theodore()
