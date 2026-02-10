"""
Docstring for theodore.web.routes.jobs

Routes for Scheduled Jobs
- pending
- running
- new job
- update job
- remove job
- cancel job etc
"""

from fastapi import Depends, Request, BackgroundTasks, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from theodore.web.schemas import Job
from theodore.core.state import TheodoreState, get_state

job_app = APIRouter()
job_app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@job_app.get("/", response_class=HTMLResponse, name="jobs_home")
def jobs_home(request: Request):
    return templates.TemplateResponse(request, "job-home.html")

@job_app.get("/new", response_class=HTMLResponse)
def new_job_form(request: Request):
    return templates.TemplateResponse(request, "job-form.html")

@job_app.post("/new", response_class=HTMLResponse, name="new-job")
def new_job_form_submit(request: Request, formdata: Job = Depends(Job.get_form), state: TheodoreState = Depends(get_state)):
    scheduler = state.scheduler
    try:
        scheduler.new_job(**formdata.model_dump())
        return templates.TemplateResponse(request, "success.html", {"message": f"success job created with key {formdata.key}"})
    except ValidationError as e:
        return templates.TemplateResponse(request, "error.html", {"Title": f"Validation Error", "error": str(e)})

@job_app.get("/pending", response_class=HTMLResponse, name="pending")
def validate_user(request: Request, state: TheodoreState = Depends(get_state)):
    scheduler = state.scheduler
    return templates.TemplateResponse(request, "pending-jobs.html", {"data": scheduler.get_jobs()})

@job_app.post("/start", name="start_jobs")
async def start(request: Request, background_tasks: BackgroundTasks, state: TheodoreState = Depends(get_state)):
    scheduler = state.scheduler
    background_tasks.add_task(scheduler.start_jobs)
    return

@job_app.post("/stop", name="stop_jobs")
async def stop(request: Request, state: TheodoreState = Depends(get_state)):
    state.scheduler.stop_jobs()
    return
