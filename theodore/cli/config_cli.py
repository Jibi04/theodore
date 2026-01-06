from pathlib import Path
import click
import rich_click as click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAnyOptionGroup
from theodore.managers.configs_manager import Configs_manager
from theodore.cli.async_click import AsyncCommand
from theodore.models.configs import Configs_table
from theodore.core.utils import DB_tasks, get_configs_table
from theodore.core.theme import cli_defaults, console
from theodore.core.logger_setup import base_logger
from theodore.core.utils import user_error, user_success

cli_defaults()

configs_manager = Configs_manager()

@click.group()
@click.pass_context
def config(ctx):
    """Adjust configuration settings"""

@config.command(cls=AsyncCommand)
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p")
@click.argument("category", type=str)
@click.pass_context
async def set(ctx, default_location, api_key, default_path, category):
    base_logger.internal('Getting option from ctx manager')
    args_map = ctx.params

    if default_location: default_location = default_location.strip()

    if default_path: 
        path = Path(default_path.strip()).absolute()
        if path is None: return user_error('Unable to set default path invalid path')
        path.parent.mkdir(exist_ok=True, parents=True) 
        path_str = str(path)
        args_map['default_path'] = path_str

    try:
        response = await configs_manager.upsert_category(args_map)
        if not response.get('ok', None):
            user_error(response.get('message', 'An error occured whilst setting new configs please try again later'))
            return
        user_success(response.get('message'))
        return
    except Exception as e:
        raise

@config.command(cls=AsyncCommand)
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p")
@click.argument("category", type=str)
@click.pass_context
async def update(ctx, default_location, api_key, default_path, category):
    base_logger.internal('Getting option from ctx manager')
    args_map = ctx.params
    if default_location: default_location = default_location.strip()

    if default_path: 
        path = Path(default_path.strip()).absolute()
        if path is None: return user_error(f'Unable to update default path invalid path {default_path}')
        path.parent.mkdir(exist_ok=True, parents=True) 
        path_str = str(path)
        args_map['default_path'] = path_str

    cols_to_update = {
        key:val for key, val in args_map.items() if val
    }

    try:
        response = await configs_manager.upsert_category(cols_to_update)
        if not response.get('ok', None):
            user_error(response.get('message', 'An error occured whilst updating configs settings please try again later'))
            return
        user_success(response.get('message'))
        return
    except Exception as e:
        raise

@config.command(cls=AsyncCommand)
@optgroup.group(name='required action', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='show all configs')
@optgroup.option('--weather', '-w', is_flag=True, help='show all weather configs')
@optgroup.option('--downloads', '-d', is_flag=True, help='show all downloads configs')
@optgroup.option('--todos', '-t', is_flag=True, help='show all configs')
@click.pass_context
async def show_configs(ctx, all, weather, downloads, todos):
    """Show category configurations"""
    args_map = ctx.params
    try:
        response = await configs_manager.show_configs(args_map=args_map)
        if not response.get('ok', None):
            user_error(response.get('message', 'An error occurred try again shortly'))
            return
        table = response.get('data', None)
        if not table:
            user_error('Unable to display configs at this time')
            return
        console.print(table)
    except Exception:
        raise
    return
