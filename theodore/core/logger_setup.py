import logging
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler
from theodore.core.theme import console
from pathlib import Path 


# ------------------------------------
LOGS_DIR = Path(__file__).parent.parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def get_logger(name, log_file: str | None = None) -> logging.Logger:
    FILE_PATH = LOGS_DIR / (log_file or "theodore.log")

    # ----------- Httpx showing unwanted logs ------------
    for noisy in ["httpx", "urllib3", "sentence_transformers", "sentence-transformers", "sentence-transformers/all-MiniLM-L6-v2"]:
        logging.getLogger(noisy).setLevel(logging.CRITICAL)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s - %(name)-10s] [%(funcName)-10s:%(lineno)4d] - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S"
    )

    # -------- Console (Client) Logs --------
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        markup=True
    )
    rich_handler.setLevel(logging.INFO)
    logger.addHandler(rich_handler)

    # ------------- File Logs ----------------
    file_handler = RotatingFileHandler(
        FILE_PATH, 
        encoding="utf-8", 
        backupCount=3, 
        maxBytes=2*1024*1024
        )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG) 
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


base_logger = get_logger("theodore", "theodore.log")
error_logger = get_logger("theodore.errors", "theodore.log")
vector_perf = get_logger("theodore.performance", "performance.log")
system_logs = get_logger("theodore.monitor", "monitor.log")
sys_vector_logs = get_logger("theodore.monitor_vector", "sys_vector.log")
