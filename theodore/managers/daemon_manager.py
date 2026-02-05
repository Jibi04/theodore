import asyncio, getpass, json, psutil, struct, threading, numpy

from pathlib import Path
from contextlib import suppress
from typing import Mapping
from datetime import datetime as dt, UTC
from asyncio.exceptions import IncompleteReadError
from watchdog.observers import Observer
from watchdog.events import (
    FileClosedEvent, FileSystemEventHandler, DirMovedEvent, 
    FileMovedEvent, DirDeletedEvent, FileDeletedEvent, 
    )

from theodore.core.paths import SOCKET_PATH
from theodore.core.logger_setup import  system_logs
from theodore.managers.file_manager import FileManager
from theodore.core.exceptions import MissingParamArgument
from theodore.core.file_helpers import resolve_path, organize
from theodore.core.informers import user_info, user_warning, LogsHandler

from theodore.core.paths import (
    SERVER_STATE_FILE, 
    WATCHER_ETL_DIR, 
    CLEANED_ETL_DIR, 
    WATCHER_ORGANIZER, 
    SYS_VECTOR_FILE, 
    DF_CHANNEL
    )


class Signal:
    def __init__(self, client_cb, socket: str | Path = SOCKET_PATH):
        self.socket = Path(socket)
        self.client_cb = client_cb
        self._signal_shutdown_event = asyncio.Event()

    async def start(self) -> None:
        if self.socket.exists():
            self.socket.unlink(missing_ok=True)

        self._server = await asyncio.start_unix_server(client_connected_cb=self.client_cb, path=self.socket)
        user_info(
            f"Server Running: since: {dt.now(UTC).strftime("%d/%m/%y, %H:%M:%S")} UTC"
        )

        await self._signal_shutdown_event.wait()

        self._server.close()
        await self._server.wait_closed()
        user_info(
            f"Signal: Server closed! at: {dt.now(UTC).strftime('%d/%m/%y, %H:%M:%S')} UTC"
        )
        self.socket.unlink(missing_ok=True)
        self._signal_shutdown_event.clear()

    def stop(self) -> None:
        self._signal_shutdown_event.set()

class ETL:

    def transform(
        self,
        path: Path | str,
        save_to: Path | str = CLEANED_ETL_DIR,
        **kwds
        ) -> int:

        from theodore.core.etl_helpers import transform_data


        general, numeric = transform_data(path=path, save_to=save_to, **kwds)

        stats = {
            "general": general,
            "numeric": numeric
        }
        DF_CHANNEL.write_text(json.dumps(stats, indent=2))
        return 1

class FileEventHandler:
    def __init__(self, organizer_path=WATCHER_ORGANIZER, etl_path=WATCHER_ETL_DIR):
        resolved_paths = []
        for p in (organizer_path, etl_path):
            if not (path:=resolve_path(p)).exists():
                path.mkdir(exist_ok=True, parents=True)
                user_info(f"Target path {str(p)}, not resolved. \nCreating directory at {str(path.absolute())}")
            resolved_paths.append(p)

        self._user = getpass.getuser()
        self._watcher_shutdown_event = threading.Event()
        self._observer_target_organizer = resolved_paths[0]
        self._observer_target_etl = resolved_paths[1]
        self._observer = Observer()
        self._file_organize_event = FileEventManager(user=self._user, target_folder=self._observer_target_organizer)
        self._etl_event_handler = ETLEventManager(target_path=self._observer_target_etl)

    def start(self) -> None:
        user_info("Observer Running")
        self._observer.schedule(event_handler=self._file_organize_event, path=self._observer_target_organizer, recursive=True)
        self._observer.schedule(event_handler=self._etl_event_handler, path=self._observer_target_etl, recursive=True)
        self._observer.start()

        self._watcher_shutdown_event.wait()

        self._observer.join(2)
        self._observer.stop()
        user_info("Observer Stopped")

    def stop(self) -> None:
        self._watcher_shutdown_event.set()

class SystemMonitor:
    def __init__(self):
        self._monitor_shutdown_event = threading.Event()
        self.log_handler = LogsHandler()

    def start(self, interval=15) -> None:
        # Start Observer
        system_logs.info("System Monitor running")
        while not self._monitor_shutdown_event.is_set():
            try:
                get_current_metrics(interval)
                self._monitor_shutdown_event.wait(interval)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                raise
            except KeyboardInterrupt:
                raise

    def stop(self) -> None:
        if self._monitor_shutdown_event.is_set():
            system_logs.info("System Monitor is currently not running")
            return
        self._monitor_shutdown_event.set()
        system_logs.info("System Monitor Stopped")

class Worker:
    def __init__(self, scheduler, downloads_manager, dispatch):

        self.__dispatch = dispatch
        self.__scheduler = scheduler
        self.__monitor = SystemMonitor()
        self.__log_handler = LogsHandler()
        self.__downloader = downloads_manager
        self.__file_event_handler = FileEventHandler()
        self.__signal = Signal(client_cb=self.handler)

        self._worker_shutdown_event = asyncio.Event()
        self.__cmd_registry = {
            "STOP-PROCESSES": {"basename": "STOP-PROCESSES", "func": self.start_processes},
            "RESUME": {"basename": "DownloadManager - Resume", "func": self.__downloader.resume},
            "STOP": {"basename": "DownloadManager - Stop", "func": self.__downloader.stop_download},
            "PAUSE": {"basename": "DownloadManager - Pause", "func": self.__downloader.pause},
            "DOWNLOAD": {"basename": "Download Manager - Download", "func": self.__downloader.download_file},
            "START-ETL": {"basename": "SCHEDULER", "func": organize}
        }

    async def start_processes(self) -> None:
        asyncio.create_task(
            asyncio.to_thread(
                self.__monitor.start,
                3
            ),
            name="system-monitor"
        )

        asyncio.create_task(
            asyncio.to_thread(
                self.__file_event_handler.start
            ),
            name="file-event-handler"
        )

        asyncio.create_task(
            self.__scheduler.start_jobs(),
            name="Scheduler"
        )

        self.signal_task = asyncio.create_task(
            self.__signal.start(),
            name="unix-server"
            )

        SERVER_STATE_FILE.write_text("running")
        await self._worker_shutdown_event.wait()
        # cleanup
        DF_CHANNEL.unlink(missing_ok=True)
        SYS_VECTOR_FILE.unlink(missing_ok=True)
        SERVER_STATE_FILE.unlink(missing_ok=True)

    async def stop_processes(self) -> None:
        try:

            await self.__dispatch.shutdown()
            self.__monitor.stop()
            self.__file_event_handler.stop()
            self.__scheduler.stop_jobs()
            self.__signal.stop()

            # Await server shutdown
            with suppress(TimeoutError):
                await asyncio.wait_for(self.signal_task, timeout=1)

            # free blocking start-processes method

            self._worker_shutdown_event.set()
        # cleanup
        finally:
            SYS_VECTOR_FILE.unlink(missing_ok=True)
            DF_CHANNEL.unlink(missing_ok=True)
            SERVER_STATE_FILE.unlink(missing_ok=True)

    async def __parse_message(self, reader: asyncio.StreamReader) -> bytes | None:
        try:
            header = await reader.readexactly(4)

            # unpack from a network stream
            (size,) = struct.unpack("!I", header)
            if size > 1000_000_000:
                user_info("Reader: message too large")
                return None

            payload = await reader.readexactly(size)
            return payload
        except IncompleteReadError as e:
            if not e.partial: # no new command comming
                return None
            raise

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # handler is no longer open-read-write-close.
        try:
            # wait for a minute after connection creation if no message close.
            try:
                message_bytes = await asyncio.wait_for(
                    self.__parse_message(reader),
                    timeout=60
                )
            except TimeoutError:
                return

            if message_bytes is None:
                writer.write(
                    "Reader: Invalid Message format".encode()
                )
                await writer.drain()
                return

            try:
                message = json.loads(message_bytes)
            except json.JSONDecodeError:
                writer.write(b"Invalid Json")
                await writer.drain()
                return

            cmd = message.get("cmd", None)
            args = message.get("file_args")

            cmd_register = self.__cmd_registry.get(cmd, None)
            if cmd_register is None:
                writer.write(f"Reader: unknown command '{cmd}'".encode())
                await writer.drain()
                return

            await self.process_cmd(cmd_register, file_args=args)
            writer.write(f"Worker: {cmd} Initiated".encode())
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except (BrokenPipeError, OSError, IncompleteReadError) as e:
            raise
        except Exception as e:
            raise
        finally:
            if writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def process_cmd(self, cmd_dict: Mapping[str, str], file_args) -> None:
        # Kill-switch for all tasks
        basename = cmd_dict.get("basename")
        func = cmd_dict.get("func")
        if func is None:
            raise MissingParamArgument(f"Command Not resolved Func not understood")

        match basename:
            case "STOP-PROCESSES" | "STOP-SERVERS":
                await self.stop_processes()
                return
            case "SCHEDULER":
                self.__scheduler.new_job(func=func, **file_args)
                return


        if isinstance(file_args, list):
            self.__dispatch.dispatch_many(basename=basename, func=func, func_kwargs=file_args)
            return
        self.__dispatch.dispatch_one(basename, func, file_args)
        return

class ETLEventManager(FileSystemEventHandler):
    def __init__(self, target_path: str | Path):
        self.target_path = target_path
        self.file_manager = FileManager()
        self.etl_manager = ETL()

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        if (p:=resolve_path(event.src_path)).is_dir():
            return organize(p)
        return super().on_moved(event)

    def on_closed(self, event: FileClosedEvent) -> None:
        if (p:=resolve_path(event.src_path)).is_dir():
            return organize(p)
        user_info(f"File detected in data directory. Processing...\nPath: {str(p)}")
        if not p.suffix == ".csv":
            return self.file_manager.move_dst_unknown(src=p)
        signal = self.etl_manager.transform(path=p)
        if signal:
            self.file_manager.move_file(src=str(event.src_path), dst="~/scripts/theodore/theodore/tests/original_files")
        return super().on_closed(event)

class FileEventManager(FileSystemEventHandler):
    def __init__(self, user: str, target_folder: str = ""):
        self._target_folder = target_folder
        self._user = user
        self.file_manager = FileManager()

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        user_info(f"{event.src_path} Moved to {event.dest_path}. USER: {self._user}")

    def on_closed(self, event: FileClosedEvent) -> None:
        if (path:=resolve_path(event.src_path)).is_dir():
            return
        user_info(f"New {resolve_path(event.src_path).suffix} file Detected Processing...\n {event.src_path}")
        self.file_manager.move_dst_unknown(src=path)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        user_warning(f"{event.src_path} Deleted. USER: {self._user}")

def get_current_metrics(interval):
    me = psutil.Process()

    cpu = psutil.cpu_percent(interval)
    disk = psutil.disk_usage('/').percent

    net = psutil.net_io_counters()

    sent = round(net.bytes_sent/(1024**2), )
    recv = round(net.bytes_recv/(1024**2), 2)

    ram = round(me.memory_info().rss/1024**2, 2)
    threads = me.num_threads()

    dirs = Path(__file__).parent.parent/"data"/"vectors"
    dirs.mkdir(parents=True, exist_ok=True)

    csv_filepath = dirs/"sys_vectors.csv"

    vectors = [cpu, ram, disk, sent, recv, threads]
    numpy.save(file=SYS_VECTOR_FILE, arr=numpy.array(vectors))
    
    with csv_filepath.open('a') as f:
        f.write(f"{cpu},{ram},{disk},{sent},{recv},{threads}\n")

    return
