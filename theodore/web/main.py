from fastapi import FastAPI, Request, BackgroundTasks
from theodore.core.state import TheodoreState, lifespan
from typing import Literal

theodore = FastAPI(lifespan=lifespan)

@theodore.get("/", include_in_schema=False)
def print_hello():
    return {"Hi I'm theodore": "Theodore API Transition"}

@theodore.get("/jobs/pending")
def validate_user(request: Request):
    state: TheodoreState = request.app.state.internals
    return f"Pending Jobs: {state.scheduler.get_jobs()}"

@theodore.api_route("/jobs/new", methods=["GET", "POST"])
async def new_job(
    request: Request,
    func_path: str | None = None, 
    hour: int | None = None, 
    minute: int = 10, 
    day: int | None = None, 
    trigger: Literal["cron", "interval"] = "interval",
    key: str =  "api test",
    kwargs: dict | None  = None
    ):
    state: TheodoreState = request.app.state.internals
    scheduler = state.scheduler
    scheduler.new_job(
        key=key,
        func_path=func_path,
        trigger=trigger,
        hour=hour,
        minute=minute,
        day=day,
        func_args=kwargs
    )
    return "Task created"

@theodore.api_route("/jobs/start", methods=["GET", "POST"])
async def start(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    scheduler = state.scheduler
    background_tasks.add_task(scheduler.start_jobs)
    return "Jobs started"

    
