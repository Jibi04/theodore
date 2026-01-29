import click
import rich_click as click
import asyncio

from theodore.cli.async_click import AsyncCommand
from theodore.core.utils import base_logger, user_error, DBTasks
from theodore.core.theme import console
from theodore.ai.dispatch import WEATHER
from theodore.models.configs import ConfigTable

# def get_location():
#     loop = asyncio.get_running_loop()
#     loop.

# ============= Main Weather CLI ==============
@click.group()
@click.pass_context
def weather(ctx):
    """Get Live Weather Updates"""
    config_manager = DBTasks(ConfigTable)
    weather_defaults = asyncio.run(config_manager.get_features({'category': 'weather'}, first=True))
    ctx.obj['default_location'] = weather_defaults.default_location



@weather.command(cls=AsyncCommand)
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--temp", type=click.Choice(["f", "c"]), default="c", help="weather condition in temperature metric")
@click.option("--speed", type=click.Choice(['m', 'miles', 'km']), default='km', help='Filter weather table')
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
async def current(ctx, temp, location, clear_cache, speed):
    """Get live weather updates around you"""

    if not location:
        location = ctx.obj['default_location']

    response = await WEATHER.make_request(query='forecast', location=location, retries=4)

    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        user_error(response.get('message'))
        return
    
    data = response.get("data")
    table = WEATHER.get_current_weather_table(data, temp=temp, speed=speed)

    console.print(table)
    return

@weather.command(cls=AsyncCommand)
@click.option("--temp", type=click.Choice(["f", "c"]), default="f", help="weather condition in temperature metric")
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
async def forecast(ctx, temp, location, clear_cache):
    """Get future weather update up to 7 day forecasts"""
    base_logger.internal('Getting weather manager')
    WEATHER = ctx.obj['WEATHER']

    base_logger.internal('Calling make request call')

    response = await WEATHER.make_request(location=location, retries=4)
    if not response.get('ok'):
        base_logger.internal(f"Failed Aborting")
        user_error(response.get('message'))
        return
    
    data = response.get("data")
    table = WEATHER.get_weather_forecast_table(data, temp)

    console.print(table)
    return

# # def history(ctx, F, C, location, date):
# #      """Get weather history of location"

@weather.command(cls=AsyncCommand)
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
async def alerts(ctx, location, clear_cache):
    """Get alert for weather conditions around you"""
    base_logger.internal('Getting weather manager')
    WEATHER = ctx.obj['WEATHER']

    base_logger.internal('Calling make request call')
    response = await WEATHER.make_request(query='alerts', location=location, retries=4)
    if not response.get('ok'):
        user_error(response.get('message'))
        return
    data = response.get("data")

    table = WEATHER.get_weather_alerts_table(data)
    console.print(table)

    return
