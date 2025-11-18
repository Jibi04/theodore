import click
import threading
import rich_click as click

from theodore.managers.download_manager import Downloads_manager
from theodore.managers.configs_manager import Configs_manager
from theodore.core.logger_setup import download_logger, error_logger, base_logger
from click_option_group import optgroup, RequiredAnyOptionGroup
from urllib.parse import urlparse, unquote
from pathlib import Path


# ========== Main Downloads CLI =========

def multi_download(urls, dir_path = None):

    if not urls:
        base_logger.info('No unfinished downloads')
        return

    configs_manager = Configs_manager()
    download_manager = Downloads_manager()

    movie_configs = configs_manager.load_file(movie=True)

    if not dir_path:
        load_configs = configs_manager.load_file(config=True)
        dir_path = load_configs.get('downloads', {}).get('default_location', "~/Videos")

    dir_str = Path(dir_path).expanduser().absolute()

    threads = []

    for u in urls:
        url_path_name = Path(unquote(urlparse(u).path)).name
        full_path = dir_str/url_path_name
        t = threading.Thread(target=download_manager.download_movie, args=(u, full_path, url_path_name))
        t.start()
        threads.append(t)

        movie_configs["downloads"]["movies"].setdefault(url_path_name, {"url": u, "is_downloaded": False})

    configs_manager.save_file(movie_configs, movie=True)
        
    download_logger.internal('sending request for fetch')
    for t in threads:
        t.join()

    return


@click.group()
@click.pass_context
def downloads(ctx):
    """Manage and track File downloads"""

@downloads.command()
@optgroup.group(name='required options', cls=RequiredAnyOptionGroup)
@optgroup.option('--url', type=str, help='comma separated urls')
@optgroup.option('--resume', is_flag=True, help='resume unfinished downloads')
@click.option('--dir_path', '-p', type=str, help='directory to save file in')
@click.pass_context
def movie(ctx, url, dir_path, resume):
    """Download movies mkv, mp4, and zip"""
    download_logger.internal('preparing downloads manager')

    manager = ctx.obj['configs_manager']
    configs = manager.load_file(config=True)

    movies = manager.load_file(movie=True)
    movies.setdefault("downloads", {})
    movies["downloads"].setdefault("movies", {})

    download_logger.internal('preparing downloads path')

    if not dir_path:
        dir_path = configs.get('downloads', {}).get('default_location', "~/Videos")

    dir_str = Path(dir_path).expanduser().absolute()

    download_logger.internal('parsing url for fetch')
    manager.save_file(movies, movie=True)

    if resume:
        urls = []
        movies = movies.get('downloads', {}).get('movies', {})

        if not movies:
            download_logger.info('No downloads to resume')
            return
        
        for _, movie_data in movies.items():

            if movie_data.get('is_downloaded'):
                continue
            
            print(movie_data.get('is_downloaded'))
            url = movie_data.get('url')

            urls.append(url)

    else:
        urls = [u.strip() for u in url.split(',')]

    multi_download(urls=urls, dir_path=dir_str)
    
    return
