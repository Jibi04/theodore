import inspect
import importlib
from typing import Any
from functools import lru_cache

from theodore.core.exceptions import MissingParamArgument, InvalidParamArgument, UnknownCommandError
from theodore.core.lazy import Asyncio, RouteResults

commands: dict[str, tuple[str, str | None]]= {
    "SHOW-CONFIGS": ("theodore.ai.cmd_manager.ConfigManager", "show_configs"),
    "SHOW-DASH": ("theodore.ai.cmd_manager.runDashboard", None),

    "ALEMBIC-UPGRADE": ("theodore.ai.cmd_manager.ShellManager", "alembic_upgrade"),
    "ALEMBIC-DOWNGRADE": ("theodore.ai.cmd_manager.ShellManager", "alembic_downgrade"),
    "ALEMBIC-MIGRATE": ("theodore.ai.cmd_manager.ShellManager", "alembic_migrate"),

    "GIT-COMMIT": ("theodore.ai.cmd_manager.ShellManager", "commit_git"),
    "GIT-ADD": ("theodore.ai.cmd_manager.ShellManager", "stage"),

    "CUSTOM-SHELL": ("theodore.ai.cmd_manager.ShellManager", "custom_shell_cmd"),
    "DIR-ORGANIZE": ("theodore.ai.cmd_manager.FileManager", "organize_files"),
    "WEATHER": ("theodore.ai.cmd_manager.WeatherManager", "make_request"),

    "DOWNLOAD": ("theodore.ai.cmd_manager.DownloadManager", "download_file"),
    "PAUSE-DOWNLOAD": ("theodore.ai.cmd_manager.DownloadManager", "pause"),
    "RESUME-DOWNLOAD": ("theodore.ai.cmd_manager.DownloadManager", "resume"),

    "BACKUP": ("theodore.ai.cmd_manager.ShellManager", "backup_files_rclone"),

    "START-SERVERS": ("theodore.ai.cmd_manager.Worker", "start_processes"),
    "STOP-SERVERS": ("theodore.ai.cmd_manager.Worker", "stop_processes"),
}


def resolve_module(module: str):
    mod = importlib.import_module(module)
    return mod


@lru_cache
def get_instance(cls):
    return cls()


def get_cmd(name) -> None | Any:
    if (entry:= commands.get(name)) is None:
        return None
    
    target_path, method = entry

    mod, _, cls_or_func = target_path.rpartition(".")

    if (module:=resolve_module(mod)) is None:
        raise ModuleNotFoundError(f"Module for {name} not found")
    
    if method is None:
        return getattr(module, cls_or_func)
    
    cls = getattr(module, cls_or_func)
    instance = get_instance(cls)
    return getattr(instance, method)


class Dispatch:

    def dispatch_router(self, ctx: RouteResults):
        asyncio = Asyncio()

        intent = ctx.intent
        metadata = ctx.metadata.model_dump()

        try:
            func = get_cmd(intent)
        except ModuleNotFoundError:
            raise
        if func is None:
            raise UnknownCommandError(f"Command {intent} is not Known")
        
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
        asyncio = Asyncio()
        if asyncio.iscoroutinefunction(func):
            return run_async(func, **kwargs)
        return func(**kwargs)
    

def run_async(func, **kwargs):
    asyncio = Asyncio()
    with asyncio.Runner() as runner:
        response = runner.run(func(**kwargs))
        return response


# DISPATCH = Dispatch()