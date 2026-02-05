import time
start = time.perf_counter()

import rich_click as click

from theodore.cli.dash_cli import dash
from theodore.cli.config_cli import config
from theodore.cli.weather_cli import weather
from theodore.core.theme import cli_defaults
from theodore.core.informers import user_info
from theodore.cli.task_cli import task_manager
from theodore.cli.schedule_cli import schedule
from theodore.cli.download_cli import downloads
from theodore.cli.async_click import AsyncCommand
from theodore.core.logger_setup import base_logger
from theodore.cli.file_cli import file_manager, organize
from theodore.cli.server_cli import start_servers, stop_servers
from theodore.cli.shell_cli import shell, backup, add_git, commit, upgrade_migration, migrate_db

total_time = round(time.perf_counter() - start, 5)
user_info(f"Total Import time: {total_time}")

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
    base_logger.internal("Theodore Initialized")

# @click.group()
# @click.pass_context
# def tests(ctx):
#     """Test out CLI commands"""

task_manager.add_command(file_manager, name='file-manager')
theodore.add_command(dash, "dash")
theodore.add_command(shell, "shell")
theodore.add_command(file_manager, "manager")
theodore.add_command(start_servers, 'serve')
theodore.add_command(stop_servers, 'shutdown')
theodore.add_command(organize, 'organize')
# theodore.add_command(tests, "tests")
theodore.add_command(task_manager, "tasks")
theodore.add_command(weather, 'weather')
theodore.add_command(config, "configs")
theodore.add_command(downloads, "download")
theodore.add_command(schedule, "schedule")
theodore.add_command(backup, "backup")
theodore.add_command(add_git, "add")
theodore.add_command(commit, "commit")
theodore.add_command(upgrade_migration, "upgrade")
theodore.add_command(migrate_db, "migrate")

@theodore.command(cls=AsyncCommand)
async def status():
    """Get Theodore server Status"""
    from theodore.core.transporter import send_command

    try:
        intent = "dadadadada"
        await send_command(intent=intent, file_args={})
        user_info("Theodore currently running")
    except (ConnectionRefusedError, FileNotFoundError, ConnectionAbortedError):
        user_info("Theodore currently offline")



@theodore.command()
def live():
    """Interact with click in interactive Mode."""
    click.echo("This may take a minute or two. Setting up...")
    
    import traceback
    from theodore.core.informers import user_info, user_error
    from theodore.system_service import SystemService
    from theodore.ai.intent import IntentRouter
    from theodore.ai.route_builder import routeBuilder
    from theodore.ai.rules import CONFIDENCE_THRESHOLD
    from theodore.ai.train_data import TRAIN_DATA_Path
    ss = SystemService(["theodore", "serve"])

    ss.start_processes()
    Intent = IntentRouter(train_data=TRAIN_DATA_Path)

    click.echo("Hi I'm Theodore.")
    try:
        while True:
            try:
                text = input(">> ")
                request = text.strip()
                if not request:
                    continue

                if request.lower() == "quit":
                    break

                intent, confidence = Intent.match(request)

                if confidence < CONFIDENCE_THRESHOLD:
                    user_info(f"request '{request}' not understood")
                    continue

                if intent == "STOP-SERVERS":
                    if ss.is_running():
                        ss.stop_processes()
                        ss.supervise()
                        continue

                elif intent == "START-SERVERS":
                    ss.start_processes()
                    continue

                response = routeBuilder(
                    request, 
                    intent=intent, 
                    confidence_level=confidence
                    )
                if response: user_info(response)
                time.sleep(0.1)
            except KeyboardInterrupt:
                click.echo("\nShut down Initiated.")
                break
            except RuntimeError:
                user_error(traceback.format_exc())
                break
            except Exception:
                user_error(traceback.format_exc())
    finally:
        if ss.is_running():
            ss.stop_processes()
            ss.supervise()

    

if __name__ == "__main__":
    theodore()
