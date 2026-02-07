from typing import Literal
from fastapi import FastAPI, Request, BackgroundTasks
from theodore.core.state import TheodoreState, lifespan

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
    return f"{key} Task created."

@theodore.api_route("/jobs/start", methods=["GET", "POST"])
async def start(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    scheduler = state.scheduler
    background_tasks.add_task(scheduler.start_jobs)
    return "Jobs started"

@theodore.api_route("/jobs/stop", methods=["GET", "POST"])
async def stop(request: Request):
    state: TheodoreState = request.app.state.internals
    scheduler = state.scheduler
    scheduler.stop_jobs()
    return "Jobs stopped"

@theodore.get("/sessions/new")
async def get_session(request: Request):
    state: TheodoreState = request.app.state.internals
    await state.get_session()
    return "Yep We've got it"

@theodore.get("/processes/start")
async def start_process(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    worker = state.worker()
    background_tasks.add_task(worker.start_processes)
    return "Processes Started"

@theodore.get("/processes/stop")
async def stop_process(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    worker = state.worker()
    await worker.stop_processes()
    return "Processes Stopped"

