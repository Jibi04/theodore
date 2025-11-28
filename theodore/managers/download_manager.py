import asyncio, aiofiles, httpx, tempfile, re
from sqlalchemy import update
from theodore.core.logger_setup import base_logger
from theodore.managers.configs_manager import Configs_manager
from theodore.core.utils import send_message, user_success, user_error, user_info, local_tz
from theodore.models.downloads import file_downloader
from theodore.models.base import get_async_session
from datetime import datetime
from fake_user_agent import user_agent
from pathlib import Path
from tqdm.asyncio import tqdm

ua = user_agent()
manager = Configs_manager()

# set existence of file as markers for pause, resume or download
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def clean_file(filename) -> str:
    return re.sub(r'[^a-zA-Z0-9.-]', '_', filename)

def pause_marker_path(filename) -> Path:
    return TEMP_DIR / f"pause_{clean_file(filename)}.lock"

def cancel_marker_path(filename) -> Path:
    return TEMP_DIR / f"cancel_{clean_file(filename)}.lock"


class Downloads_manager:

    @classmethod
    def pause_download(cls, filename):
        base_logger.internal(f'Download logger initialized {filename}')
        pause_marker_path(filename).write_text("paused")
        return send_message(True, message="Pause marker created")

    @classmethod
    def cancel_download(cls, filename):
        cancel_marker_path(filename).write_text("cancelled")
        return send_message(True, message="marker created")
        

    @classmethod
    def resume_download(cls, filename):
        file = pause_marker_path(filename)
        if file.exists():
            file.unlink(missing_ok=True)
            return send_message(True, message="marker removed")
        
    async def update_client(self, filename, filepath):
        stmt = (update(file_downloader)
                .where(file_downloader.c.filename==filename)
                .values(
                is_downloaded=True,
                date_downloaded=datetime.now(local_tz)
                ))
        
        async with get_async_session() as session:
            await session.execute(stmt)
        user_success(f'{filename} download complete!')

    @classmethod
    async def download_movie(cls, url: str, filepath: Path|str, filename: str=None, chunksize: int=8192, retries: int=10) -> dict:
        
        filepath = Path(filepath).expanduser()
        base_logger.internal('Preparing file directory for download')
        
        # FIX 1: Pathlib's synchronous mkdir is fine here, as it's not I/O intensive.
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            filename = filepath.name

        # ----------- Remove stale markers before starting or resuming download --------------
        try:
            base_logger.internal(f"Cleaning markers for: {filename}")
            pause_marker_path(filename).unlink(missing_ok=True)
            cancel_marker_path(filename).unlink(missing_ok=True)
        except Exception as e:
            user_error(f"MARKER CLEAN ERROR: {e}")
            raise

        for attempt in range(1, retries + 1):
            downloaded_bytes = 0
            
            # -------- Resume feature: Check size before request ---------
            if filepath.exists():
                try:
                    # Pathlib stat is synchronous
                    downloaded_bytes = filepath.stat().st_size
                except OSError:
                    downloaded_bytes = 0

            headers = {"Range": f"bytes={downloaded_bytes}-"} if downloaded_bytes > 0 else None
            # Mode determines if we are appending ('ab') or starting fresh ('wb')
            mode = 'ab' if downloaded_bytes > 0 else 'wb'
            async with httpx.AsyncClient(timeout=30) as client:
                try:
                    # FIX 3: Use client.stream() method
                    async with client.stream('GET', url=url, headers=headers) as response:
                        user_success(f'Downloading {filename} Attempt {attempt}/{retries}: starting request')
                        
                        response.raise_for_status()
                        code = response.status_code
                        
                        # if browser doesn't support resume start over
                        if code == 200 and downloaded_bytes > 0:
                            user_info("Starting over: Server doesn't support resume or returned full content.")
                            try:
                                await aiofiles.os.remove(filepath)
                            except FileNotFoundError:
                                pass # Already gone
                            downloaded_bytes = 0 # Reset downloaded bytes for the new start
                            continue # Restart the retry loop

                        # --- TQDM SETUP START ---
                        # 1. Determine total size from headers
                        content_range = response.headers.get('Content-Range')
                        content_length = response.headers.get('Content-Length', '0')
                        
                        if code == 206 and content_range:
                            expected_total = int(content_range.split('/')[-1])
                            current_segment_start = downloaded_bytes
                        elif code == 200:
                            expected_total = int(content_length)
                            current_segment_start = 0 # Starting from scratch
                        else:
                            # Fallback if range/length are missing
                            expected_total = downloaded_bytes + int(content_length) 
                            current_segment_start = downloaded_bytes

                        if downloaded_bytes < expected_total and expected_total > 0:
                            total_size = expected_total
                            
                            # 2. Open the file ONCE with aiofiles BEFORE the chunk loop
                            async with aiofiles.open(filepath, mode=mode) as f:
                                # 3. Initialize tqdm bar
                                with tqdm(
                                    initial=downloaded_bytes, # Start from the previously downloaded bytes
                                    total=total_size,        # The total expected size
                                    desc=f"Downloading {filename}",
                                    unit='B',
                                    unit_scale=True,
                                    disable=(total_size == 0)
                                ) as t:
                                    
                                    # Use aiter_bytes() with chunksize from the function argument
                                    async for chunk in response.aiter_bytes(chunk_size=chunksize):
                                        
                                        pause_marker = pause_marker_path(filename)
                                        cancel_marker = cancel_marker_path(filename)

                                        # ------- pause / resume feature -------
                                        while pause_marker.exists():
                                            user_info(f"Download paused for {filename}")
                                            # Use asyncio.sleep to avoid blocking the loop while waiting
                                            await asyncio.sleep(1.0) 

                                        # ---------- Cancel feature ----------
                                        if cancel_marker.exists():
                                            user_error(f'Download cancelled for {filename}')
                                            await aiofiles.os.remove(filepath)
                                            return send_message(False, message=f'Download cancelled for {filename}')
                                        
                                        # FIX 4: Await the file write, using the file handle opened above
                                        if chunk:
                                            await f.write(chunk)
                                            # 4. Use t.update() to advance the progress bar
                                            t.update(len(chunk))
                                            
                            # After the file is closed (out of the aiofiles.open context)
                            final_size = filepath.stat().st_size
                            if final_size != total_size:
                                # Invalid file integrity Re-starting download
                                try:
                                    await aiofiles.os.remove(filepath)
                                except FileNotFoundError:
                                    pass
                                user_error(f"Download finished but file size mismatch: {final_size} != {total_size}, Restarting ...")
                                base_logger.internal("Corrupted file data restarting download")
                                continue # Go to the next retry attempt
                            else:
                                user_success(f"Download complete for {filename}.")
                                await cls().update_client(filename=filename) 
                                return

                except httpx.ConnectTimeout:
                    user_error(f"Connection timeout during download of {filename}. Attempting retry {attempt + 1}/{retries}...")
                    base_logger.internal("HTTPX timeout occurred.")
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
                    continue
                except httpx.HTTPStatusError as e:
                    user_error(f"HTTP error {e.response.status_code} for {filename}. Attempting retry {attempt + 1}/{retries}...")
                    base_logger.internal(f"HTTPX Status Error: {e.response.status_code}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                except Exception as e:
                    user_error(f"An unexpected error occurred during download of {filename}: {e}. Stopping.")
                    raise
            
        # If the loop finishes without success
        user_error(f"Failed to download {filename} after {retries} attempts.")
        return send_message(False, message=f'Failed to download {filename} after {retries} attempts.')
            


