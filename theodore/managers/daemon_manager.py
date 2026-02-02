import asyncio, heapq, getpass, json, psutil, struct, time, threading, traceback, tempfile, numpy

from asyncio.exceptions import IncompleteReadError
from datetime import datetime as dt, UTC
from pathlib import Path
from typing import Mapping, Any, Callable, Dict, Tuple, List, Literal
from watchdog.observers import Observer
from watchdog.events import (
    FileClosedEvent, FileSystemEventHandler, DirMovedEvent, 
    FileMovedEvent, DirDeletedEvent, FileDeletedEvent, 
    )

from theodore.core.file_helpers import resolve_path, organize
from theodore.core.logger_setup import base_logger, error_logger, vector_perf, system_logs
from theodore.core.informers import user_info, user_error, user_warning
from theodore.core.time_converters import calculate_runtime_as_timestamp, get_time_difference, get_localzone
from theodore.managers.file_manager import FileManager
from theodore.managers.schedule_manager import ValidationError, Job, Status
from theodore.core.exceptions import InvalidScheduleTimeError
from contextlib import suppress

from theodore.core.paths import (
    SERVER_STATE_FILE, 
    WATCHER_ETL_DIR, 
    CLEANED_ETL_DIR, 
    WATCHER_ORGANIZER, 
    SYS_VECTOR_FILE, 
    DF_CHANNEL
    )


class Signal:
    def __init__(self, client_cb, socket: str | Path = "/tmp/theodore.sock"):
        self.socket = Path(socket)
        self.client_cb = client_cb
        self._signal_shutdown_event = asyncio.Event()

    async def start(self):
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

    def stop(self):
        self._signal_shutdown_event.set()

class ETL:

    def transform(
        self,
        path: Path | str,
        save_to: Path | str = CLEANED_ETL_DIR,
        **kwds
        ):

        from theodore.core.etl_helpers import transform_data


        general, numeric = transform_data(path=path, save_to=save_to, **kwds)

        stats = {
            "general": general,
            "numeric": numeric
        }
        DF_CHANNEL.write_text(json.dumps(stats, indent=2))
        return 1

class Dispatch:

    def __init__(self):
        self.supervisor = Supervisor()

    def dispatch_one(self, basename,  func, func_kwargs):
        self._run(task_name=basename, func=func, func_kwargs=func_kwargs)

    def dispatch_many(self, basename, func, func_kwargs):
        for i, kwargs in enumerate(func_kwargs):
            task_name = f"{basename}-{i}"
            self._run(task_name, func=func, func_kwargs=kwargs)

    def _run(self, task_name, func, func_kwargs):
        task = asyncio.create_task(
            self.supervisor.supervise(
                func=func,
                func_kwargs=func_kwargs
            ),
            name=task_name
        )

        self.supervisor.tasks.add(task)
        task.add_done_callback(self.supervisor.tasks.discard)

    async def shutdown(self):
        user_info("Cleaning pending tasks...")
        for task in self.supervisor.tasks:
            task.cancel()
        return await asyncio.gather(*self.supervisor.tasks, return_exceptions=True)

class Scheduler:
    def __init__(self):


        self._running_jobs: Dict[str, Job] = {}
        
        self.__scheduler_shutdown_event = asyncio.Event()

    def new_job(
            self,
            *,
            key: Any,
            func: Callable[[Any], None] | None,
            func_path: str | None,
            module: str | None,
            method: str | None,
            cls_name: str | None,
            func_args: Dict[Any, Any] | None = None,
            trigger: Literal["cron", "interval"],
            second: int | None = None,
            minute: int | None = None,
            hour: int | None = None,
            day: int | None = None,
            dow: int | None = None,
            week: int | None = None,
            month: int | None = None,
            year: int | None = None,
            profiling_enabled: bool = False
        ):
        from theodore.managers.schedule_manager import Job, FunctionModel, RuntimeModel, Status

        runtime_model= RuntimeModel(
            second=second,
            hour=hour,
            minute=minute,
            day=day,
            day_of_week=dow,
            week=week,
            month=month,
            year=year
        )

        function_model = FunctionModel(
            func_path=func_path,
            module=module,
            method=method,
            cls_name=cls_name,
            func=func
        )

        job = Job(
            key=key,
            trigger=trigger,
            function_model=function_model,
            runtime_model=runtime_model,
            func_args=func_args,
            profiling_enabled=profiling_enabled,
            status=Status.inactive,
        )

        scheduler = self.schedule_job(job)
        user_info(f"new job created! key: '{key}'")

    def schedule_job(self, job: Job):
        # trigger_func = __trigger_format__[job.trigger]
        # trigger = trigger_func(job.runtime_model.model_dump())
        # func = parse_function(job.function_model.model_dump())

        # if is_async(func):
        #     return schedule_async(func, trigger)
        
        # return schedule_sync(func, trigger)
        pass
        
    def stop(self):
        pass

class Heaper:
    def __init__(self):
        self.heap: List[Tuple[float, Any]] = list()
        heapq.heapify(self.heap)

    def add_to_heap(self, job: Job):
        runtime = job.next_runtime
        key = job.key

        heapq.heappush(self.heap, (runtime, key))

    def peek_first(self):
        return self.heap[0]

    def get_first(self):
        return heapq.heappop(self.heap)

    def update_heap(self, runtime: float, key: Any):
        heapq.heappushpop(self.heap, (runtime, key))

    def remove(self):
        heapq.heappop(self.heap)

class Supervisor:

    def __init__(self):
        self.__log_handler = LogsHandler()
        self.tasks: set[asyncio.Task] = set()

    async def supervise(self, func, func_kwargs):
        task_name = "Supervisor-"
        try:
            start = time.perf_counter()
            if asyncio.iscoroutinefunction(func):
                result = await func(**func_kwargs)
            else:
                result = func(**func_kwargs)
            stop = time.perf_counter()
            vector_perf.internal(numpy.array([1, stop - start]))

            current_task = asyncio.current_task()
            if current_task:
                task_name = current_task.get_name()
            user_info(f"Supervisor: Task done - {result} took: {round(time.perf_counter() - start, 2)}s")
            self.__log_handler.inform_base_logger(
                task_name=task_name,
                status="Completed",
                task_response=result
            )
        except asyncio.CancelledError:
            self.__log_handler.inform_error_logger(
                task_name=task_name,
                error_stack=self.__log_handler.format_error(),
                reason="Task Cancelled"
            )
            raise
        except (OSError, RuntimeError) as e:
            self.__log_handler.inform_error_logger(
                task_name=task_name,
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )
            raise
        except Exception as e:
            raise

class LogsHandler:

    def format_error(self) -> str:
        return traceback.format_exc()

    def inform_error_logger(self, task_name, error_stack, reason, status: str = "Cancelled"):
        error_logger.internal(
                f"""
Task Name: {task_name}
status: {status}
Reason: {reason}
Error stack: {error_stack}
                """
            )

    def inform_base_logger(self, task_name: str, task_response: Any, status):
        base_logger.internal(
        f"""
Task Name: {task_name}
status: {status}
Task response: {task_response}
                """)

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

    def start(self):
        user_info("Observer Running")
        self._observer.schedule(event_handler=self._file_organize_event, path=self._observer_target_organizer, recursive=True)
        self._observer.schedule(event_handler=self._etl_event_handler, path=self._observer_target_etl, recursive=True)
        self._observer.start()

        self._watcher_shutdown_event.wait()

        self._observer.join(2)
        self._observer.stop()
        user_info("Observer Stopped")

    def stop(self):
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
    def __init__(self):
        from theodore.managers.download_manager import DownloadManager

        self.__signal = Signal(client_cb=self.handler)
        self.__dispatch = Dispatch()
        # self.__scheduler = Scheduler()
        self.__monitor = SystemMonitor()
        self.__log_handler = LogsHandler()
        self.__file_event_handler = FileEventHandler()
        self.__downloader = DownloadManager()
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

        # asyncio.create_task(
        #     self.__scheduler.start(),
        #     name="Scheduler"
        # )

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
            # self.__scheduler.stop()
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

    async def send_signal(self, header: bytes, message: bytes):
        try:
            reader, writer = await asyncio.open_unix_connection(self.__signal.socket)
        except FileNotFoundError:
            user_info("Could Not open Connections at this time. start servers so theodore can process your commands.")
            return
        try:
            if writer.is_closing():
                user_info("Messenger: Cannot send messages at this time, No open Connection")
                return
            writer.write(header)
            writer.write(message)
            await writer.drain()

            message = await reader.read(1024)
            user_info(message.decode())
            return
        except (IncompleteReadError, InterruptedError, asyncio.CancelledError):
            user_info("A connection error occurred whilst parsing command check logs for more details.")
            self.__log_handler.inform_error_logger(
                task_name="Messenger",
                reason="Connection Interupted",
                error_stack=self.__log_handler.format_error(),
                status="Signal Not sent!"
                )
        except (BrokenPipeError, OSError):
            user_info("A connection error occurred whilst parsing command check logs for more details.")
            self.__log_handler.inform_error_logger(
                task_name="Messenger",
                reason="BrokenPipe",
                error_stack=self.__log_handler.format_error(),
                status="Signal Not sent!"
                )
        except Exception as e:
            user_info("An error Occurred whilst parsing command check logs for more details.")
            self.__log_handler.inform_error_logger(
                task_name="Messenger",
                reason=type(e).__name__,
                error_stack=self.__log_handler.format_error(),
                status="Signal Not sent!"
                )
        finally:
            if writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def process_cmd(self, cmd_dict: Mapping[str, str], file_args):
        # Kill-switch for all tasks
        basename = cmd_dict.get("basename")
        func = cmd_dict.get("func")
        if func is None:
            raise

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
