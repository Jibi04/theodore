import asyncio
import inspect

from theodore.ai.cmd_manager import *
from theodore.ai.rules import RouteResult
from theodore.core.exceptions import InvalidParamArgument, MissingParamArgument


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
    "STOP-SERVERS": {"func": WORKER.send_signal},
}


class Dispatch:
    def dispatch_router(self, ctx: RouteResult):
        intent = ctx.intent
        if (register:=commands.get(intent)) is None:
            raise ValueError(f"Command {intent} Not Understood")
        
        metadata = ctx.metadata.model_dump()
        required_metadata = {}
        func = register["func"]

        sig = inspect.signature(func)

        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if name in metadata:
                val = metadata[name]

                if isinstance(val, list):
                    if len(val) > 0:
                        if param.annotation == list():
                            required_metadata[name] = val
                        else:
                            required_metadata[name] = val[0]
                    elif param.default is inspect.Parameter.empty:
                        raise InvalidParamArgument(f"{func._name__} expected argument {name} but got None {val}")
                else:
                    required_metadata[name] = val
                    
            elif param.default is inspect.Parameter.empty:
                raise MissingParamArgument(f"{func.__name__} expected argument {name} but was never extracted.")

        if asyncio.iscoroutinefunction(func):
            return run_async(func=func, **required_metadata)
        return func(**required_metadata)


    def dispatch_cli(self, func, **kwargs):
        if asyncio.iscoroutinefunction(func=func):
            return run_async(func, **kwargs)
        return func(**kwargs)


def run_async(func, **kwargs):
    try:
        result = asyncio.run(func(**kwargs))
        return result
    except RuntimeWarning:
        raise
    

DISPATCH = Dispatch()


