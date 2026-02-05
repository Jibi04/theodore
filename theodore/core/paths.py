from dotenv import find_dotenv, load_dotenv
from pathlib import Path
import tempfile
import os


DATA_DIR = Path(__file__).parent.parent / "data"

JSON_DIR = DATA_DIR / "json"
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
FILE = JSON_DIR / "cache.json"

MODELS_PATH = DATA_DIR/"models"
MODELS_PATH.mkdir(parents=True, exist_ok=True)

TRANSFORMER_MODEL_PATH = MODELS_PATH/"all_MiniLM_L6_v2"

SOCKET_PATH = TEMP_DIR/"theodore.sock"

DF_CHANNEL = Path(f"{TEMP_DIR}/transformed_data.json")
SYS_VECTOR_FILE = Path(f"{TEMP_DIR}/sys_vector.npy")
SERVER_STATE_FILE = Path(f"{TEMP_DIR}/server_state.lock")
WATCHER_ORGANIZER = Path("~/Downloads").expanduser().absolute()
WATCHER_ETL_DIR = Path(__file__).parent.parent/"data"/"datasets"/"uncleaned_csv_files"
CLEANED_ETL_DIR = Path(__file__).parent.parent/"data"/"datasets"/"cleaned_csv_files"

WATCHER_ORGANIZER.mkdir(parents=True, exist_ok=True)
CLEANED_ETL_DIR.mkdir(parents=True, exist_ok=True)
WATCHER_ETL_DIR.mkdir(parents=True, exist_ok=True)

def get_db_path():

    ENV_PATH = find_dotenv()
    load_dotenv(ENV_PATH)

    db_name = os.getenv('DB_NAME')
    BASE_DIR = Path(__file__).parent.parent.resolve()
    DB_PATH = Path(f"{BASE_DIR}/data/{db_name}")
    DB = f"sqlite+aiosqlite:///{DB_PATH}"

    return DB