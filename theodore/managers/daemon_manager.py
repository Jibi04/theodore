import asyncio
import heapq
import getpass
import json
import numpy
import psutil
import struct
import time
import threading
import traceback
from asyncio.exceptions import IncompleteReadError
from datetime import datetime as dt, UTC
from pathlib import Path
import time
from typing import Mapping, Any, Callable, Dict, Tuple, List, Literal
from watchdog.events import FileClosedEvent, FileSystemEventHandler, DirCreatedEvent, FileCreatedEvent, DirMovedEvent, FileMovedEvent, DirDeletedEvent, FileDeletedEvent
from watchdog.observers import Observer

from theodore.core.file_helpers import resolve_path, organize
from theodore.core.logger_setup import base_logger, error_logger, vector_perf, system_logs
from theodore.core.utils import user_info, user_error, user_warning
from theodore.core.time_converters import calculate_runtime_as_timestamp, get_time_difference, get_localzone
from theodore.core.state import TheodoreState
from theodore.core.etl_helpers import transform_data
from theodore.managers.file_manager import FileManager
from theodore.managers.schedule_manager import ValidationError, InvalidScheduleTimeError, Job, Status
from theodore.managers.download_manager import DownloadManager
from theodore.managers.schedule_manager import JobManager


STATE_OBJ = TheodoreState()
DEFAULT = Path(__file__).parent.parent/"data"/"datasets"
DEFAULT.mkdir(parents=True, exist_ok=True)

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
        # await self._server.wait_closed()
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
        save_to: str | Path = DEFAULT,
        **kwds
        ):

        df, general_profile, numeric_profile = transform_data(path=path, save_to=save_to, **kwds)

        STATE_OBJ.generalProfile = general_profile
        STATE_OBJ.numericProfile = numeric_profile
        return 1


class SytemMonitor:
    def __init__(self, cpu_threshold: float = 25.0):
        self._monitor_shutdown_event = threading.Event()
        self.log_handler = LogsHandler()
        self.state_obj = STATE_OBJ

    def start(self, interval=35) -> None:

        me = psutil.Process()
        # Start Observer
        system_logs.info("System Monitor running")
        while not self._monitor_shutdown_event.is_set():
            try:
                self.state_obj.cpu = me.cpu_percent(interval)
                self.state_obj.memory = round(me.memory_percent("vms"), 3)
                self.state_obj.ram = round(me.memory_info().rss / 1024 / 1024, 3)
                self.state_obj.threads = me.num_threads()
                self.state_obj.status = me.status()
                self.state_obj.processName = me.name()
                self.state_obj.processID = me.pid
                self.state_obj.username = me.username()
                system_logs.internal(f"CPU: {self.state_obj.cpu}% Process Name: {self.state_obj.processName} Memory Used: {self.state_obj.memory}% RAM: {self.state_obj.ram} MB STATUS: {self.state_obj.status} THREADS: {self.state_obj.threads} USER: {self.state_obj.username}"
                                    )
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
        self._job_manager: JobManager = JobManager()
        self._dispatch = Dispatch()
        self._heaper = Heaper()
        self.__in_active_jobs: Dict[Any, Job] = {}
        self.__scheduler_shutdown_event = asyncio.Event()
        self.__sleep_event = asyncio.Event()

    def new_job(
            self, 
            *,
            key: Any,
            func: Callable[..., None], 
            func_args: Dict[Any, Any] | None = None,
            trigger: Literal["cron", "interval"],
            seconds: float | str| None = "*",
            min: float | str | None= "*",
            hour: int | str | None = "*",
            dow: int | None = None,
            profiling_enabled: bool = False
        ):

        time_blueprint = {
            "second": seconds,
            "minute": min,
            "hour": hour,
        }

        runtime_registry = {}
        for k, val in time_blueprint.items():
            if val != "*" and val is not None:
                runtime_registry[k] = val
        
        runtime = calculate_runtime_as_timestamp(target=runtime_registry, dow=dow)
        if runtime is None:
            user_error(f"Invalid time Args. {json.dumps(runtime_registry, indent=2)}")
            return

        try:
            job = self._job_manager.add_job(
                key=key.lower(),
                func=func,
                func_args=func_args,
                next_runtime=runtime,
                trigger=trigger,
                status=Status.active,
                runtime_registry=runtime_registry,
                profiling_enabled=profiling_enabled
            )
        except ValidationError:
            raise

        self.__in_active_jobs[key] = job
        self._heaper.add_to_heap(job=job)
        self.__sleep_event.set()
        user_info(f"new job created! key: '{key}'")

    async def start(self):
        user_info("Scheduler Running")
        while not self.__scheduler_shutdown_event.is_set():
            if not self._heaper.heap:
                sleep_task = asyncio.create_task(self.__sleep_event.wait())
                shutdown_task = asyncio.create_task(self.__scheduler_shutdown_event.wait())
                
                done, pending = await asyncio.wait(
                    [sleep_task, shutdown_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                # cleanup
                for t in pending: t.cancel() 

                self.__sleep_event.clear()
                if self.__scheduler_shutdown_event.is_set(): break
                
                if not self._heaper.heap: continue

            runtime, key = self._heaper.peek_first()
            diff = max(get_time_difference(runtime), 0)

            print(f"this is runtime: {runtime}, this is now {dt.now(get_localzone()).timestamp()}")
            if diff > 0:
                sleep_task = asyncio.create_task(self.__sleep_event.wait())
                shutdown_task = asyncio.create_task(self.__scheduler_shutdown_event.wait())
                
                # Race the clock vs the signals
                done, pending = await asyncio.wait(
                    [sleep_task, shutdown_task],
                    timeout=diff,
                    return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending: t.cancel() # Clean up
                self.__sleep_event.clear()
                
                if self.__scheduler_shutdown_event.is_set(): break
                if sleep_task in done: continue 

            # If we reach here, the timeout expired or diff was 0: TIME TO RUN
            job = self.__in_active_jobs.get(key)
            if job:
                self.start_job(job=job)
                self._heaper.remove()
        user_info("Scheduler Shutdown.")


    def start_job(self, job: Job):
        next_runtime = calculate_runtime_as_timestamp(
                target=job.runtime_registry, 
                dow=job.dow
                )
        
        if next_runtime is None:
            raise InvalidScheduleTimeError(f"Unable to understand job time parameters '{job.dow}'")
        
        if job.trigger == "cron":
            job.next_runtime = next_runtime
            self._heaper.add_to_heap(job)
            self.__sleep_event.set()
            
        
        coro_func = job.func
        name = f"Sheduler"

        coro_func_args = job.func_args

        if isinstance(coro_func_args, list):
            self._dispatch.dispatch_many(
                basename=name,
                func=coro_func,
                func_kwargs=coro_func_args
                )
        else:
            self._dispatch.dispatch_one(
                basename=name,
                func=coro_func,
                func_kwargs=coro_func_args
            )
        
        self._running_jobs[job.key] = job

    def stop(self):
        self.__scheduler_shutdown_event.set()
            
    
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
    def __init__(self, observer_path: str, target_path):
        if not Path(observer_path).expanduser().exists():
            user_info(f"FileHandler: {observer_path} doesn't exist!")
            return
        
        self._user = getpass.getuser()
        self._watcher_shutdown_event = threading.Event()
        self._observer_target = Path(observer_path).expanduser()
        self._observer = Observer()
        self._event = FileEventManager(user=self._user, target_folder=target_path)

    def start(self):
        user_info("Observer Running")

        self._observer.schedule(event_handler=self._event, path=str(self._observer_target), recursive=True)
        self._observer.start()

        self._watcher_shutdown_event.wait()

        self._observer.stop()
        self._observer.join()

        user_info("Observer Stopped")

    def stop(self):
        self._watcher_shutdown_event.set()


class Worker:
    def __init__(self):
        self.__signal = Signal(client_cb=self.handler)
        self.__dispatch = Dispatch()
        self.__scheduler = Scheduler()
        self.__monitor = SytemMonitor()
        self.__log_handler = LogsHandler()
        self.__file_event_handler = FileEventHandler(observer_path="~/Downloads", target_path="Theodore_etl")
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
        # loop = asyncio.get_running_loop()
        # loop.add_signal_handler(signal.SIGINT, self.stop_processes)
        # loop.add_signal_handler(signal.SIGTERM, self.stop_processes)
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
            self.__scheduler.start(),
            name="Scheduler"
        )

        self.signal_task = asyncio.create_task(
            self.__signal.start(),
            name="unix-server"
            )
        
        await self._worker_shutdown_event.wait()

    async def stop_processes(self) -> None:

        await self.__dispatch.shutdown()
        self.__monitor.stop()
        self.__file_event_handler.stop()
        self.__scheduler.stop()
        self.__signal.stop()

        # Await server shutdown
        await self.signal_task

        # free blocking start-processes method
        self._worker_shutdown_event.set()
       
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
            case "STOP-PROCESSES":
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





class FileEventManager(FileSystemEventHandler):
    def __init__(self, user: str, target_folder: str = ""):
        
        self._target_folder = target_folder
        self._file_manager = FileManager()
        self.etl_handler = ETL()
        self._user = user

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        user_info(f"{event.src_path} Moved to {event.dest_path}. USER: {self._user}")

    def on_closed(self, event: FileClosedEvent) -> None:
        if (path:=resolve_path(event.src_path)).is_dir():
            return
        
        if path.suffix == ".csv":
            start = time.perf_counter()
            success = self.etl_handler.transform(path=path)
            end = time.perf_counter()
            vector_perf.internal(numpy.array([1 if success else 0, end - start, ""]))
            return 
        self._file_manager.move_dst_unknown(src=path)
    
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None:
        user_warning(f"{event.src_path} Deleted. USER: {self._user}")
   