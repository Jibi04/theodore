# set schedules plan trips, plan daily routines etc
from enum import Enum
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator, model_validator
from typing import Any, Callable, Dict, List, Literal, Annotated, Tuple

from theodore.core.exceptions import JobNotFoundError
from theodore.ai.dispatch import resolve_module, commands


    
class Status(Enum):
    cancelled = "cancelled"
    active = "active"
    inactive = "in_active"

class RuntimeModel(BaseModel):
    hour: Annotated[int | None, Field(ge=1, le=59)]
    minute: Annotated[int | None, Field(ge=1, le=59)]
    second: Annotated[int | None, Field(ge=1, le=59)]
    day: Annotated[int | None, Field(ge=1, le=31)]
    day_of_week: Annotated[int | None, Field(ge=0, le=6)]
    week: Annotated[int | None, Field(ge=1, le=53)]
    month: Annotated[int | None, Field(ge=1, le=12)]
    year: Annotated[int | None, Field(max_length=4, max_digits=4)]

class FunctionModel(BaseModel):
    func_path: str | None = None
    module: str | None = None
    method: str | None = None
    cls_name: str | None = None
    func: Callable[[Any], None] | None = None

    @field_validator("func_path", mode="after")
    def extract_paths(cls, v, info):
        if v is None:
            return v
        
        try:
            entry = resolve_module_path(name=v)
            if entry is None:
                raise ValueError(f"Function path {v} could not be resolved")
        except ModuleNotFoundError:
                raise ValueError(f"Module {v} Not Found")
        
        module, cls_name, method = entry

        info.data["module"] = module
        info.data["cls_name"] = cls_name
        info.data["method"] = method

        return v
    
    @model_validator(mode="before")
    @classmethod
    def validate_func(cls, data):
        if data.get("func") is None and data.get("func_path") is None:
            raise ValueError(f"Callable Function and Function Path cannot be None.")
        
        return data

class Job(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    key: str
    trigger: Literal["interval", "cron"]
    function_model: FunctionModel
    runtime_model: RuntimeModel
    func_args: Dict[Any, Any] | List[Dict[str, Any]] | None = None
    profiling_enabled: bool = False
    status: Status = Status.inactive
    date_created: datetime = Field(default_factory=lambda: datetime.now(UTC))

class JobManager:
    def __init__(self):
        self._all_jobs: Dict[str, Job] = {}

    def add_job(self, job: Job): 
        self._all_jobs[job.key] = job

    def modify_job(self, key, **data):
        job = self.verify_key(key)
        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        try:
            new_job = self.validate_job(job=job, values=data)

            self._all_jobs.pop(job.key)
            self._all_jobs[new_job.key] = new_job
        except ValidationError:
            raise

    def remove_job(self, key):
        job = self.verify_key(key)
        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        self._all_jobs.pop(job.key)

    def resume_job_execution(self, key):
        job = self.verify_key(key)
        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        

    def validate_job(self, job: Job, values: Dict) -> Job:
        _job = job.model_dump()
        for key, val in values.items():
            _job[key]= val
        return Job.model_validate(_job)

    def verify_key(self, key) -> Job | None:
        for k, job in self._all_jobs.items():
            if k == key.lower():
                return job
        return None
    
def resolve_module_path(name, commands: dict[str, tuple[str, str | None]] = commands) -> None | Tuple[str, str | None, str]:
    if (entry:= commands.get(name)) is None:
        return None
    
    target_path, method = entry

    mod, _, cls_or_func = target_path.rpartition(".")

    if resolve_module(mod) is None:
        raise ModuleNotFoundError(f"Module for {name} not found")
    
    if method is None:
        return (mod, None, cls_or_func)

    return (mod, cls_or_func, method)