import inspect
import json
import asyncio
import importlib

from enum import Enum
from tzlocal import get_localzone
from datetime import datetime, UTC
from sqlalchemy import create_engine
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Any, Callable, Dict, List, Literal, Annotated, Tuple, Self

from theodore.core.paths import DATA_DIR
from theodore.core.informers import user_info
from theodore.core.exceptions import JobNotFoundError, NotRegisteredFunctionError
from theodore.ai.dispatch import resolve_module, commands, get_instance

from apscheduler.job import Job
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# ------------------------------------------------
# Scheduler Configurations
# ------------------------------------------------
def setup_scheduler() -> AsyncIOScheduler:
    path = DATA_DIR/"jobs.sqlite"
    engine = create_engine(f"sqlite:///{path.absolute()}")

    executors = {
        "async": AsyncIOExecutor(),
        "sync": ThreadPoolExecutor(max_workers=10)
    }

    job_stores = {
        "default": SQLAlchemyJobStore(engine=engine)
    }
    return AsyncIOScheduler(jobstores=job_stores, executors=executors)

# ------------------------------------------------------------
# Validation Classes
# ------------------------------------------------------------

class Status(Enum):
    cancelled = "cancelled"
    active = "active"
    inactive = "in_active"

class RuntimeModel(BaseModel):
    hour: Annotated[int | None, Field(ge=0, le=23)]
    minute: Annotated[int | None, Field(ge=0, le=59)]
    second: Annotated[int | None, Field(ge=0, le=59)]
    day: Annotated[int | None, Field(ge=1, le=31)]
    day_of_week: Annotated[int | None, Field(ge=0, le=6)]
    week: Annotated[int | None, Field(ge=1, le=53)]
    month: Annotated[int | None, Field(ge=1, le=12)]
    year: Annotated[int | None, Field(ge=2026, le=9999)]

class FunctionModel(BaseModel):
    func_path: str | None = None
    module: str | None = None
    method: str | None = None
    cls_name: str | None = None
    func: Callable[[Any], None] | None = None

    @model_validator(mode="after")
    def extract_paths(self) -> Self:
        if self.func_path is None:
            return self
        p = self.func_path
        try:
            entry = resolve_module_path(name=p)
            if entry is None:
                raise ValueError(f"Function path {p} could not be resolved")
        except ModuleNotFoundError:
                raise ValueError(f"Module {p} Not Found")
        
        module, cls_name, method = entry

        self.module = module
        self.cls_name = cls_name
        self.method = method

        return self
    
    @model_validator(mode="before")
    @classmethod
    def validate_func(cls, data):
        if data.get("func") is None and data.get("func_path") is None:
            raise ValueError(f"Callable Function and Function Path cannot be None.")
        
        return data

class JOB(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    key: str
    trigger: Literal["interval", "cron"]
    function_model: FunctionModel
    runtime_model: RuntimeModel
    func_args: Dict[Any, Any] | List[Dict[str, Any]] | None = None
    profiling_enabled: bool = False
    status: Status = Status.inactive
    date_created: datetime = Field(default_factory=lambda: datetime.now(UTC))

# ----------------------------------------
# HANDLER
# ----------------------------------------

class Scheduler:
    def __init__(self, scheduler: AsyncIOScheduler = setup_scheduler()):
        self.scheduler = scheduler
        self._job_registry: List[Job] = self.scheduler.get_jobs()
        self._scheduler_shutdown_event = asyncio.Event()
        self.running = False

    def new_job(
            self,
            *,
            key: str,
            trigger: Literal["cron", "interval"],
            func: Callable[[Any], None] | None = None,
            func_path: str | None = None,
            module: str | None = None,
            method: str | None = None,
            cls_name: str | None = None,
            func_args: Dict[Any, Any] | None = None,
            second: int | None = None,
            minute: int | None = None,
            hour: int | None = None,
            day: int | None = None,
            dow: int | None = None,
            week: int | None = None,
            month: int | None = None,
            year: int | None = None,
            profiling_enabled: bool = False
        ):


        runtime_model= RuntimeModel(
            second=second,
            hour=hour,
            minute=minute,
            day=day,
            day_of_week=dow,
            week=week,
            month=month,
            year=year
        )

        function_model = FunctionModel(
            func_path=func_path,
            module=module,
            method=method,
            cls_name=cls_name,
            func=func
        )

        job = JOB(
            key=key,
            trigger=trigger,
            function_model=function_model,
            runtime_model=runtime_model,
            func_args=func_args,
            profiling_enabled=profiling_enabled,
            status=Status.inactive,
        )
        
        job = self.schedule_job(job, key=key.lower())
        return f"new job created! key: '{key}'"

    def remove_job(self, key: str) -> str:
        job = self.get_job(key=key)

        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        job.remove()
        return f"Job with key '{key}' removed"

    def pause_job(self, key: str) -> str:
        job = self.get_job(key=key)

        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        job.pause()
        return f"Job with key '{key}' paused"

    def job_info(self, key: str | None = None, all: bool = False) -> str:
        from theodore.core.theme import console

        jobs: List[Job] = []
        if key:
            job = self.get_job(key=key)

            if job is None:
                raise JobNotFoundError(f"Invalid Job Key. '{key}'")
            
            jobs.append(job)
        elif all:
            jobs = self.get_jobs()

        jobs_info = list()

        for job in jobs:
            job_info = dict(
                jid=str(job.id), 
                next_runtime=str(job.next_run_time), 
                job_name=str(job.name), 
                func=job.func.__name__, 
                kwargs=str(job.kwargs), 
                args=str(job.args), 
                executor=str(job.executor), 
                trigger=str(job.trigger)
                )
            
            jobs_info.append(job_info)

        return json.dumps(jobs_info)

    def resume_job(self, key: str) -> str:
        job = self.get_job(key=key)

        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        job.resume()
        return f"Job with key '{key}' resumed"

    def schedule_job(self, job: JOB, key: str | None= None) -> Job:
        trigger_func = __trigger_format__[job.trigger]
        trigger = trigger_func(job.runtime_model.model_dump())
        func = parse_function(job.function_model.model_dump())

        if is_async(func):
            return self.scheduler.add_job(func, kwargs=job.func_args, trigger=trigger, executor="async", id=key, replace_existing=True)
        return self.scheduler.add_job(func, trigger=trigger, kwargs=job.func_args, executor="sync", id=key, replace_existing=True)
    
    async def start_jobs(self):
        if self.running:
            user_info("Scheduler Already Running")
            return
        user_info("Scheduler Running..")
        self._scheduler_shutdown_event.clear()
        self.scheduler.start()
        self.running = True
        await self._scheduler_shutdown_event.wait()

        self.scheduler.shutdown(wait=True)
        self.running = False
        user_info("Scheduler shutdown.")
        return
    
    def stop_jobs(self):
        self._scheduler_shutdown_event.set()
        return

    def get_job(self, key) -> Job | None:
        return self.scheduler.get_job(job_id=key.lower())
    
    def get_jobs(self):
        return self.scheduler.get_jobs(jobstore="default")
    
# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------

def resolve_module_path(
        *,
        name, 
        commands: dict[str, tuple[str, str | None]] = commands
        ) -> None | Tuple[str, str | None, str]:
    
    if (entry:= commands.get(str(name).upper())) is None:
        return None
    
    target_path, method = entry

    mod, _, cls_or_func = target_path.rpartition(".")

    if resolve_module(mod) is None:
        raise ModuleNotFoundError(f"Module for {name} not found")
    
    if method is None:
        return (mod, None, cls_or_func)

    return (mod, cls_or_func, method)

def parse_cron(runtime: dict) -> CronTrigger:
    return CronTrigger(**runtime, timezone=get_localzone())

def parse_interval(runtime: dict) -> IntervalTrigger:
    interval_registry = {
        "weeks": runtime.get("week") or 0,
        "hours": runtime.get("hour") or 0,
        "days": runtime.get("day") or 0,
        "minutes": runtime.get("minute") or 0,
        "seconds": runtime.get("second") or 0,
        "timezone": get_localzone()
    }
    return IntervalTrigger(**interval_registry)

def parse_function(func_dict: dict) -> Callable[[Any], Any]:

    func = func_dict.pop('func')
    if func is None:
        module_str = func_dict.get('module')
        cls_name = func_dict.get('cls_name')
        method_name = func_dict.get('method')

        module = importlib.import_module(module_str) 
        if cls_name is None:
            func = getattr(module, method_name)
        else:
            cls = getattr(module, cls_name)
            instance = get_instance(cls)
            func = getattr(instance, method_name)
    
    if not getattr(func, "_is_theodore_task", False):
        raise NotRegisteredFunctionError(f"{func.__name__} is not registered as a task for Theodore")

    return func

def is_async(func) -> bool:
    return inspect.iscoroutinefunction(func)

__trigger_format__ = {
    "cron": parse_cron,
    "interval": parse_interval
}

def get_table(jobs: list[dict[str, str]]):

    from rich.table import Table

    table = Table()
    table.leading = 1
    table.show_lines = True

    table.add_column("key", justify="center", header_style="dim cyan")
    table.add_column("next-runtime", justify="center", header_style="dim cyan")
    table.add_column("name", justify="center", header_style="dim cyan")
    table.add_column("func name", justify="center", header_style="dim cyan")
    table.add_column("kwargs", justify="center", header_style="dim cyan")
    table.add_column("args", justify="center", header_style="dim cyan")
    table.add_column("executor", justify="center", header_style="dim cyan")
    table.add_column("trigger", justify="center", header_style="dim cyan")

    for row in jobs:
        table.add_row(*row.values())
    
    return table
