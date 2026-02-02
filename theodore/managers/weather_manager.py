import fake_user_agent
import httpx, time, os
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from rich.table import Table
from theodore.core.theme import console
from theodore.core.logger_setup import base_logger
from theodore.core.informers import send_message, user_error
from theodore.core.db_operations import DBTasks
from theodore.core.utils import get_weather_models
from theodore.models.base import get_async_session
from theodore.models.configs import ConfigTable
from theodore.models.weather import Current, Alerts, Forecasts
from sqlalchemy import select, or_
from theodore.core.paths import DATA_DIR
from theodore.core.time_converters import get_localzone
from theodore.managers.configs_manager import ConfigManager
from httpx import ConnectTimeout, ReadTimeout, ReadError
from typing import Type, TypeVar

WeatherModel, CurrentModel, AlertsModel, ForecastModel = get_weather_models()
DOTENV_PATH = find_dotenv()
load_dotenv(DOTENV_PATH)

configs = ConfigManager()
ua = fake_user_agent.user_agent()
manager = ConfigManager()

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
T = TypeVar('T', bound=WeatherModel)

FILE_PATH = CACHE_DIR / 'dummy.cache'

class WeatherManager:

    def validate_data(self, schema: Type[T], raw_data: dict, extra_context: dict):
        return schema(**raw_data, **extra_context).model_dump()

    async def make_request(self, query, location: str = None, retries: int =3, clear_cache = False):
        """Make weather request from the weather API 

        - headers: special key_word headers you'd like to add

        returns dict with request response and validation response
        for attempt in range(retries + 1):

        """
        base_logger.internal('Attempting weather request')
        weather_map = {
            'forecast': select(Forecasts),
            'current': select(Current),
            'alerts': select(Alerts)
        }

        async with get_async_session() as session:
            NOW = datetime.now(tz=get_localzone())
            table = weather_map[query]
            stmt = (table
                    .where(or_(table.c.city == location, table.c.country == location))
                    .where(table.c.time_requested >= NOW - timedelta(minutes=30))
                    .order_by(table.c.time_requested.desc())
                    .limit(1)
                    )
            result = await session.execute(stmt)
            cache = result.mappings().first()

        if cache is not None:
            return send_message(True, data=cache)

        with DBTasks(ConfigTable) as config_manager:
            defaults = await config_manager.get_features({'category': 'weather'}, first=True)

        if location is None:
            location = defaults.default_location
            if not location:
                    user_error.error("Unable to fetch no location to query weather data from.")
                    return send_message(False, message='no location')
        data = {}
        
        with console.status(f'Fetching weather data for {location.capitalize()}', spinner='arc'):
            for attempt in range(retries + 1):
                try:
                    API_KEY  = os.getenv('WEATHER_API_KEY') or defaults.api_key
                    if not API_KEY:
                        base_logger.internal("[!] Missing environment variable: 'weather_api_key' aborting")
                        return send_message(False, message="Missing environment variable: 'weather_api_key'")
                    
                    url = f"https://api.weatherapi.com/v1/{query}.json"
                    params = {
                        "q": location,
                        "key": API_KEY,
                    }
                    headers = {
                        "User-Agent": ua
                    }
                    base_logger.debug(f'making {query} request for {location}')
                    async with httpx.AsyncClient(timeout=30) as client:
                        base_logger.internal('awaiting response from client')
                        response = await client.get(url=url, params=params, headers=headers)
                        response.raise_for_status() 
                        base_logger.debug(f'weather data jsonified {data}')
                except (ConnectTimeout, ReadTimeout, ReadError,) as e:
                    if attempt == retries:
                        base_logger.internal(f'{type(e).__name__} error. Aborting...')
                        return send_message(False, message='A server error occurred')
                    time.sleep(1)
                except httpx.HTTPError:
                    continue
                except Exception as e:
                    user_error(f'{type(e).__name__} error. Aborting...')
                    return send_message(False, message=f'A  error occurred')
                
            if not data:
                return send_message(False, message=f'Unable to get weather data for {location}')
            
            if 'error' in data:
                base_logger.internal('An Httpx error occurred getting error message...')
                error_info = data['error']
                error_code = error_info.get("code", "N/A")
                error_message = error_info.get("message", "Unknown API Error.")

                if error_code in (1002, 2006):
                    final_message = "API key error - Confirm weather-api-key in environment variable"
                elif error_code == 1006:
                    final_message = f"No location found matching '{location}'."
                else:
                    final_message = f"{error_code} - {error_message}"
                return send_message(False, message=f"[red bold][!] An API error occurred:[/red bold] {final_message}")

            registry = {
                'current': {'table': Current, 'schema': CurrentModel, 'path': ['current']},
                'forecast': {'table': Forecasts, 'schema': ForecastModel, 'path': ['forecast', 'forecastday', 0, {'split': ['day', 'astro']}]},
                'alerts': {'table': Alerts, 'schema': AlertsModel, 'path': ['alerts', 'alert']}
            }

            reg = registry[query]
            nested_data = data
            extra_context = {}

            for key in reg['path']:
                if key == 'split':
                    extra_context = nested_data.get('astro')
                    nested_data = nested_data.get('day')
                if key.isdigit():
                    nested_data = nested_data[key]
                nested_data = nested_data.get(key, {})

            extra_context.update(data.get('location', {}))
            table = reg['table']
            data_dict = self.validate_data(reg['schema'], raw_data=nested_data, extra_context=extra_context)
            
            await DBTasks(table).upsert_features(values=data_dict)
            return send_message(True, data=data_dict)
        

    def get_current_weather_table(self, data, temp = None, speed= None):
        """Table designed to show beautiful display weather condition summary"""

        current = data.get("current", {})
        location = data.get("location", {})
        temp_symbol = "C" if temp == "c" else "F"
        temp_data = 'temp_c' if temp == 'c' else 'temp_f'
        feel = "feelslike_c" if temp_symbol == "C" else "feelslike_f"
        table = Table()

        table.width = 60
        table.show_header = False

        table.add_row(f"{location.get('country')} Weather", style='bold')
        table.add_row(f"[bold]City: [/]{location.get('name')}")
        table.add_row(f"[bold]Cloud composition 🌡 [/]: {current.get('condition').get('text')}")
        table.add_section()
        table.add_row(f"[bold]Temp: [/bold]{current.get(temp_data)}°{temp_symbol}   Feels ({current.get(feel)}°{temp_symbol})")
        table.add_row(f"[bold]Humidity: [/]{current.get('humidity')}%")
        table.add_row(f"[bold]Wind Speed: [/]{current.get('wind_kph')}km/h")
        table.add_row(f"[bold]Wind direction: [/]{current.get('wind_dir')}")
        
        return table


    def get_weather_forecast_table(self, data, temp= None, speed=None):
        forecast = data.get('forecast', {}).get('forecastday', [])[0]
        if not forecast:
            return "No forecasts at this time"

        day = forecast.get('day')
        astro = forecast.get('astro') 

        table = Table()
        table.show_header = False

        table.add_row(f"Sunrise at: {astro.get('sunrise')}")
        table.add_row(f"Sunset at: {astro.get('sunset')}")
        table.add_row(f"Moonrise at: {astro.get('moonrise')}")
        table.add_row(f"Moonset at: {astro.get('moonset')}")
        table.add_row(f"Moonphase: {astro.get('moon_phase')}")
        table.add_row(f"Moon illumination: {astro.get('moon_illumination')}")

        # ----- Celcius filter -------------
        if temp == 'c':
            table.add_row(f"Min temp: {day.get('mintemp_c', {})}°C")
            table.add_row(f"Max temp: {day.get('maxtemp_c', {})}°C")
            table.add_row(f"Avg temp: {day.get('avgtemp_c', {})}°C")

        # ----- Farenheit filter -------------
        if temp == 'f':
            table.add_row(f"Min temp: {day.get('mintemp_f', {})}°F")
            table.add_row(f"Max temp: {day.get('maxtemp_f', {})}°F")
            table.add_row(f"Avg temp: {day.get('avgtemp_f', {})}°F")

        # --------- Km filter -----------------
        if speed in ('miles', 'mph'):
            table.add_row(f"Max wind speed: {day.get('maxwind_kph', {})}kph")
            table.add_row(f"Avg Vis: {day.get('avgvis_km', {})}km")

        # ---------- Miles filter --------------
        if  speed == 'kph':
            table.add_row(f"Max wind speed: {day.get('maxwind_mph', {})}mph")
            table.add_row(f"Avg Vis: {day.get('avgvis_miles', {})}mph")


        chance_of_rain = f"{day.get('daily_chance_of_rain', {})}"
        chance_of_snow = f"{day.get('daily_chance_of_snow', {})}"
        it_will_rain = f"{day.get('daily_will_it_rain', {})}"
        it_will_snow = f"{day.get('daily_will_it_snow', {})}"

        
        # ------------ General data ---------
        table.add_row(f"Total precipitation: {day.get('totalprecip_mm', {})}mm")
        table.add_row(f"Total Precipitation: {day.get('totalprecip_in', {})}in")

        table.add_row(f"Avg Humidity: {day.get('avghumidity', {})}")
        table.add_row("Will it rain: " + "Yes" if it_will_rain else "No")
        table.add_row(f"Chance of rain: {chance_of_rain}%")
        table.add_row("Will it snow: " + "Yes" if it_will_snow else "No")

        if it_will_snow:
            table.add_row(f"Total Snow: {day.get('totalsnow_cm', {})}cm")
        table.add_row(f"Chance of snow: {chance_of_snow}%")


        return table


    def get_weather_alerts_table(self, data) -> dict:

        alerts = data.get('alerts').get('alert')
        if not alerts:
            return "[!] No alerts at this time"

        table = Table()
        table.show_header=False
        table.title = f"Weather alerts {data.get('location').get('name')}"

        for alert in alerts:
                table.add_row(f"[bold white]Headline[/]: {alert.get('headline')}", style="cyan")
                table.add_row(f"[bold white]Event[/]: {alert.get('event')}", style="cyan")
                table.add_row(f"[bold white]Certainty[/]: {alert.get('certainty')}", style="cyan")
                table.add_row(f"[bold white]Urgency[/]: {alert.get('urgency')}", style="cyan")
                table.add_row(f"[bold white]Severity[/]: {alert.get('severity')}", style="cyan")
                table.add_row(f"[bold white]Note[/]: {alert.get('note')}", style="cyan")
                table.add_row(f"[bold white]Effective[/]: {datetime.fromisoformat(alert.get('effective')).strftime('%Y-%m-%d %H:%M:%S')}", style="cyan")
                table.add_row(f"[bold white]Description[/]: {alert.get('desc')}", style="cyan")
                table.add_row(f"[bold white]Instructions[/]: {alert.get('instruction')}", style="magenta")

        return table
    