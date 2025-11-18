from pathlib import Path
import click
import rich_click as click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup
import json
from theodore.core.theme import cli_defaults
from theodore.core.logger_setup import base_logger
from theodore.core.utils import user_error, user_success, error_logger

cli_defaults()

@click.group(context_settings=dict())
@click.pass_context
def config(ctx):
    """Adjust configuration settings"""

@config.command()
@optgroup.group('required', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option("--default-location", "-l", type=str, help='Set default weather location')
@optgroup.option("--api-key", "-api-key", type=str)
@optgroup.option("--default-path", "-p")
@optgroup.option("--target-dirs", "-td", type=str, help="Set default target dirs")
@optgroup.option("--file-patterns", "-pattern", type=str)
@click.argument("category", type=click.Choice(['weather', 'downloads', 'tasks']))
@click.pass_context
def set(ctx, default_location, api_key, default_path, target_dirs, file_patterns, **kwargs):
    base_logger.internal('Getting option from ctx manager')
    args_map = ctx.params

    base_logger.internal('cleaning parameters')

    if default_location: default_location = default_location.strip()


    if default_path: 
        base_logger.internal('cleaning Path parameter')

        path = Path(default_path.strip()).absolute()

        if path is None: return user_error('Unable to set default path invalid path')
        path.parent.mkdir(exist_ok=True, parents=True) 

        base_logger.internal('converting default path to str')
        path_str = str(path)
        base_logger.internal('updating args map default location')
        args_map['default_location'] = path_str


    if target_dirs: 
        base_logger.internal('cleaning target dirs parameter')

        new_dict = target_dirs.split(',')
        base_logger.internal('cleaning new target dirs')

        base_logger.debug(f'cleaned target dirs: {new_dict}')
        cleaned_dict = [tuple(d.split('=')) for d in new_dict if '=' in d]

        dir_dict = {k.strip():str(Path(v).expanduser()) for (k, v) in cleaned_dict}
        base_logger.debug(f'Cleaned target directory: {dir_dict}')

        base_logger.internal('updating args map default location')
        args_map['target_dirs'] = dir_dict
    

    if file_patterns:
        base_logger.internal('cleaning new file patterns')
        new_patterns = file_patterns.split(',')
        cleaned_patterns_list = ["*." + ptrn.replace('.', '').replace('*', '').strip() for ptrn in new_patterns]

        args_map['file_patterns'] = cleaned_patterns_list

    configs = ctx.obj['configs']

    try:
        base_logger.internal('setting configs')
        base_logger.internal('Awaiting response from database')
        response = configs.set(**args_map)
        msg = response.get('message')

        if not response.get('ok'):
            base_logger.internal('An error occurred with the db Aborting ...')
            return
        
        user_success(msg)
    except Exception as e:
        base_logger.internal(f'{type(e).__name__} error Aborting ...')
        error_logger.exception(e)

    return

@config.command()
@optgroup.group(name='required action', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='show all configs')
@optgroup.option('--weather', '-w', is_flag=True, help='show all weather configs')
@optgroup.option('--downloads', '-d', is_flag=True, help='show all downloads configs')
@optgroup.option('--todos', '-t', is_flag=True, help='show all configs')
@click.pass_context
def show_configs(ctx, all, weather, downloads, todos):
    """Show category configurations"""

    base_logger.internal('Loading configurations file')
    config_manager = ctx.obj['config_manager']
    configs = config_manager.load_file(config=True)
    if not configs:
        user_error('No configs set')
        return
    
    base_logger.debug(f'configs file loaded {configs}')

    if weather:
        base_logger.internal('getting weather data')
        json_data = configs.get('weather')
        base_logger.debug(f"Loaded weather configuration data: {json_data}")

    if downloads:
        base_logger.internal('getting downloads data')
        json_data = configs.get('downloads')
        base_logger.debug(f"Loaded downloads configuration data: {json_data}")

    if todos:
        base_logger.internal('getting to-dos data')
        json_data = configs.get('todos')
        base_logger.debug(f"Loaded to-dos configuration data: {json_data}")

    if all:
        base_logger.internal('loading all configs data')
        json_data = configs
        base_logger.debug(f"Loaded all configs data: {json_data}")

    if not json_data:
        user_error('No configurations have been set yet.')
        return

    base_logger.internal('writing and indenting configs')
    data = json.dumps(json_data, indent=4)
    base_logger.internal("Indented configs data: {data}")

    user_success(data)
    return
