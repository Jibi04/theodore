import rich_click as click
import asyncio
from theodore.models.downloads import file_downloader
from theodore.managers.download_manager import Downloads_manager, get_marker
from theodore.core.utils import user_success, Downloads, user_error, user_info
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
    dir_path: Path = ctx.obj['dir_path']
    
    urls_to_download = []
    db_tasks = [] 

    if resume:
        urls_to_download = await downloader.get_undownloaded_urls()
        
    elif url:
        urls = [u.strip() for u in url.split(',') if u.strip()]
        if not urls:
             user_error("No valid URLs provided.")
             return

        for u in urls:
            url_path_name = downloader.parse_url(u)
            full_path = dir_path / url_path_name
            
            urls_to_download.append(u)
            
            # Prepare data for bulk insert *before* starting the download task
            db_tasks.append(dict(filename=url_path_name, url=u, filepath=str(full_path)))
    else:
        user_info('No URLs provided and --resume not set.')
        return
    if not urls_to_download and resume:
        user_info('No unfinished downloads to resume.')
        return

    # -------------------------------------------------------------
    # 3. Queue Tasks and Database Insertion
    # -------------------------------------------------------------
    
    tasks = []

    # FIX 2: Only insert new records if it's NOT a resume operation
    if db_tasks:
        tasks.append(downloader.bulk_insert(file_downloader, values=db_tasks))

    # Create the download tasks (must happen AFTER preparing db_tasks list)
    for u in urls_to_download:
        url_path_name = downloader.parse_url(u)
        full_path = dir_path / url_path_name
        # FIX 3: Ensure Download_manager.download_movie is awaited in the final gather
        tasks.append(Downloads_manager.download_movie(u, full_path, url_path_name))

    if tasks:
        user_success(f'Starting {len(tasks)} download and database tasks...')
        await asyncio.gather(*tasks, return_exceptions=True)
    return

@downloads.command(cls=AsyncCommand)
@click.argument('filename', type=str)
@click.pass_context
async def cancel(ctx: click.Context, filename: str):
    """Cancel file download"""

    response = await downloader.get_full_name(filename)
    if not response:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    
    # Check if the downloading marker exists *before* attempting to cancel
    if not get_marker(filename).exists():
        click.echo(f'Warning: No download in progress marker found for \'{filename}\'.')
    
    Downloads_manager.cancel_download(filename)
    click.echo(f'{filename} download Cancelled. Cleanup will occur automatically.')


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def pause(ctx, filename):
    """Pause File download"""
    response = await downloader.get_full_name(filename)
    if not response:
        click.echo(f'Error: No file record found for "{filename}".')
        return
    
    if not get_marker(filename).exists():
        click.echo(f'Warning: No download in progress marker found for \'{filename}\'.')
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
        click.echo(f'Error: No file record found for "{filename}".')
        return
    
    if not get_marker(filename).exists():
        click.echo(f'Warning: No file with name \'{filename}\' downloading')
        return
        
    Downloads_manager.resume_download(filename)
    click.echo(f'{filename} Resumed')
    return