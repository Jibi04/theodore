# set schedules plan trips, plan daily routines etc
from enum import Enum
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from typing import Coroutine, Any, Callable, Dict, List




class InvalidScheduleTimeError(Exception):...
class InvalidCoroutineFunctionError(Exception):...
class JobNotFoundError(Exception):...

    
class Status(Enum):
    cancelled = "cancelled"
    active = "active"
    inactive = "in_active"


class Trigger(Enum):
    interval = "interval"
    cron = "cron"



class Job(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    key: Any
    func: Callable[..., Coroutine[Any, Any, Any]]
    dow: int | None = None
    next_runtime: float
    kwargs: Dict[Any, Any] | List[Dict[str, Any]] | None = None
    trigger: Trigger = Trigger.interval
    runtime_registry: Dict[str, Any]
    profiling_enabled: bool = False
    status: Status = Status.inactive
    date_created: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobManager:
    def __init__(self):
        self._all_jobs: set[Job] = set()

    def add_job(
            self,
            key: Any,
            func: Callable[..., Coroutine[Any, Any, Any]], 
            next_runtime: float,
            kwargs: Dict[Any, Any] | None = None,
            **extra
        ) -> Job:
        
        if next_runtime is None:
            raise InvalidScheduleTimeError("Cannot create Job without specific runtime")
        try:
            job = Job(
                key=key,
                func=func, 
                kwargs=kwargs, 
                next_runtime=next_runtime,
                **extra
            )
        except ValidationError:
            # Job add should catch error and log error, not crash the scheduler.
            raise

        self._all_jobs.add(job)
        return job

    def modify_job(self, key, **data):
        job = self.verify_key(key)
        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        try:
            new_job = self.validate_job(job=job, values=data)

            self._all_jobs.discard(job)
            self._all_jobs.add(new_job)
        except ValidationError:
            raise

    def remove_job(self, key):
        job = self.verify_key(key)
        if job is None:
            raise JobNotFoundError(f"Invalid Job Key. '{key}'")
        
        self._all_jobs.discard(job)

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
        for job in self._all_jobs:
            if job.key == key:
                return job
        return None
    
 