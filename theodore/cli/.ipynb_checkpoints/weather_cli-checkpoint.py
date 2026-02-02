import rich_click as click
import asyncio

from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.theme import console


# from pathlib import Path
# path = Path('~/scripts/theodore/theodore/data/json').absolute()
# path.mkdir(parents=True, exist_ok=True)

# file = path / 'json_txt.json'


# ============= Main Weather CLI ==============
@click.group()
@click.pass_context
def weather(ctx):
    """Get Live Weather Updates"""


@weather.command()
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--temp", type=click.Choice(["f", "c"]), default="c", help="weather condition in temperature metric")
@click.option("--speed", type=click.Choice(['m', 'miles', 'km']), default='km', help='Filter weather table')
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
def current(ctx, temp, location, clear_cache, speed):
    """Get live weather updates around you"""
    
    base_logger.internal('Getting weather manager')
    weather_manager = ctx.obj['weather_manager']

    base_logger.internal('Calling make request call')

    ttl = 23456

    if clear_cache:
        ttl = 0

    response = asyncio.run(weather_manager.make_request(query='forecast', location=location, retries=4, ttl=ttl))
    message = response.get('message')
    

    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        error_logger.error(message)
        return
    
    data = response.get("data")

    table = weather_manager.get_current_weather_table(data, temp=temp, speed=speed)

    console.print(table)

    return

@weather.command()
@click.option("--temp", type=click.Choice(["f", "c"]), default="f", help="weather condition in temperature metric")
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
def forecast(ctx, temp, location, clear_cache):
    """Get future weather update up to 7 day forecasts"""
    base_logger.internal('Getting weather manager')
    weather_manager = ctx.obj['weather_manager']

    base_logger.internal('Calling make request call')

    ttl = 23456
    if clear_cache:
        ttl = 0

    response = asyncio.run(weather_manager.make_request(location=location, retries=4, ttl=ttl))
    message = response.get('message')
    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        error_logger.error(message)
        return
    
    base_logger.internal('getting data from response')
    data = response.get("data")

    base_logger.internal('getting table from weather forcast table')
    table = weather_manager.get_weather_forecast_table(data, temp)

    base_logger.internal('printing table')
    console.print(table)

    return

# # def history(ctx, F, C, location, date):
# #      """Get weather history of location"

@weather.command()
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
def alerts(ctx, location, clear_cache):
    """Get alert for weather conditions around you"""
    base_logger.internal('Getting weather manager')
    weather_manager = ctx.obj['weather_manager']

    base_logger.internal('Calling make request call')

    ttl = 23456
    if clear_cache:
        ttl = 0

    response = asyncio.run(weather_manager.make_request(query='alerts', location=location, retries=4, ttl=ttl))
    message = response.get('message')
    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        error_logger.error(message)
        return
    
    base_logger.internal('getting data from response')
    data = response.get("data")


    base_logger.internal('getting table from weather forcast table')
    table = weather_manager.get_weather_alerts_table(data)

    base_logger.internal('printing table')
    console.print(table)

    return
