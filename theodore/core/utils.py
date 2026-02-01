import re
from datetime import datetime
from functools import partial
from rich.table import Table
from typing import  Annotated
from theodore.core.time_converters import get_localzone


from theodore.core.informers import send_message

# -------------------------
# Global Variables 
# -------------------------

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
    import dateparser 
    _date = dateparser.parse(date)
    if date is None:
        message = 'unable to parse date'
        return send_message(False, message)
    return send_message(True, 'Date Parsed', date=_date)

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

def get_configs_table(data):
    table = Table()
    table.min_width = 100
    table.title = 'Tasks'
    table.show_lines = True

    table.add_column('[bold]category[/]', no_wrap=True)
    table.add_column('[bold]default_path[/]', no_wrap=True)
    table.add_column('[bold]location[/]', no_wrap=True)
    table.add_column('[bold]api_key[/]', no_wrap=True)

    for row in data:
        table.add_row(
            row.category.capitalize(), 
            row.default_path, 
            row.default_location, 
            row.api_key if row.api_key else '[magenta bold]Not set[/]'
        )
    return table

def get_weather_models():
    from pydantic import BaseModel, ConfigDict, Field

    class WeatherModel(BaseModel):
        model_config = ConfigDict(extra='ignore')
        city: str
        country: str
        time_requested: Annotated[datetime, Field(default_factory=partial(datetime.now, tz=get_localzone()))]

    class CurrentModel(WeatherModel):
        model_config = ConfigDict(extra='ignore')

        text: Annotated[str | None, Field(alias='text')]
        temp_c: Annotated[float, Field(alias='temp_c')]
        feels_c: Annotated[float, Field(alias='feels_c')]
        temp_f: Annotated[float, Field(alias='temp_f')]
        feels_f: Annotated[float, Field(alias='feels_f')]
        humidity: Annotated[str, Field(alias='humidity')]
        wind_kph: Annotated[float, Field(alias='wind_kph')]
        wind_mph: Annotated[float, Field(alias='wind_mph')]
        wind_dir: Annotated[float, Field(alias='wind_dir')]

    class AlertsModel(WeatherModel):
        model_config = ConfigDict(extra='ignore')

        headline: Annotated[str | None, Field(alias='headline')]
        event: Annotated[str | None, Field(alias='event')]
        certainty: Annotated[str | None, Field(alias='certainty')]
        urgency: Annotated[str | None, Field(alias='urgency')]
        severity: Annotated[str | None, Field(alias='severity')]
        note: Annotated[str | None, Field(alias='note')]
        effective: Annotated[str | None, Field(alias='effective')]
        description: Annotated[str | None, Field(alias='description')]
        instructions: Annotated[str | None, Field(alias='instructions')]

    class ForecastModel(WeatherModel):
        model_config = ConfigDict(extra='ignore')

        sunrise: Annotated[datetime, Field(alias='sunrise')]
        sunset: Annotated[datetime, Field(alias='sunset')]
        moonrise: Annotated[datetime, Field(alias='moonrise')]
        moonset: Annotated[datetime, Field(alias='moonset')]
        min_temp_c: Annotated[float, Field(alias='min_temp_c')]
        max_temp_c: Annotated[float, Field(alias='max_temp_c')]
        avg_temp_c: Annotated[float, Field(alias='avg_temp_c')]
        min_temp_f: Annotated[float, Field(alias='min_temp_f')]
        max_temp_f: Annotated[float, Field(alias='max_temp_f')]
        avg_temp_f: Annotated[float, Field(alias='avg_temp_f')]
        maxwind_kph: Annotated[float, Field(alias='maxwind_kph')]
        avgvis_km: Annotated[float, Field(alias='avgvis_km')]
        maxwind_mph: Annotated[float, Field(alias='maxwind_mph')]
        avgvis_miles: Annotated[float, Field(alias='avgvis_miles')]
        daily_chance_of_rain: Annotated[float, Field(alias='daily_chance_of_rain')]
        daily_chance_of_snow: Annotated[float, Field(alias='daily_chance_of_snow')]
        daily_will_it_rain: Annotated[bool | int, Field(alias='daily_will_it_rain')]
        daily_will_it_snow: Annotated[bool | int, Field(alias='daily_will_it_snow')]

    return [WeatherModel, CurrentModel, AlertsModel, ForecastModel]