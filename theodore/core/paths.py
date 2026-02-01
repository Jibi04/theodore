from pathlib import Path
import tempfile


DATA_DIR = Path(__file__).parent.parent / "data"

JSON_DIR = DATA_DIR / "json"
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
FILE = JSON_DIR / "cache.json"


TEMP_DIR = tempfile.gettempdir()

DF_CHANNEL = Path(f"{TEMP_DIR}/transformed_data.json")
SYS_VECTOR_FILE = Path(f"{TEMP_DIR}/sys_vector.npy")
SERVER_STATE_FILE = Path(f"{TEMP_DIR}/server_state.lock")
WATCHER_ORGANIZER = Path("~/Downloads").expanduser().absolute()
WATCHER_ETL_DIR = Path(__file__).parent.parent/"data"/"datasets"/"uncleaned_csv_files"
CLEANED_ETL_DIR = Path(__file__).parent.parent/"data"/"datasets"/"cleaned_csv_files"

WATCHER_ORGANIZER.mkdir(parents=True, exist_ok=True)
CLEANED_ETL_DIR.mkdir(parents=True, exist_ok=True)
WATCHER_ETL_DIR.mkdir(parents=True, exist_ok=True)