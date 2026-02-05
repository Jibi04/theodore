"""
Docstring for theodore.tests.state_v2

we're  using getters, to lazy load the classes only on demand then cache instance for shared memory.

The ground rules are. Web owns Theodore State. 
The CLI can temporarily own one if the Web isn't running, if the web is online, 
The CLI delegates the command rather than do it internally provided that
the task to run is under the jurisdiction of the classes under theodore's Long running processes.

"""
from fastapi import FastAPI
from pydantic import BaseModel
from dataclasses import dataclass
from typing import Protocol, Optional
from contextlib import asynccontextmanager

from theodore.core.paths import TRANSFORMER_MODEL_PATH
from theodore.models.base import AsyncSession, LOCAL_SESSION
from theodore.managers.scheduler import Scheduler, setup_scheduler
from theodore.core.informers import user_info, base_logger, error_logger

from theodore.ai.dispatch import Dispatch
from theodore.managers.daemon_manager import Worker
from theodore.managers.file_manager import FileManager
from theodore.managers.tasks_manager import TaskManager
from theodore.core.exceptions import UnknownManagerError
from theodore.managers.shell_manager import ShellManager
from theodore.managers.configs_manager import ConfigManager
from theodore.managers.weather_manager import WeatherManager
from theodore.managers.download_manager import DownloadManager

from theodore.core.lazy import (
    # type Aliases
    SentenceModel,
)



class MonitorState(BaseModel):
    cpu: float 
    vm: float 
    disk: float 
    sent: float 
    recv: float 
    ram: float 
    threads: float
    status: str 
    name: str 
    username: str 

class SessionProvider(Protocol):
    async def __call__(self) -> AsyncSession: ...

class CallableShellManager(Protocol):
    def __call__(self) -> ShellManager: ...

class CallableTaskManager(Protocol):
    def __call__(self) -> TaskManager: ...

class CallableDownloadsManager(Protocol):
    def __call__(self) -> DownloadManager: ...

class CallableWeatherManager(Protocol):
    def __call__(self) -> WeatherManager: ...

class CallableFileManager(Protocol):
    def __call__(self) -> FileManager: ...

class CallableWorker(Protocol):
    def __call__(self) -> Worker: ...

class CallableDispatch(Protocol):
    def __call__(self) -> Dispatch: ...

class CallableConfigsManager(Protocol):
    def __call__(self) -> ConfigManager: ...


@dataclass
class TheodoreState:
    scheduler: Scheduler
    model: SentenceModel
    shell: CallableShellManager
    tasks: CallableTaskManager
    downloader: CallableDownloadsManager
    weather: CallableWeatherManager
    configs: CallableConfigsManager
    file_manager: CallableFileManager
    get_session: SessionProvider
    worker: CallableWorker
    dispatch: CallableDispatch


class TheodoreStateManager:
    def __init__(self):
        self._session = None
        self._scheduler = None
        self._model: Optional[SentenceModel] = None
        self._file_manager = None
        self._weather_manager = None
        self._configs_manager = None
        self._downloads_manager = None
        self._tasks_manager = None
        self._shell_manager = None
        self._worker = None
        self._dispatch = None

        self._managers_registry = {
            "file": FileManager,
            "weather": WeatherManager,
            "shell": ShellManager,
            "tasks":  TaskManager,
            "downloads":  DownloadManager,
            "configs":  ConfigManager,
            "worker":  Worker,
            "dispatch":  Dispatch,
        }

    async def __aenter__(self):
        self._scheduler = self._get_scheduler()
        self._model = self._get_model()
        return TheodoreState(
            scheduler=self._scheduler, 
            model=self._model, 
            get_session=self._get_session,
            file_manager=self._get_file_manager,
            weather=self._get_weather_manager,
            configs=self._get_config_manager,
            downloader=self._get_download_manager,
            tasks= self._get_tasks_manager,
            shell=self._get_shell_manager,
            worker=self._get_worker,
            dispatch=self._get_dispatch,
            )
    
    def _get_file_manager(self) -> FileManager:
        return self._get_manager("file")
    
    def _get_weather_manager(self) -> WeatherManager:
        return self._get_manager("weather")
    
    def _get_config_manager(self) -> ConfigManager:
        return self._get_manager("configs")
    
    def _get_download_manager(self) -> DownloadManager:
        return self._get_manager("downloads")
    
    def _get_tasks_manager(self) -> TaskManager:
        return self._get_manager("tasks")
    
    def _get_shell_manager(self) -> ShellManager:
        return self._get_manager("shell")
    
    def _get_worker(self) -> Worker:
        instance = getattr(self, "_worker")
        if instance is None:
            download_mgt = self._get_download_manager()
            dispatch = self._get_dispatch()
            scheduler = self._get_scheduler()
            instance = Worker(scheduler=scheduler, downloads_manager=download_mgt, dispatch=dispatch)
        return instance

    def _get_dispatch(self) -> Dispatch:
        return self._get_manager("dispatch")
    
    def _get_scheduler(self) -> Scheduler:
        if self._scheduler is None:
            self._scheduler = Scheduler(setup_scheduler())
        return self._scheduler
        
    def _get_model(self) -> SentenceModel:
        from sentence_transformers import SentenceTransformer
        if not TRANSFORMER_MODEL_PATH.exists():
            model = SentenceTransformer("MiniLM_")
            model.save(str(TRANSFORMER_MODEL_PATH))
            return model
        return SentenceTransformer(str(TRANSFORMER_MODEL_PATH))
    
    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = self._new_session()
            return self._session
        
        is_healthy  = await self.session_is_active()
        if is_healthy:
            return self._session
        
        base_logger.internal("Session unhealthy. Repairing...")

        try:
            await self._session.rollback()
            await self._session.close()
        except Exception:
            pass

        self._session = self._new_session()
        return self._session
    
    def _get_manager(self, manager: str):
        if manager not in self._managers_registry:
            raise UnknownManagerError(f"Manager {manager} not a known manager.")
        
        attr_name = f"_{manager}"
        if manager not in ("dispatch", "worker"):
            attr_name = f"_{manager}_manager"

        instance = getattr(self, attr_name)
        if instance is None:
            cls = self._managers_registry[manager]
            instance = cls()
            setattr(self, attr_name, instance)
        return instance

    def _new_session(self) -> AsyncSession:
        return LOCAL_SESSION()
        
    async def session_is_active(self) -> bool:
        from sqlalchemy import select
        from sqlalchemy.exc import InternalError, OperationalError
        
        if not self._session:
            return False

        try:
            await self._session.execute(select(1))
            return True
        except (InternalError, OperationalError):
            return False

    async def _cleanup(self) -> None:
        if self._scheduler:
            self._scheduler.stop_jobs()
        if self._session:
            await self._session.commit()
            await self._session.close()
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_logger.internal(f"ErrorType: {exc_type}\n VAL: {exc_val}\n Traceback: {exc_tb}")
        else:
            base_logger.internal("Cleaning up resources, No errors gotten.")
        await self._cleanup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with TheodoreStateManager() as theodore_state:
        app.state.internals = theodore_state
        yield
    user_info("Theodore Cleanup done. Web Offline.")
