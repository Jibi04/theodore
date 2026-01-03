import asyncio, aiofiles, tempfile, re
import httpx
from theodore.core.logger_setup import base_logger
from theodore.managers.configs_manager import Configs_manager
from theodore.core.utils import send_message, user_success, user_error, user_info, local_tz, DB_tasks
from theodore.models.downloads import file_downloader
from datetime import datetime
from fake_user_agent import user_agent
from pathlib import Path
from tqdm.asyncio import tqdm

# --- Global Setup ---
ua = user_agent()
manager = Configs_manager()

# Set existence of file as markers for pause, resume or download
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def clean_file(filename) -> str:
    """Sanitizes filename for marker creation."""
    return re.sub(r'[^a-zA-Z0-9.-]', '_', filename)

def pause_marker_path(filename) -> Path:
    return TEMP_DIR / f"pause_{clean_file(filename)}.lock"

def cancel_marker_path(filename) -> Path:
    return TEMP_DIR / f"cancel_{clean_file(filename)}.lock"

def downloading_marker_path(filename) -> Path:
    return TEMP_DIR / f"downloading_{clean_file(filename)}.lock"

def get_marker(filename: str) -> Path:
    """Returns the path to the main downloading marker."""
    return downloading_marker_path(filename)



class Downloads_manager:

    @classmethod
    async def _cleanup_markers(cls, filename):
        """Removes all temporary markers for a given file."""
        for marker_path in [pause_marker_path(filename), cancel_marker_path(filename), downloading_marker_path(filename)]:
            if marker_path.exists():
                try:
                    await aiofiles.os.remove(marker_path)
                except Exception as e:
                    base_logger.internal(f"Failed to remove marker {marker_path.name}: {e}")
    @classmethod
    async def mark_current():
        pass
        

    @classmethod
    async def pause_download(cls, filename):
        """Creates a pause marker file asynchronously (using to_thread)."""
        base_logger.internal(f'Download logger initialized {filename}')
        # Synchronous Path operations moved to a separate thread
        await asyncio.to_thread(pause_marker_path(filename).write_text, "paused")
        return send_message(True, message="Pause marker created")

    @classmethod
    async def cancel_download(cls, filename):
        """Creates a cancel marker file asynchronously (using to_thread)."""
        await asyncio.to_thread(cancel_marker_path(filename).write_text, "cancelled")
        return send_message(True, message="Cancel marker created")
        
    @classmethod
    async def resume_download(cls, filename):
        """Removes the pause marker file."""
        file = pause_marker_path(filename)
        if file.exists():
            await aiofiles.os.remove(file)
            return send_message(True, message="Pause marker removed, download should resume")
        
    @classmethod
    async def start_download(cls, filename):
        """Creates the downloading marker."""
        await asyncio.to_thread(downloading_marker_path(filename).write_text, f"{filename} downloading")

    @classmethod
    async def stop_download(cls, filename):
        """Removes the downloading marker."""
        file = downloading_marker_path(filename)
        if file.exists():
            await aiofiles.os.remove(file)

    @classmethod
    async def update_client(cls, filename, filepath):
        """Updates the database entry on successful download."""
        with DB_tasks(file_downloader) as manager:
            conditions = dict(filename=filename)
            values = [
                {"is_downloaded": True, "date_downloaded": datetime.now(local_tz)}
                ]
            await manager.update_features(values=values, and_conditions=conditions)
        user_success(f'{filename} download complete and database updated!')

    @classmethod
    async def download_movie(cls, url: str, filepath: Path | str, filename: str=None, chunksize: int=8192, retries: int=10) -> dict:
        
        filepath = Path(filepath).expanduser()
        base_logger.internal('Preparing file directory for download')
        
        # Synchronous mkdir is fine here
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            filename = filepath.name

        # ----------- Remove stale markers before starting or resuming download --------------
        try:
            base_logger.internal(f"Cleaning markers for: {filename}")
            # Use async marker cleanup helper
            await cls._cleanup_markers(filename)
        except Exception as e:
            user_error(f"MARKER CLEAN ERROR: {e}")
            raise

        for attempt in range(1, retries + 1):
            downloaded_bytes = 0
            
            # -------- Resume feature: Check size before request ---------
            if filepath.exists():
                try:
                    # Pathlib stat is synchronous but acceptable for small metadata check
                    downloaded_bytes = filepath.stat().st_size
                except OSError:
                    downloaded_bytes = 0
            
            # Range header for resuming
            headers = {"Range": f"bytes={downloaded_bytes}-", "User-Agent": ua} 
            
            # Mode: append ('ab') if resuming, write ('wb') if starting fresh (though 'ab' is safer)
            mode = 'ab' 

            async with httpx.AsyncClient(timeout=30) as client:
                try:
                    await cls.start_download(filename)
                    user_success(f'Downloading {filename} Attempt {attempt}/{retries}: starting request...')

                    async with client.stream('GET', url=url, headers=headers) as response:
                        response.raise_for_status()
                        code = response.status_code
                        
                        # --- Handle non-resumable download (Server returns 200 instead of 206) ---
                        if code == 200 and downloaded_bytes > 0:
                            user_info("Server ignored Range header (200 OK). Starting download from scratch.")
                            try:
                                await aiofiles.os.remove(filepath)
                            except FileNotFoundError:
                                pass 
                            downloaded_bytes = 0 
                            # Continue to the next attempt, which will now start with a fresh file
                            continue 

                        # --- TQDM SETUP START ---
                        # 1. Determine total size from headers
                        total_size = 0
                        content_range = response.headers.get('Content-Range')
                        content_length = response.headers.get('Content-Length', '0')
                        
                        if code == 206 and content_range:
                            # Resume successful (206 Partial Content)
                            expected_total = int(content_range.split('/')[-1])
                            total_size = expected_total
                        elif code == 200:
                            # New download (200 OK)
                            total_size = int(content_length)
                        

                            
                        # --- Handle edge cases based on status code ---
                        elif code == 416: # 416 Range Not Satisfiable (download likely complete)
                            if filepath.exists() and filepath.stat().st_size == total_size: # Assuming total_size was set previously or correctly inferred
                                user_success(f"File {filename} already fully downloaded (416 received).")
                                await cls.update_client(filename=filename, filepath=filepath)
                                await cls._cleanup_markers(filename)
                                return
                            # If 416 but size is wrong, something went wrong, restart from 0
                            downloaded_bytes = 0
                            user_error("416 received but local file size mismatch, restarting.")
                            await aiofiles.os.remove(filepath)
                            continue # Restart loop

                        # Only proceed if we have a total size and haven't fully downloaded
                        if downloaded_bytes < total_size and total_size > 0:
                            
                            # Use aiofiles.open for asynchronous file handling
                            async with aiofiles.open(filepath, mode=mode) as f:
                                # Use tqdm for async progress bar
                                with tqdm(
                                    initial=downloaded_bytes,
                                    total=total_size,        
                                    desc=f"Downloading {filename}",
                                    unit='B',
                                    unit_scale=True,
                                    disable=(total_size == 0)
                                ) as t:

                                    # Iterate over bytes from the stream
                                    async for chunk in response.aiter_bytes(chunk_size=chunksize):
                                        
                                        # Check for pause/cancel markers in the loop
                                        pause_marker = pause_marker_path(filename)
                                        cancel_marker = cancel_marker_path(filename)

                                        # ------- pause / resume feature (non-blocking sleep) -------
                                        # Note: Checking existence is synchronous but fast
                                        while pause_marker.exists():
                                            user_info(f"Download paused for {filename}")
                                            await asyncio.sleep(1.0) 

                                        # ---------- Cancel feature ----------
                                        if cancel_marker.exists():
                                            user_error(f'Download cancelled for {filename}')
                                            if filepath.exists():
                                                await aiofiles.os.remove(filepath)
                                            
                                            await cls._cleanup_markers(filename)
                                            user_info(f'Cleanup complete for {filename}')
                                            return
                                        
                                        # Write the chunk and update progress
                                        if chunk:
                                            await f.write(chunk)
                                            t.update(len(chunk))
                                            
                            # --- Integrity Check after file is fully streamed and closed ---
                            final_size = filepath.stat().st_size
                            if final_size != total_size:
                                # Invalid file integrity. Re-starting download
                                try:
                                    await aiofiles.os.remove(filepath)
                                except FileNotFoundError:
                                    pass
                                user_error(f"Download finished but file size mismatch: {final_size} != {total_size}. Restarting...")
                                base_logger.internal("Corrupted file data restarting download")
                                continue # Go to the next retry attempt
                            else:
                                # SUCCESS PATH
                                user_success(f"Download complete for {filename}.")
                                await cls.update_client(filename=filename, filepath=filepath) 
                                await cls._cleanup_markers(filename)
                                return

                # --- Error Handling ---
                except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadError, httpx.WriteError) as err:
                    user_error(f"{type(err).__name__} during download of {filename}. Attempting retry {attempt + 1}/{retries}...")
                    base_logger.internal("HTTPX timeout occurred.")
                    await asyncio.sleep(2 ** attempt)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        # Permanent forbidden error
                        condition = dict(filename=filename)
                        with DB_tasks(file_downloader) as manager:
                            await manager.delete_features(and_conditions=condition)
                            user_error(f'Unable to download {filename}: link forbidden (403).')
                        await cls._cleanup_markers(filename)
                        return
                    elif e.response.status_code == 302:
                            url = response.headers.get('Location', None)
                            if url is None:
                                user_error('URL moved to another Location, unable to reach')
                                return
                            user_error(f'Url moved to another location trying out \'{url}\'')
                            continue
                    
                    user_error(f"HTTP error {e.response.status_code} for {filename}. Attempting retry {attempt + 1}/{retries}...")
                    base_logger.internal(f"HTTPX Status Error: {e.response.status_code}")
                    await asyncio.sleep(2 ** attempt * 3)
                except KeyboardInterrupt:
                    user_info('Keyboard Interupt Aborting...')
                    await asyncio.sleep(0.7)
                    await cls.cancel_download(filename)
                    return
                except Exception as e:
                    user_error(f"An unexpected error occurred while downloading {filename}: {type(e).__name__} Stopping...")
                    await asyncio.sleep(1)
                    await cls.cancel_download(filename)
                    raise

        # If the loop finishes without success
        user_error(f"Failed to download {filename} after {retries} attempts.")
        await cls.cancel_download(filename) # Use the async cancel method here
        return