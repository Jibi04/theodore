import asyncio
import inspect

from theodore.ai.rules import RouteResult
from theodore.core.exceptions import MissingParamArgument, InvalidParamArgument

from theodore.ai.cmd_manager import (
    ShellManager, 
    WeatherManager, 
    FileManager, 
    DownloadManager, 
    Worker, 
    ConfigManager, 
    runDashboard,
    TaskManager
    )

SHELL = ShellManager()
WEATHER = WeatherManager()
FILEMANAGER = FileManager()
DOWNLOADMANAGER = DownloadManager()
WORKER = Worker()
CONFIG_MANAGER = ConfigManager()
TASK_MANAGER = TaskManager()

commands = {
    "SHOW-CONFIGS": {"func": CONFIG_MANAGER.show_configs},
    "SHOW-DASH": {"func": runDashboard},
    "ALEMBIC-UPGRADE": {"func": SHELL.alembic_upgrade},
    "ALEMBIC-DOWNGRADE": {"func": SHELL.alembic_downgrade},
    "ALEMBIC-MIGRATE": {"func": SHELL.alembic_migrate},
    "GIT-COMMIT": {"func": SHELL.commit_git},
    "GIT-ADD": {"func": SHELL.stage},
    "CUSTOM-SHELL": {"func": SHELL.custom_shell_cmd},
    "DIR-ORGANIZE": {"func": FILEMANAGER.organize_files},
    "WEATHER": {"func": WEATHER.make_request},
    "DOWNLOAD": {"func": DOWNLOADMANAGER.download_file},
    "PAUSE-DOWNLOAD": {"func": DOWNLOADMANAGER.pause},
    "RESUME-DOWNLOAD": {"func": DOWNLOADMANAGER.resume},
    "BACKUP": {"func": SHELL.backup_files_rclone},
    "START-SERVERS": {"func": WORKER.start_processes},
    "STOP-SERVERS": {"func": WORKER.stop_processes},
}

class Dispatch:
    def dispatch_router(self, ctx: RouteResult):
        intent = ctx.intent
        metadata = ctx.metadata.model_dump()

        func = commands[intent]["func"]
        sig = inspect.signature(func)
        refined_args = {}

        for name, param in sig.parameters.items():
            if name == "self":
                continue
            annotation = param.annotation

            val = metadata.get(name)
            if param.default is inspect.Parameter.empty:
                if val is None:
                    raise MissingParamArgument(f"{intent} requires argument {name} but none was extracted.")
                
                # empty list or string
                if not val and annotation is list():
                    raise InvalidParamArgument(f"{intent} expected argument {name} with args {annotation} but got {val}")
            
            if val is None:
                continue
            elif annotation is list():
                refined_args[name] = val
            elif isinstance(val, list):
                if not val: 
                    continue
                refined_args[name] = val[0]
            else:
                refined_args[name] = val

        if asyncio.iscoroutinefunction(func):
            return run_async(func, **refined_args)
        return func(**refined_args)
        
    def dispatch_cli(self, func, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return run_async(func, **kwargs)
        return func(**kwargs)
    

def run_async(func, **kwargs):
    with asyncio.Runner() as runner:
        response = runner.run(func(**kwargs))
        return response


DISPATCH = Dispatch()