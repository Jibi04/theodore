import shutil
from pathlib import Path
from watchdog.events import DirCreatedEvent, FileCreatedEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
from theodore.core.utils import user_info
from theodore.managers.file_manager import FileManager


class FileManagerEventHandler(PatternMatchingEventHandler):
    def __init__(self, path: str = "~/Downloads"):
        self.watch_path = Path(path)
        self.file_manager = FileManager()
        self.observer = Observer()
        self.destination = "~/scripts/documents"
        super().__init__(patterns=[".csv"])

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        curr_location = str(event.src_path)
        self._event = event
        user_info(f"CSV File detected. Moving to {self.destination} for Processing.")
        self.move(src=curr_location, dst=self.destination)
    

    def move(self, src: str | Path, dst: str | Path) -> None:
        if not Path(src).exists():
            user_info(f"Cannot {src} Non existent")
            return None
        dest = shutil.move(str(src), dst=str(dst))
        user_info(f"Moved CSV to {dest}")

