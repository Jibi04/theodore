from pathlib import Path
import rich_click as click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAnyOptionGroup
from theodore.core.theme import cli_defaults, console
from theodore.core.logger_setup import base_logger
from theodore.core.informers import user_error, user_success
from theodore.ai.dispatch import DISPATCH, CONFIG_MANAGER

cli_defaults()

@click.group()
@click.pass_context
def config(ctx):
    """Adjust configuration settings"""

@config.command()
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p")
@click.argument("category", type=str)
@click.pass_context
def set(ctx, default_location, api_key, default_path, category):
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
        response = DISPATCH.dispatch_cli(CONFIG_MANAGER.upsert_category, data=args_map)
        if not response.get('ok', None):
            user_error(response.get('message', 'An error occured whilst setting new configs please try again later'))
            return
        user_success(response.get('message'))
        return
    except Exception as e:
        raise

@config.command()
@optgroup.group('required', cls=RequiredAnyOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p")
@click.argument("category", type=str)
@click.pass_context
def update(ctx, default_location, api_key, default_path, category):
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
        response = DISPATCH.dispatch_cli(CONFIG_MANAGER.upsert_category, data=cols_to_update)
        if not response.get('ok', None):
            user_error(response.get('message', 'An error occured whilst updating configs settings please try again later'))
            return
        user_success(response.get('message'))
        return
    except Exception as e:
        raise

@config.command()
@optgroup.group(name='required action', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='show all configs')
@optgroup.option('--weather', '-w', is_flag=True, help='show all weather configs')
@optgroup.option('--downloads', '-d', is_flag=True, help='show all downloads configs')
@optgroup.option('--todos', '-t', is_flag=True, help='show all configs')
@click.pass_context
def show_configs(ctx, all, weather, downloads, todos):
    """Show category configurations"""
    args_map = ctx.params
    try:
        response = DISPATCH.dispatch_cli(CONFIG_MANAGER.show_configs, args_map=args_map)
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
