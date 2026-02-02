"""

Implementing Lazy Loading using Importlib for this modules and every other heavy modules
SQLALCHEMY, PANDAS, NUMPY, SENTENCE TRANSFORMERS, HTTPX, DATEPARSER, PYDANTIC, RICH-CLICK, CLICK AND ANYIO

"""

from typing import TYPE_CHECKING, TypeAlias, Any
from functools import lru_cache


if TYPE_CHECKING:
    import pandas as pd
    import numpy as np
    import sqlalchemy
    from sqlalchemy import Row
    from pydantic import ValidationError
    from sqlalchemy.exc import SQLAlchemyError
    from sentence_transformers import SentenceTransformer
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from theodore.ai.rules import RouteResult
    from theodore.managers.schedule_manager import Job
    from theodore.managers.configs_manager import ConfigManager
    from theodore.managers.shell_manager import ShellManager
    from theodore.managers.file_manager import FileManager
    from theodore.managers.daemon_manager import Worker
    from theodore.managers.tasks_manager import TaskManager
    from theodore.managers.weather_manager import WeatherManager
    from theodore.ai.dispatch import Dispatch


NDArray: TypeAlias = "np.ndarray"
DataFrame: TypeAlias = "pd.DataFrame"
SQLRow: TypeAlias = "Row[Any]"
SQLERROR: TypeAlias = "SQLAlchemyError"
SQLTable: TypeAlias = "sqlalchemy.Table"
SQLSequence: TypeAlias = "sqlalchemy.Sequence"
SentenceModel: TypeAlias = "SentenceTransformer"
ConfigsManagement: TypeAlias = "ConfigManager"
ShellManagement: TypeAlias = "ShellManager"
FileManagement: TypeAlias = "FileManager"
WorkerManagement: TypeAlias = "Worker"
TaskManagement: TypeAlias = "TaskManager"
WeatherManagement: TypeAlias = "WeatherManager"
RouteResults: TypeAlias = "RouteResult"
PydValidationError: TypeAlias = "ValidationError"
BACKGROUND_SCHEDULER: TypeAlias = "BackgroundScheduler"
AsyncioScheduler: TypeAlias = "AsyncIOScheduler"
ScheduleJob: TypeAlias = "Job"




@lru_cache
def pandas():
    import pandas as pd
    return pd

@lru_cache
def numpy():
    import numpy as np
    return np

@lru_cache
def sql():
    import sqlalchemy
    return sqlalchemy

@lru_cache
def Asyncio():
    import asyncio
    return asyncio

@lru_cache
def aio_os():
    import aiofiles.os as os
    return os

@lru_cache
def aiofiles():
    import aiofiles
    return aiofiles

@lru_cache
def get_dispatch():
    from theodore.ai.dispatch import Dispatch
    return Dispatch()

@lru_cache
def sentence_model():
    from sentence_transformers import SentenceTransformer
    return  SentenceTransformer("all-MiniLM-L6-v2")


@lru_cache
def get_config_manager():
    from theodore.managers.configs_manager import ConfigManager
    return ConfigManager()

@lru_cache
def get_shell_manager():
    from theodore.managers.shell_manager import ShellManager
    return ShellManager()

@lru_cache
def get_downloads_manager():
    from theodore.managers.download_manager import DownloadManager
    return DownloadManager()

@lru_cache
def get_cache_manager():
    from theodore.managers.cache_manager import Cache_manager
    return Cache_manager(ttl=5)

@lru_cache
def get_file_manager():
    from theodore.managers.file_manager import FileManager
    return FileManager()

@lru_cache
def get_worker():
    from theodore.managers.daemon_manager import Worker
    return Worker()

@lru_cache
def get_task_manager():
    from theodore.managers.tasks_manager import TaskManager
    return TaskManager()

@lru_cache
def get_weather_manager():
    from theodore.managers.weather_manager import WeatherManager
    return WeatherManager()

@lru_cache
def get_db_handler(table: SQLTable):
    from theodore.core.db_operations import DBTasks
    return DBTasks(table)
