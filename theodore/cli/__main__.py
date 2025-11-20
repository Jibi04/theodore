import click, os, asyncio
import rich_click as click

from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.cli.config_cli import config
from theodore.cli.tasks_cli import task_manager
from theodore.cli.weather_cli import weather
from theodore.cli.download_cli import downloads
from theodore.cli.file_cli import file_manager
from theodore.tests.tasks_test import tasks_test
from theodore.core.worker_setup import start_workers
from theodore.managers.file_manager import File_manager
from theodore.managers.download_manager import Downloads_manager
from theodore.managers.tasks_manager import Task_manager
from theodore.managers.configs_manager import Configs_manager
from theodore.managers.weather_manager import Weather_manager


# ======= Theme Import instantiation ========
cli_defaults()


@click.group(context_settings=dict(help_option_names=['--help', 'help']))
@click.version_option("0.1.0", prog_name="Theodore")
@click.option("--verbose", '-v', is_flag=True, help="Enable verbose output")
@click.pass_context
def theodore(ctx, verbose):
    """🤖 Theodore — your personal CLI Assistant"""

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj['task_manager'] = Task_manager()
    ctx.obj['config_manager'] = Configs_manager()
    ctx.obj['weather_manager'] = Weather_manager()
    ctx.obj['download_manager'] = Downloads_manager
    ctx.obj['file_manager'] = File_manager()

    base_logger.internal("Theodore Initalized")

@click.group()
@click.pass_context
def tests(ctx):
    """Test out CLI commands"""

def AsyncRunner():
    try:
        worker_task = asyncio.create_task(start_workers(10))

        theodore.main(standalone_mode=False)
    except Exception as e:
        print(f'An Error occurred in the AsyncRunner {type(e).__name__}: {str(e)}')
    finally:
        worker_task.cancel()


    

tests.add_command(tasks_test, name="tasks")
task_manager.add_command(file_manager, name='file-manager')

theodore.add_command(tests, name="tests")
theodore.add_command(task_manager, name="tasks")
theodore.add_command(weather, name='weather')
theodore.add_command(config, name="configs")
theodore.add_command(downloads, name="download")
theodore.add_command(file_manager, name="files")

if __name__ == "__main__":
    asyncio.run(AsyncRunner())
