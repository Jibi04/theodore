import click
from rich.table import Table
import rich_click as click
import re, json, asyncio
import pandas as pd

# The assumption is your main script will now run the click group within an asyncio loop.
# Libraries used must be async-compatible or run in a thread executor if blocking.

from theodore.managers.download_manager import Downloads_manager
from theodore.managers.configs_manager import Configs_manager
from theodore.core.logger_setup import base_logger
from theodore.core.utils import user_success, send_message, user_error, normalize_ids
from theodore.core.theme import console
from theodore.core.worker_setup import put_new_task
from click_option_group import optgroup, RequiredAnyOptionGroup
from urllib.parse import urlparse, unquote
from pathlib import Path


# -------------------------------
#        Helper methods 
# --------------------------------

# 🚨 CHANGE: This function must now be 'async def' because it performs async DB lookups
async def get_full_name(filename):
    base_logger.internal(f'get full name initalized file name: {filename}')
    
    undownloaded_filenames = await Downloads_manager.get_undownloaded_urls(filename=True)
    
    movie_col = pd.Series(undownloaded_filenames)
    pattern = re.compile(filename)
    match = movie_col[movie_col.str.contains(pattern, flags=re.I, case=False, regex=True)]
    
    if match.empty:
        base_logger.internal(f'File is None. {match}')
        return send_message(False, message='File not found.')
    
    match_dict = {}
    if len(match) > 1:
        table = Table(title="Ambiguous Search Results")
        table.add_column('index') 
        table.add_column('filename')
        
        for i, m in enumerate(match):
            table.add_row(str(i), m)
            match_dict[i] = m

        console.print(table)
        res = console.input(f'Your file match returned {len(match)} results. select index from ids above to perform this operation.: ')
        res = normalize_ids(task_ids=res)

        if not res: return send_message(False, message='Invalid id input')

        fullname = match_dict[res[0]]
        base_logger.internal(f'full name returned {fullname}')
        return send_message(True, data=fullname)
    
    # If len(match) == 1
    fullname = match.iloc[0]
    base_logger.internal(f'full name returned {fullname}')
    return send_message(True, data=fullname)


async def multi_download(urls, dir_path = None):
    if not urls:
        user_success('No unfinished downloads')
        return
    download_manager = Downloads_manager() 

    query_args = []
    tasks = [] # List to hold coroutines (tasks)

    for u in urls:
        url_path_name = Path(unquote(urlparse(u).path)).name
        full_path = dir_path / url_path_name

        query_args.append((url_path_name, u, str(full_path)))
        
        # The task is created, but not immediately awaited.
        task = put_new_task(3, download_manager.download_movie, (u, full_path, url_path_name))
        tasks.append(task)
        
    # Wait for all tasks to be added to the queue concurrently
    # The actual execution depends on your worker setup (which should also be async)
    await asyncio.gather(*tasks) 
    
    # 🚨 CHANGE: Await the bulk insert operation
    await download_manager.insert_into_db(query_args)
    return

# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------

# 🚨 CHANGE: Use the standard click.group() but remember to run the application 
# entry point with an async runner (like click_async)
@click.group()
@click.pass_context
def downloads(ctx):
    """Manage and track File downloads"""

# 🚨 CHANGE: Command is now 'async def'
@downloads.command()
@optgroup.group(name='required options', cls=RequiredAnyOptionGroup)
@optgroup.option('--url', type=str, help='comma separated urls')
@optgroup.option('--resume', is_flag=True, help='Resume specific file download')
@click.option('--dir_path', '-p', type=str, help='directory to save file in')
@click.pass_context
async def movie(ctx, url, dir_path, resume):
    """Download movies mkv, mp4, and zip"""
    base_logger.internal('preparing downloads manager')

    downloads_manager = ctx.obj['download_manager']
    configs_manager = ctx.obj['config_manager']
    base_logger.internal('preparing downloads path')

    if not dir_path:
        dir_path = await configs_manager.load_db_configs(category='downloads')
        dir_path = dir_path.get('default_path', '~/Videos')

    dir_str = Path(dir_path).expanduser().absolute()

    if resume:
        urls = await downloads_manager.get_undownloaded_urls(urls=True)
        if not urls:
            user_error('No unfinished downloads')
            return 
    else:
        if not url:
            user_error("URL is required when not resuming.")
            return

        urls = [u.strip() for u in url.split(',')]

    await multi_download(urls=urls, dir_path=dir_str)
    return

@downloads.command()
@click.argument('filename')
@click.pass_context
async def cancel(ctx, filename):
    """Cancel file download"""
    manager = ctx.obj['download_manager']
    
    response = await get_full_name(filename) 
    
    if not response.get('ok'):
        msg = response.get('message')
        click.echo(msg)
        return
    filename = response.get('data')
    
    await Downloads_manager.cancel_download(filename)
    click.echo(f'{filename} Cancelled')

@downloads.command()
@click.argument('filename')
@click.pass_context
async def pause(ctx, filename):
    """Pause File download"""
    base_logger.internal(f'Preparing to pause file {filename} was passed')

    base_logger.internal(f'getting refactored full name')
    response = await get_full_name(filename) 

    base_logger.internal(f'recieved response {response}')
    if not response.get('ok'):
        msg = response.get('message')
        base_logger.internal(f'returning nothing {msg}')
        click.echo(msg)
        return
    
    filename = response.get('data')
    base_logger.internal(f'file found filename {filename}')

    base_logger.internal(f'Calling Downloads manager with filename')
    res = await Downloads_manager.pause_download(filename) 

    base_logger.internal(f'downloads manager response {res}')
    click.echo(f'{filename} Paused')

@downloads.command()
@click.argument('filename')
@click.pass_context
async def resume(ctx, filename):
    """Resume Paused downloads"""
    response = await get_full_name(filename) 
    
    if not response.get('ok'):
        msg = response.get('message')
        click.echo(msg)
        return
    filename = response.get('data')
    
    await Downloads_manager.resume_download(filename) 
    click.echo(f'resuming {filename} download...')