import dateparser 
import json, re
from datetime import datetime
from rich.table import Table
from pathlib import Path
from theodore.core.theme import console
from theodore.core.logger_setup import base_logger, error_logger
import tempfile
from zoneinfo import ZoneInfo


# -------------------------
# Global Variables 
# -------------------------
local_tz = ZoneInfo("GMT")
DATA_DIR = Path(__file__).parent.parent / "data"
JSON_DIR = DATA_DIR / "json"
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
FILE = JSON_DIR / "cache.json"

def user_success(msg):
    return base_logger.info(f'[success]{msg}')

def user_warning(msg):
    return base_logger.warning(f'[warning]{msg}')

def user_error(msg):
    return error_logger.error(f'[error]{msg}')

def user_info(msg):
    return base_logger.info(msg)

def send_message(ok, message=None, date=None, data=None):
    return {'ok': ok, 'message': message, 'data': data, 'date': date}

def normalize_ids(task_id = None, task_ids = None):
    ids = []

    if task_id: ids.append(task_id)
    if task_ids: ids.extend(re.split(r'\D+', task_ids))
    cleaned_ids = []
    for val in ids:
        try:
            cleaned_ids.append(int(val))
        except ValueError:
            continue
    return cleaned_ids

def parse_date(date: str) -> dict:
    date = dateparser.parse(date)
    if date is None:
        message = 'unable to parse date'
        return send_message(False, message)
    return send_message(True, 'Date Parsed', date=date)

def get_task_table(data, deleted=False):
    table = Table()
    table.min_width = 100
    table.title = 'Tasks'
    table.show_lines = True
    
    table.add_column(f'[bold]Task id[/]', no_wrap=True)
    table.add_column(f'[bold]Title[/]', no_wrap=True)
    table.add_column(f'[bold]Description[/]', no_wrap=True)
    table.add_column(f'[bold]Status[/]', no_wrap=True)
    table.add_column(f'[bold]Date Created[/]', no_wrap=True)
    table.add_column(f'[bold]Due Date[/]', no_wrap=True)
    if deleted:
        table.add_column(f'[bold]Date Deleted[/]', no_wrap=True)
    status_map = {"in_progress": "[green]", "pending": "[bold red]", "not_completed": "[bold cyan]"}
    for task in data:
        status = task.get("status")
        style = status_map.get(status, "[white]")
        task_id = f'{style}{task.get("task_id")}[/]'
        task_title = f'{style}{task.get("title")}[/]'
        description = task.get('description')

        description = f'{style}{"-".join((description).split(","))}[/]' if description else f'[bold cyan]{description}[/]'
        status = f'{style}{status}[/]'
        due_date = f'{style}{task.get("due")}[/]'
        date_created = f'{style}{str(task.get("date_created"))}[/]' 

        if deleted:
            date_deleted = f'{style}{str(task.get("date_deleted"))}[/]'
            row_data = (task_id, task_title, description, status, date_created, due_date, date_deleted)
        else:
            row_data = (task_id, task_title, description, status, date_created, due_date)

        table.add_row(*row_data)

    return table


def get_current_weather_table(**kwargs):
    pass


def get_current_weather_table(**kwargs):
    pass