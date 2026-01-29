import asyncio

from theodore.ai.cmd_manager import *
from theodore.ai.rules import RouteResult
from theodore.core.exceptions import InvalidParamArgument


SHELL = ShellManager()
WEATHER = WeatherManager()
FILEMANAGER = FileManager()
DOWNLOADMANAGER = DownloadManager()
WORKER = Worker()
CONFIG_MANAGER = ConfigManager()
TASK_MANAGER = TaskManager()


commands = {
    "SHOW-CONFIGS": {"func": CONFIG_MANAGER.show_configs, "metadata": ["category"]},
    "SHOW-DASH": {"func": runDashboard, "metadata": []},
    "ALEMBIC-UPGRADE": {"func": SHELL.alembic_upgrade, "metadata": []},
    "ALEMBIC-DOWNGRADE": {"func": SHELL.alembic_downgrade, "metadata": []},
    "ALEMBIC-MIGRATE": {"func": SHELL.alembic_migrate, "metadata": ["commit_message"]},
    "GIT-COMMIT": {"func": SHELL.commit_git, "metadata": ["commit_message"]},
    "GIT-ADD": {"func": SHELL.stage, "metadata": ["directory"]},
    "CUSTOM-SHELL": {"func": SHELL.custom_shell_cmd, "metadata": ["custom_cmd"]},
    "DIR-ORGANIZE": {"func": FILEMANAGER.organize_files, "metadata": ["directory"]},
    "WEATHER": {"func": WEATHER.make_request, "metadata": ["query", "location"]},
    "DOWNLOAD": {"func": DOWNLOADMANAGER.download_file, "metadata": ["url", "directory", "filename"]},
    "PAUSE-DOWNLOAD": {"func": DOWNLOADMANAGER.pause, "metadata": ["filename"]},
    "RESUME-DOWNLOAD": {"func": DOWNLOADMANAGER.resume, "metadata": ["filename"]},
    "BACKUP": {"func": SHELL.backup_files_rclone, "metadata": ["directory", "drive_name", "env_key"]},
    "START-SERVERS": {"func": WORKER.start_processes, "metadata": []},
    "STOP-SERVERS": {"func": WORKER.send_signal, "metadata": ["header", "message"]},
}


class Dispatch:
    def dispatch_router(self, ctx: RouteResult):
        intent = ctx.intent
        if (register:=commands.get(intent)) is None:
            raise ValueError("Command Not Understood")
        
        metadata = ctx.metadata.model_dump()
        required_metadata = {}
        func = register["func"]

        for param in register["metadata"]:
            try:
                required_metadata[param] = metadata[param]
            except KeyError:
                raise InvalidParamArgument(f"Missing or Invalid func arguments. {func.__name__}\nFunc Args: {metadata}")
        
        if asyncio.iscoroutinefunction(func):
            return run_async(func=func, **required_metadata)
        return run_sync(func=func, **required_metadata)


    def dispatch_cli(self, func, **kwargs):
        if asyncio.iscoroutinefunction(func=func):
            return run_async(func=func, **kwargs)
        
        return run_sync(func=func, **kwargs)


async def run_async(func, **kwargs):
    return await func(**kwargs)
    

def run_sync(func, **kwargs):
    return func(**kwargs)

DISPATCH = Dispatch()