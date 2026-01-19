import click
import rich_click as click

from theodore.cli.config_cli import config
from theodore.cli.file_cli import file_manager, organize
from theodore.cli.task_cli import task_manager
from theodore.cli.weather_cli import weather
from theodore.cli.download_cli import downloads
from theodore.cli.server_cli import start_servers, stop_servers
from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.managers.file_manager import FileManager
from theodore.managers.tasks_manager import TaskManager
from theodore.tests.schedule_cli import schedule


# ======= Theme Import instantiation ========
cli_defaults()


@click.group(context_settings=dict(help_option_names=['--help', 'help']))
@click.version_option("0.1.0", prog_name="Theodore")
@click.option("--verbose", '-v', is_flag=True, help="Enable verbose output")
@click.pass_context
def theodore(ctx: click.Context, verbose):
    """🤖 Theodore — your personal CLI Assistant"""

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj['task_manager'] = TaskManager()
    ctx.obj['file_manager'] = FileManager()

    base_logger.internal("Theodore Initialized")

@click.group()
@click.pass_context
def tests(ctx):
    """Test out CLI commands"""

    

task_manager.add_command(file_manager, name='file-manager')
theodore.add_command(file_manager, name="file-manager")
theodore.add_command(start_servers, name='serve')
theodore.add_command(stop_servers, name='shutdown')
theodore.add_command(organize, name='organize')
theodore.add_command(tests, name="tests")
theodore.add_command(task_manager, name="tasks")
theodore.add_command(weather, name='weather')
theodore.add_command(config, name="configs")
theodore.add_command(downloads, name="download")
theodore.add_command(schedule, name="schedule")

if __name__ == "__main__":
    theodore()
