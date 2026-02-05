from theodore.core.logger_setup import base_logger, error_logger
import requests
from pathlib import Path
from http.client import IncompleteRead
from requests.exceptions import HTTPError, ConnectionError, ChunkedEncodingError, ConnectTimeout, ReadTimeout
import time, sys
# from fake_user_agent import user_agent
from theodore.core.utils import send_message
# Import tqdm for progress bar management
from tqdm.auto import tqdm

# ua = user_agent()

class Downloads_manager:

    def update_client(self, filename, movies:dict | str, filepath):
        from theodore.managers.configs_manager import ConfigManager

        manager = ConfigManager()

        # base_logger.info(f'{filename} download complete!')
        # movies.setdefault('downloads', {})
        # movies['downloads'].setdefault('movies', {})
        # movies['downloads']['movies'].setdefault(filename, {})

        # movies['downloads']['movies'][filename].update(
        #     {
        #         "is_downloaded": True,
        #         "date_downloaded": datetime.now(timezone.utc).isoformat(),
        #         "filepath": str(filepath)
        #         })
        
        # manager.save_file(movies, movie=True)

    def download_movie(self, url, filepath, filename=None, chunksize=8192, retries=10):
        filepath = Path(filepath).expanduser()
        
        base_logger.info('Preparing file directory for download')
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if not filename:
            filename = filepath.name

        # movies = manager.load_file(movie=True)


        downloaded_bytes = 0
        if filepath.exists():
            try:
                downloaded_bytes = filepath.stat().st_size
            except OSError:
                downloaded_bytes = 0

        headers = {"Range": f"bytes={downloaded_bytes}-"} if downloaded_bytes > 0 else None
        mode = 'ab' if downloaded_bytes > 0 else 'wb'

        with requests.Session() as session:
            # session.headers.update({"User-Agent": ua})

            for attempt in range(1, retries + 1):
                try:
                    base_logger.info(f'Attempt {attempt}/{retries}: starting request')
                    with session.get(url, stream=True, headers=headers, timeout=30) as r:
                        r.raise_for_status()
                        
                        # --- TQDM SETUP START ---
                        # 1. Determine total size from headers
                        content_range = r.headers.get('content-range')
                        if content_range:
                            expected_total = int(content_range.split('/')[-1])
                        else:
                            expected_total = int(r.headers.get('content-length', 0))

                        # 2. Check if the file is incomplete
                        if downloaded_bytes < expected_total and expected_total > 0:
                            total_size = expected_total  # This is the total file size

                            # 3. Initialize tqdm bar
                            # initial: start from the previously downloaded bytes (for resume)
                            # total: the total expected size
                            # desc: label for the bar (using filename)
                            # unit: bytes
                            # unit_scale: True for B, KB, MB, etc.
                            # disable: only disable if total_size is 0 (optional)
                            with tqdm(
                                initial=downloaded_bytes,
                                total=total_size,
                                desc=f"Downloading {filepath.name}",
                                unit='B',
                                unit_scale=True,
                                disable=(total_size == 0)
                            ) as t:

                                with open(filepath, mode) as f:
                                    for chunk in r.iter_content(chunk_size=chunksize):
                                        if not chunk:
                                            continue
                                        f.write(chunk)
                                        # 4. Use t.update() to advance the progress bar
                                        t.update(len(chunk))
        
                            # --- TQDM SETUP END ---
                        
                            # After the inner 'with tqdm(..)' block, we check the final size
                            final_size = filepath.stat().st_size
                            if final_size != total_size:
                                error_logger.error(f"Download finished but file size mismatch: {final_size} != {total_size}")
                                # Re-raise an error to trigger a retry or final failure
                                raise IncompleteRead(partial=bytes(final_size), expected=total_size)
                    self.update_client(filename=filename, movies="", filepath=filepath)
                    return
                except HTTPError as e:
                    err_msg = str(e)

                    if '416 client error' in err_msg.lower():
                        self.update_client(filename=filename, movies="", filepath=filepath)
                        return
                    error_logger.error(f"HTTP ERROR: ", err_msg)
                    time.sleep(30)
                    if attempt == retries:
                        error_logger.error("Max retries reached. Aborting...")
                        return send_message(False, message=f"Http Error: {err_msg}")
                    continue
                except (IncompleteRead, ConnectionError, ReadTimeout, ChunkedEncodingError, ConnectTimeout) as e:
                    print()
                    error_logger.error(f"{type(e).__name__}: {e}")
                    if attempt == retries:
                        error_logger.error("Max retries reached, Aborting...")
                        return send_message(False, message=f'"error": {str(e)}')
                    for sec in range(5, 0, -1):
                        sys.stdout.write(f"\rRetrying in {sec} seconds...")
                        sys.stdout.flush()
                        time.sleep(1)
                    print()

                except Exception as e:
                    error_logger.error(f"Unexpected error: {e}")
                    return send_message(False, message=f'"error": {str(e)}')

        return send_message(False, message="Download failed unexpectedly")



