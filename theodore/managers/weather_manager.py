import fake_user_agent
import httpx, time, os, asyncio

from dotenv import load_dotenv
from datetime import datetime
from rich.table import Table
from theodore.core.theme import console
from theodore.core.logger_setup import base_logger
from theodore.core.utils import send_message, DATA_DIR, user_error, DB_tasks
from theodore.models.base import engine
from theodore.models.configs import Configs_table
from theodore.models.weather import Current, Alerts, Forecasts
from theodore.managers.configs_manager import Configs_manager
from theodore.managers.cache_manager import Cache_manager
from httpx import ConnectTimeout, ReadTimeout, ReadError, DecodingError


load_dotenv()
configs = Configs_manager()
ua = fake_user_agent.user_agent()
manager = Configs_manager()


CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FILE_PATH = CACHE_DIR / 'dummy.cache'

class Weather_manager:
    async def make_request(self, query, location: str = None, retries: int =3, clear_cache = False):
        """Make weather request from the weather API 

        - headers: special key_word headers you'd like to add

        returns dict with request response and validation response
        for attempt in range(retries + 1):

        """
        base_logger.internal('Attempting weather request')
        with DB_tasks(Configs_table) as config_manager:
            defaults = await config_manager.get_features({'category': 'weather'}, first=True)
        if location is None:
            location = defaults.default_location
            if not location:
                    user_error.error("Unable to fetch no location to query weather data from.")
                    return send_message(False, message='no location')
            
        base_logger.debug(f'Location loaded - {location}')

        ttl = 60 * 30
        cache = Cache_manager(ttl)

        if clear_cache:
            cache.clear_cache()


        cache_key = f"{location}:{query}"
        data = cache.get_cache(cache_key)
        if data:
            base_logger.debug(f'Cache found for {location} data - {data}')
            return send_message(True, data=data, message='this is cache')

        base_logger.internal(f'\'{cache_key}\' data expired or not in cache. cache-response \'{data}\'')
        with console.status(f'Fetching weather data for {location.capitalize()}', spinner='arc'):
            for attempt in range(retries + 1):
                try:
                    API_KEY  = os.getenv('weather_api_key') or defaults.api_key
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
                        data = response.json()
                        base_logger.debug(f'weather data jsonified {data}')
                except (ConnectTimeout, ReadTimeout, ReadError,) as e:
                    if attempt == retries:
                        base_logger.internal(f'{type(e).__name__} error. Aborting...')
                        return send_message(False, message='A server error occurred')
                    time.sleep(1)
                except httpx.HTTPError:
                    continue
                except DecodingError:
                        base_logger.debug(f"Recieved non json-Response from Serve. {str(e)}")
                        return send_message(False, message=f"Recieved non json-Response from server {response.status_code}")
                except Exception as e:
                    base_logger.internal(f'{type(e).__name__} error. Aborting...')
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
        
            base_logger.debug(f'creating new cache-object {cache_key} value {data}')

            coroutines =[]
            if 'current' in data: coroutines.append(cache.create_new_cache(self.to_dict(data, current=True), current=True))
            if 'forecast' in data: coroutines.append(cache.create_new_cache(self.to_dict(data, forecast=True), forecasts=True))
            if query == 'alerts': coroutines.append(cache.create_new_cache(self.to_dict(data, alerts=True), alerts=True))
            
            await asyncio.gather(*coroutines)
            return send_message(True, data=data)
        

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
    
    def to_dict(self, data, alerts=False, current=False, forecast=False):
        location = data.get('location', {})
        if alerts:
            alert = data.get('alerts').get('alert')
            return {
            "headline" : alert.get('headline'),
            "event" : alert.get('event'),
            "certainty" : alert.get('certainty'),
            "urgency" : alert.get('urgency'),
            "severity" : alert.get('severity'),
            "note" : alert.get('note'),
            "desc" : alert.get('desc'),
            "instruction" : alert.get('instruction'),
            "city": location.get('name'),
            "country": location.get('country'),
        }
        
        if forecast:
            forecast = data.get('forecast', {}).get('forecastday', [])[0]
            day = forecast.get('day', {})
            astro = forecast.get('astro', {})
            return {
                    "sunrise": astro.get('sunrise'),
                    "sunset": astro.get('sunset'),
                    "moonrise": astro.get('moonrise'),
                    "moonset": astro.get('moonset'),
                    "min_temp_c": day.get('mintemp_c', {}),
                    "max_temp_c": day.get('maxtemp_c', {}),
                    "avg_temp_c": day.get('avgtemp_c', {}),
                    "min_temp_f": day.get('mintemp_f', {}),
                    "max_temp_f": day.get('maxtemp_f', {}),
                    "avg_temp_f": day.get('avgtemp_f', {}),
                    "maxwind_kph":day.get('maxwind_kph', {}),
                    "avgvis_km": day.get('avgvis_km', {}),
                    "maxwind_mph": day.get('maxwind_mph', {}),
                    "avgvis_miles": day.get('avgvis_mph', {}),
                    "daily_chance_of_rain": day.get('daily_chance_of_rain', {}),
                    "daily_chance_of_snow": day.get('daily_chance_of_snow', {}),
                    "daily_will_it_rain": day.get('daily_will_it_rain', {}),
                    "daily_will_it_snow": day.get('daily_will_it_snow', {}),
                    "city": location.get('name'),
                    "country": location.get('country'),
            }
        
        if current:
            current = data.get("current", {})
            return {
                        "text": current.get('condition').get('text'),
                        "temp_c": current.get('temp_c'),
                        "feels_c": current.get('feels_c'),
                        "temp_f": current.get('temp_f'),
                        "feels_f": current.get('feels_f'),
                        "humidity": current.get('humidity'),
                        "wind_kph": current.get('wind_kph'),
                        "wind_mph": current.get('wind_mph'),
                        "wind_dir": current.get('wind_dir'),
                        "city": location.get('name'),
                        "country": location.get('country'),
            }
            