from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from theodore.core.state import TheodoreState, lifespan

from theodore.web.jobs import job_app

theodore = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
theodore.mount("/static", StaticFiles(directory="static"), name="static")
theodore.include_router(job_app, prefix="/jobs")

@theodore.get("/", include_in_schema=False, response_class=HTMLResponse)
def welcome(request: Request):
    return templates.TemplateResponse(request, "home.html")

@theodore.get("/sessions/new")
async def get_session(request: Request):
    state: TheodoreState = request.app.state.internals
    await state.get_session()
    return "Yep We've got it"

@theodore.get("/processes/start", name="start_processes")
async def start_process(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    worker = state.worker()
    background_tasks.add_task(worker.start_processes)
    return "Processes Started"

@theodore.get("/processes/stop", name="stop_processes")
async def stop_process(request: Request, background_tasks: BackgroundTasks):
    state: TheodoreState = request.app.state.internals
    worker = state.worker()
    await worker.stop_processes()
    return "Processes Stopped"