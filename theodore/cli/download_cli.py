import rich_click as click
import asyncio
from theodore.models.downloads import file_downloader
from theodore.managers.download_manager import Downloads_manager, get_marker
from theodore.core.utils import user_success, Downloads
from theodore.cli.async_click import AsyncCommand
from pathlib import Path


downloader = Downloads(file_downloader)

# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------

@click.group()
@click.option('--dir_path', '-p', default="~/Downloads", type=str, help='directory to save file in')
@click.pass_context
def downloads(ctx: click.Context, dir_path: str) -> None:
    """Download, Manage and track downloads"""
    # Group logic runs before subcommands.
    ctx.obj['dir_path'] = Path(dir_path).expanduser()

@downloads.command(cls=AsyncCommand)
@click.option('--url', '-u', type=str, help='comma separated urls')
@click.option('--resume', is_flag=True, help='Resume specific file download')
@click.pass_context
async def file(ctx: click.Context, url: str, resume: bool) -> None:
    """Download, Manage and track downloads"""
    dir_str = ctx.obj['dir_path']

    if resume:
        urls = await downloader.get_undownloaded_urls()
    else:
        urls = [u.strip() for u in url.split(',')]
    if not urls:
        user_success('No unfinished downloads')
        return
    tasks = list()
    db_tasks = list()

    for u in urls:
        url_path_name = downloader.parse_url(u)
        full_path = dir_str / url_path_name

        tasks.append(Downloads_manager.download_movie(u, full_path, url_path_name))

        if not resume:
            db_tasks.append(dict(filename=url_path_name, url=u, filepath=str(full_path)))

    tasks.append(downloader.bulk_insert(file_downloader, values=db_tasks))

    await asyncio.gather(*tasks, return_exceptions=True)
    return

@downloads.command(cls=AsyncCommand)
@click.argument('filename', type=str)
@click.pass_context
async def cancel(ctx: click.Context, filename: str):
    """Cancel file download"""

    response = await downloader.get_full_name(filename)
    if not response:
        click.echo('')
        return
    
    if not get_marker(filename).exists():
        click.echo(f'No file with name \'{filename}\' downloading')
        return
    
    Downloads_manager.cancel_download(filename)
    click.echo(f'{filename} download Cancelled')

@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def pause(ctx, filename):
    """Pause File download"""
    response = await downloader.get_full_name(filename)
    if not response:
        click.echo(f'No file matching "{filename}" found')
        return
    if not get_marker(filename).exists():
        click.echo(f'No file with name \'{filename}\' downloading')
        return
    
    Downloads_manager.pause_download(filename)
    click.echo(f'{filename} Paused')
    return


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def resume(ctx, filename):
    """Resume Paused downloads"""
    
    response = await downloader.get_full_name(filename)
    if not response:
        click.echo(f'No file matching "{filename}" found')
        return
    if not get_marker(filename).exists():
        click.echo(f'No file with name \'{filename}\' downloading')
        return
    Downloads_manager.resume_download(filename)
    click.echo(f'{filename} Paused')
    return