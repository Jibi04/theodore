import rich_click as click

from theodore.cli.async_click import AsyncCommand
from theodore.core.theme import console
from theodore.core.informers import user_error, base_logger
from theodore.core.lazy import get_weather_manager, WeatherManagement

# def get_location():
#     loop = asyncio.get_running_loop()
#     loop.

# ============= Main Weather CLI ==============
@click.group()
@click.pass_context
def weather(ctx: click.Context):
    """Get Live Weather Updates"""
    ctx.ensure_object(dict)
    ctx.obj['manager'] = get_weather_manager()



@weather.command(cls=AsyncCommand)
@click.option("--location", "-l", type=str, help="You may pass lat and lon, zipcode, postcode, city name, IP, etc")
@click.option("--temp", type=click.Choice(["f", "c"]), default="c", help="weather condition in temperature metric")
@click.option("--speed", type=click.Choice(['m', 'miles', 'km']), default='km', help='Filter weather table')
@click.option("--clear-cache", "-clr", is_flag=True)
@click.pass_context
async def current(ctx: click.Context, temp, location, clear_cache, speed):
    """Get live weather updates around you"""
    WEATHER: WeatherManagement = ctx.obj['manager']

    response = await WEATHER.make_request(query='forecast', location=location, retries=4)

    if not response.get('ok'):
        base_logger.debug(f"Failed Aborting")
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
async def forecast(ctx: click.Context, temp, location, clear_cache):
    """Get future weather update up to 7 day forecasts"""
    base_logger.debug('Getting weather manager')
    WEATHER: WeatherManagement = ctx.obj['manager']

    base_logger.debug('Calling make request call')

    response = await WEATHER.make_request(query="forecast", location=location, retries=4)
    if not response.get('ok'):
        base_logger.debug(f"Failed Aborting")
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
async def alerts(ctx: click.Context, location, clear_cache):
    """Get alert for weather conditions around you"""
    base_logger.debug('Getting weather manager')
    WEATHER: WeatherManagement = ctx.obj['manager']

    base_logger.debug('Calling make request call')
    response = await WEATHER.make_request(query='alerts', location=location, retries=4)
    if not response.get('ok'):
        user_error(response.get('message'))
        return
    data = response.get("data")

    table = WEATHER.get_weather_alerts_table(data)
    console.print(table)

    return
