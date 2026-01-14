import time
import shutil
from pathlib import Path
from watchdog.events import LoggingEventHandler, DirCreatedEvent, FileCreatedEvent, DirMovedEvent, FileMovedEvent, DirDeletedEvent, FileDeletedEvent
from watchdog.observers import Observer
from theodore.core.utils import user_info
from theodore.core.logger_setup import base_logger


class FileEventManager(LoggingEventHandler):
    def __init__(self, user: str, target_folder: str = ""):
        self._target_folder = target_folder
        self._user = user
        super().__init__(logger=base_logger)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        user_info(f"New Item detected '{self.parse_name(event.src_path)}'. Moving to {self.parse_name(self._target_folder)} for Processing. USER: {self._user}.")

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        user_info(f"{self.parse_name(event.src_path)} Moved to {event.dest_path}. USER: {self._user}")
    
    # def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
    #     user_info(f"Folder Contents Modified. USER: {self._user}")
    
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        user_info(f"{self.parse_name(event.src_path)} Deleted. USER: {self._user}")

    def parse_name(self, event_name: str | bytes) -> str:
        return Path(str(event_name)).name
    
    def move(self, src: str | Path, dst: str | Path) -> None:
        if not Path(src).exists():
            user_info(f"Cannot {src} Non existent")
            return None
        dest = shutil.move(str(src), dst=str(dst))
        user_info(f"Moved CSV to {dest}")



if __name__ == "__main__":
    import getpass
    user = getpass.getuser()
    observer = Observer()
    event = FileEventManager(user=user, target_folder="Home")
    path = Path("~/scripts/theodore/theodore").expanduser()

    observer.schedule(event_handler=event, path=str(path), recursive=True)
    observer.start()
    print("observer Started")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        user_info("Observer closed")