# set schedules plan trips, plan daily routines etc
from enum import Enum
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from typing import Any, Callable, Dict, List, Literal




class InvalidScheduleTimeError(Exception):...
class InvalidCoroutineFunctionError(Exception):...
class JobNotFoundError(Exception):...

    
class Status(Enum):
    cancelled = "cancelled"
    active = "active"
    inactive = "in_active"



class Job(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    key: Any
    func: Callable[[Any], None]
    next_runtime: float
    trigger: Literal["interval", "cron"]
    runtime_registry: Dict[str, Any]
    func_args: Dict[Any, Any] | List[Dict[str, Any]] | None = None
    dow: int | None = None
    profiling_enabled: bool = False
    status: Status = Status.inactive
    date_created: datetime = Field(default_factory=lambda: datetime.now(UTC))



class JobManager:
    def __init__(self):
        self._all_jobs: Dict[str, Job] = {}

    def add_job(
            self,
            key: Any,
            func: Callable[..., Any], 
            next_runtime: float,
            func_args: Dict[Any, Any] | None = None,
            **extra
        ) -> Job:
        
        if next_runtime is None:
            raise InvalidScheduleTimeError("Cannot create Job without specific runtime")
        try:
            job = Job(
                key=key,
                func=func, 
                func_args=func_args, 
                next_runtime=next_runtime,
                **extra
            )
            self._all_jobs[job.key] = job
            return job
        except ValidationError:
            # Job add should catch error and log error, not crash the scheduler.
            raise


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
    
 