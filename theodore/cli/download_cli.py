import rich_click as click
import asyncio
from theodore.models.downloads import file_downloader
from theodore.managers.download_manager import Downloads_manager
from theodore.core.utils import user_success, Downloads, user_error, user_info, DB_tasks
from theodore.cli.async_click import AsyncCommand
from pathlib import Path

downloader = Downloads(file_downloader)
manager = Downloads_manager()

# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------

async def send_command(filename, filepath, cmd):
    socket_path = manager.socket_path

    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)

        message = f'{cmd.upper()}:{filename}:{filepath}'
        writer.write(message.encode())
        await writer.drain()

        response = await reader.read(1024)
        user_info(f'server response: {response.decode()}')

        writer.close()
        await writer.wait_closed()
    except FileNotFoundError:
        user_error('Downloader isn\'t running (socket not found)')
    except Exception as e:
        user_error('Error communicating with downloader.')
    return

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

    resumable_downloads = await downloader.get_undownloaded_urls()
    urls_to_download.extend(list(map(downloader.parse_url, resumable_downloads)))
    if url:
        urls = [u.strip() for u in url.split(',') if u.strip()]
        if not urls:
            user_error("No valid URLs provided.")
            return
        urls_to_download.extend(list(map(downloader.parse_url, urls)))
    if not url and not resume:
        user_info('No URLs provided and --resume not set.')
        return
    
    if not urls_to_download and resume:
        user_info('No unfinished downloads to resume.')
        return
    server = await manager.start_server()
    try:
        
        # bulk insert
        entries_to_insert = [url_map for url_map in urls_to_download if url_map.get('url') not in resumable_downloads]
        if entries_to_insert:
            await downloader.bulk_insert(file_downloader, entries_to_insert)
        # -------------------------------------------------------------
        # 3. Queue Tasks and Database Insertion
        # -------------------------------------------------------------
        tasks = []
        # Create the download tasks (must happen AFTER preparing db_tasks list)
        for url_map in urls_to_download:
            url = url_map.get('url')
            url_path_name = url_map.get('filename')
            full_path = url_map.get('filepath', dir_path / url_path_name)
            # FIX 3: Ensure Download_manager.download_movie is awaited in the final gather
            tasks.append(manager.download_movie(url, full_path, url_path_name))
        if tasks:
            user_success(f'Starting {len(tasks)} download(s)...')
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        server.close()
        await server.wait_closed()
        socket_file = Path(manager.socket_path)
        if socket_file.exists():
            socket_file.unlink()
    return

@downloads.command(cls=AsyncCommand)
@click.argument('filename', type=str)
@click.pass_context
async def cancel(ctx: click.Context, filename: str):
    """Cancel file download"""

    _filename = await downloader.get_full_name(filename)
    if not file:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': file}, first=True)
        if file_obj:
            filepath = file_obj.filepath
        else:
            click.echo(f'Error: No record found for file matching "{filename}".')
            return
    await send_command(_filename, filepath, cmd='CANCEL')
    click.echo(f'{filename} download Cancelled. Cleanup will occur automatically.')


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def pause(ctx, filename):
    """Pause File download"""
    _filename = await downloader.get_full_name(filename)
    if not file:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
        if file_obj:
            filepath = file_obj.filepath
        else:
            click.echo(f'Error: No record found for file matching "{filename}".')
            return
    await send_command(_filename, filepath, cmd='PAUSE')
    click.echo(f'{filename} download Paused.')

@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def resume(ctx, filename):
    """Resume Paused downloads"""
    _filename = await downloader.get_full_name(filename)
    if not file:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
        if file_obj:
            filepath = file_obj.filepath
        else:
            click.echo(f'Error: No record found for file matching \'{filename}\'.')
            return
    await send_command(_filename, filepath, cmd='RESUME')
    click.echo(f'{filename} download Resumed.')


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def status(ctx, filename):
    """Get file download status of you file"""
    _filename = await downloader.get_full_name(filename)
    if _filename:
        with DB_tasks(file_downloader) as db_manager:
            f = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
            if f:
                status_text = "Completed" if f.is_downloaded else "In Progress/Paused"
                name = f.filename if len(f.filename) <= 30 else f.filename[:30] + '...'

                user_info(f"[File: {name}  | Status: {status_text} | Path: {f.filepath} | Downloaded size: {f.download_percentage}% done]")
    else:
        user_info(f'Could not find data with filename \'{filename}\' name not in downloads or too vague')
