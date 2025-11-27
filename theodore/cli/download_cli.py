import click
from concurrent.futures import ThreadPoolExecutor
import rich_click as click
import re, json

from theodore.managers.download_manager import Downloads_manager
from theodore.managers.configs_manager import Configs_manager
from theodore.core.logger_setup import base_logger
from theodore.core.utils import user_success, send_message
from click_option_group import optgroup, RequiredAnyOptionGroup
from urllib.parse import urlparse, unquote
from pathlib import Path

# -------------------------------
#        Helper methods 
# --------------------------------

def get_full_name(filename):
    base_logger.internal(f'get full name initalized file name: {filename}')

    def search(pattern, text):
        base_logger.internal(f'search pattern initalized pattern: {pattern}, Text {text}')

        base_logger.internal('compiling search')
        keyword = re.compile(pattern, re.I)

        match = keyword.search(text)
        if match is None:
            base_logger.internal(f'match from compiler returned {match}')
            return None
        
        base_logger.internal(f'returning match from compiler {match.string}')
        return match.string
    
    manager = Configs_manager()
    base_logger.internal(f'configs manager loaded {manager}')
    movies = manager.load_file(movie=True)
    movies = movies.get('downloads', {}).get('movies', {})

    base_logger.internal(f'movies manager {movies}')

    file = None
    for movie in movies.keys():
        full_name = search(filename, movie)
        if full_name:
            if movies[full_name].get('is_downloaded'):
                base_logger.internal(f'{movie} already downloaded')
                return send_message(False, message=f'{movie} already downloaded')
            file = full_name
            break
    if file is None:
        base_logger.internal(f'File is None. {file}')
        return send_message(False, message='File not found.')
    
    base_logger.internal(f'full name returned {file}')
    return send_message(True, data=file)


def multi_download(urls, dir_path = None):
    if not urls:
        user_success('No unfinished downloads')
        return
    
    configs_manager = Configs_manager()
    download_manager = Downloads_manager()
    movie_configs = configs_manager.load_file(movie=True)

    if not dir_path:
        load_configs = configs_manager.load_file(config=True)
        dir_path = load_configs.get('downloads', {}).get('default_location', "~/Videos")

    dir_str = Path(dir_path).expanduser().absolute()
    executor = ThreadPoolExecutor(max_workers=5)

    for u in urls:
        url_path_name = Path(unquote(urlparse(u).path)).name
        full_path = dir_str / url_path_name

        executor.submit(download_manager.download_movie, u, full_path, url_path_name)
        movie_configs["downloads"]["movies"].setdefault(url_path_name, {"url": u, "is_downloaded": False})

    configs_manager.save_file(movie_configs, movie=True)
    # executor.shutdown(wait=True)
    return
# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------

@click.group()
@click.option('--url', type=str, help='comma separated urls')
@click.option('--resume', is_flag=True, help='Resume specific file download')
@click.option('--dir_path', '-p', default="~/Downloads", type=str, help='directory to save file in')
@click.pass_context
def downloads(ctx: click.Context, url: str, resume: bool, dir_path: str) -> None:
    """Download, Manage and track downloads"""
    base_logger.internal('preparing downloads manager')

    manager = ctx.obj['config_manager']
    configs = manager.load_file(config=True)


    movies = manager.load_file(movie=True)
    movies.setdefault("downloads", {})
    movies["downloads"].setdefault("movies", {})

    base_logger.internal('preparing downloads path')

    if not dir_path:
        dir_path = configs.get('downloads', {}).get('default_location', "~/Videos")

    dir_str = Path(dir_path).expanduser().absolute()

    base_logger.internal('parsing url for fetch')
    manager.save_file(movies, movie=True)

    if resume:
        urls = []

        movies = movies.get('downloads', {}).get('movies', {})

        if not movies:
            user_success('No downloads to resume')
            return
        
        for _, movie_data in movies.items():

            if movie_data.get('is_downloaded'):
                continue
            
            url = movie_data.get('url')

            urls.append(url)

    else:
        urls = [u.strip() for u in url.split(',')]

    multi_download(urls=urls, dir_path=dir_str)
    
    return

@downloads.command()
@click.argument('filename')
@click.pass_context
def cancel(ctx, filename):
    """Cancel file download"""
    manager = ctx.obj['download_manager']
    response = get_full_name(filename)
    if not response.get('ok'):
        msg = response.get('message')
        click.echo(msg)
        return
    filename = response.get('data')
    Downloads_manager.cancel_download(filename)
    click.echo(f'{filename} Cancelled')

@downloads.command()
@click.argument('filename')
@click.pass_context
def pause(ctx, filename):
    """Pause File download"""
    base_logger.internal(f'Preparing to pause file {filename} was passed')

    base_logger.internal(f'getting refactored full name')
    response = get_full_name(filename)

    base_logger.internal(f'recieved response {response}')
    if not response.get('ok'):
        msg = response.get('message')
        base_logger.internal(f'returning nothing {msg}')
        click.echo(msg)
        return
    
    filename = response.get('data')
    base_logger.internal(f'file found filename {filename}')

    base_logger.internal(f'Calling Downloads manager with filename')
    res = Downloads_manager.pause_download(filename)

    base_logger.internal(f'downloads manager response {res}')
    click.echo(f'{filename} Paused')


@downloads.command()
@click.argument('filename')
@click.pass_context
def resume(ctx, filename):
    """Resume Paused downloads"""
    response = get_full_name(filename)
    manager = ctx.obj['download_manager']
    if not response.get('ok'):
        msg = response.get('message')
        click.echo(msg)
        return
    filename = response.get('data')
    Downloads_manager.resume_download(filename)
    click.echo(f'resuming {filename} download...')
