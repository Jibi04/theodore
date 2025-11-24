from pathlib import Path
import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAnyOptionGroup
from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.core.utils import user_error, user_success

cli_defaults()

@click.group(context_settings=dict())
@click.pass_context
async def config(ctx):
    """Adjust configuration settings"""


@config.command()
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p", default='~')
@click.argument("category", type=click.Choice(['weather', 'downloads', 'tasks']))
@click.pass_context
async def set(ctx, category, default_location, api_key, default_path):
    """set new config info"""
    base_logger.internal('Getting option from ctx manager')
    args_map = {"category": category}

    base_logger.internal('cleaning parameters')

    if default_location: args_map["default_location"] = default_location.strip()
    if api_key: args_map['api_key'] = api_key
    if default_path: args_map["default_path"] = str(Path(default_path.strip()).expanduser()) 

    configs_manager = ctx.obj['configs_manager']
    if not configs_manager:
        user_error('Configs Manager not found')

    try:
        response = await configs_manager.new_category(**args_map)
        msg = response.get('message')

        if not response.get('ok'):
            base_logger.internal('An error occurred with the db Aborting ...')
            user_error(msg)
            return
        user_success(msg)
    except Exception as e:
        base_logger.internal(f'{type(e).__name__} error Aborting ...')
        user_error(str(e))
    return


@config.command()
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p", default='~')
@click.argument("category", type=click.Choice(['weather', 'downloads', 'tasks']))
@click.pass_context
async def update(ctx, category, default_location, api_key, default_path):
    """Update configs settings"""
    base_logger.internal('Getting option from ctx manager')
    args_map = {"category": category}

    base_logger.internal('cleaning parameters')

    if default_location: args_map["default_location"] = default_location.strip()
    if api_key: args_map['api_key'] = api_key
    if default_path: args_map["default_path"] = str(Path(default_path.strip()).expanduser()) 

    configs_manager = ctx.obj['config_manager']
    if not configs_manager:
        user_error('Configs Manager not found')

    try:
        response = await configs_manager.update_db_configs(**args_map)
        msg = response.get('message', '')

        if not response.get('ok'):
            base_logger.internal('An error occurred with the db Aborting ...')
            user_error(msg)
            return
        user_success(msg)
    except Exception as e:
        base_logger.internal(f'{type(e).__name__} error Aborting ...')
        user_error(str(e))
    return


@config.command()
@optgroup.group(name='required action', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='show all configs')
@optgroup.option('--weather', '-w', is_flag=True, help='show all weather configs')
@optgroup.option('--downloads', '-d', is_flag=True, help='show all downloads configs')
@optgroup.option('--tasks', '-t', is_flag=True, help='show all configs')
@click.pass_context
async def show_configs(ctx, all, weather, downloads, tasks):
    """Show category configurations"""

    category = None
    if weather: category = 'weather'
    if downloads: category = 'downloads'
    if tasks: category = 'tasks'

    config_manager = ctx.obj['config_manager']


    try:
        if category: 
            db_response = await config_manager.show_configs(category=category)
        else:
            db_response = await config_manager.load_db_configs()

        msg = db_response.get('message', 'Db returned no message')
        if not db_response.get('ok'):
            user_error(msg)
            return
        user_success(db_response.get('data', ''))
    except Exception as exc:
        user_error(str(exc))
        return
