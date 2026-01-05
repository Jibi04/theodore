import click
import rich_click as click
import asyncio

from theodore.cli.async_click import AsyncCommand
from theodore.managers.weather_manager import Weather_manager
from theodore.core.utils import base_logger, user_error
from theodore.core.theme import console

weather_manager = Weather_manager()

# ============= Main Weather CLI ==============
@click.group()
@click.pass_context
def weather(ctx):
    """Get Live Weather Updates"""


@weather.command(cls=AsyncCommand)
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--temp", type=click.Choice(["f", "c"]), default="c", help="weather condition in temperature metric")
@click.option("--speed", type=click.Choice(['m', 'miles', 'km']), default='km', help='Filter weather table')
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
async def current(ctx, temp, location, clear_cache, speed):
    """Get live weather updates around you"""

    ttl = 23456

    if clear_cache:
        ttl = 0
    response = await weather_manager.make_request(query='forecast', location=location, retries=4)
    message = response.get('message')
    

    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        user_error(message)
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
        user_error(message)
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
        user_error(message)
        return
    
    base_logger.internal('getting data from response')
    data = response.get("data")


    base_logger.internal('getting table from weather forcast table')
    table = weather_manager.get_weather_alerts_table(data)

    base_logger.internal('printing table')
    console.print(table)

    return
