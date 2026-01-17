import asyncio
import heapq
import getpass
import json
import psutil
import struct
import time
import threading
import traceback
from asyncio.exceptions import IncompleteReadError
from datetime import datetime as dt, UTC, timedelta
from pathlib import Path
from typing import Mapping, Any, Callable, Coroutine, Dict, Tuple, List
from watchdog.observers import Observer
from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.utils import user_info, user_error
from theodore.managers.download_manager import DownloadManager
from theodore.managers.event_handler import FileEventManager
from theodore.tests.converters import get_timestamp, calculate_runtime_as_timestamp, is_ready_to_run, get_time_difference
from theodore.managers.schedule_manager import JobManager, JobNotFoundError, ValidationError, InvalidScheduleTimeError, Job, InvalidCoroutineFunctionError, Status, Trigger


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


class SytemMonitor:
    def __init__(self, cpu_threshold: float = 25.0):
        self.cpu_threshold = cpu_threshold
        self._monitor_shutdown_event = threading.Event()
        self.log_handler = LogsHandler()

    def start(self, interval) -> None:

        me = psutil.Process()
        # Start Observer
        user_info("System Monitor running")
        while not self._monitor_shutdown_event.is_set():
            try:
                cpu = me.cpu_percent(None)
                if cpu > 20:
                    mem = me.memory_percent()
                    RAM = me.memory_info().rss / 1024 / 1024
                    threads = me.num_threads()
                    user_info(f"CPU={cpu} Name={me.name()} RAM={RAM: .2f}MB MEM={mem: .2f}% STATUS={me.status()} Threads-Running={threads}")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                raise
            except KeyboardInterrupt:
                raise
            self._monitor_shutdown_event.wait()

    def stop(self) -> None:
        if self._monitor_shutdown_event.is_set():
            user_info("System Monitor is currently not running")
            return
        self._monitor_shutdown_event.set()
        user_info("System Monitor Stopped")


class Dispatch:

    def __init__(self):
        self.supervisor = Supervisor()

    def dispatch_one(self, basename,  func, func_kwargs):
        self._run(task_name=basename, func=func, func_kwargs=func_kwargs)

    def dispatch_many(self, basename, func, func_kwargs):
        for i, kwargs in enumerate(func_kwargs):
            task_name = f"{basename}-{i}"
            self._run(task_name, func, kwargs)

    def _run(self, task_name, func, func_kwargs):
        task = asyncio.create_task(
            self.supervisor.supervise(func, func_kwargs),
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
        self._running_jobs: set[Job] = set()
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
            func: Callable[..., Coroutine[Any, Any, Any]], 
            kwargs: Dict[Any, Any] | None = None,
            trigger: Trigger = Trigger.interval,
            seconds: float | str = "*",
            min: float | str = "*",
            hour: int | str = "*",
            dow: int | None = None,
            profiling_enabled: bool = False
        ):

        time_blueprint = {
            "second": seconds,
            "minute": min,
            "hour": hour,
        }

        runtime_registry = {}
        for key, val in time_blueprint.items():
            if val != "*":
                runtime_registry[key] = val

        if not asyncio.iscoroutinefunction(func=func):
            raise InvalidCoroutineFunctionError("Function is Not a coroutine Function")
        
        runtime = calculate_runtime_as_timestamp(target=runtime_registry, dow=dow)
        if runtime is None:
            user_error(f"Invalid time Args. {json.dumps(runtime_registry, indent=2)}")
            return

        try:
            job = self._job_manager.add_job(
                key=key,
                func=func,
                next_runtime=runtime,
                kwargs=kwargs,
                trigger=trigger,
                status=Status.active,
                runtime_registry=runtime_registry,
                profiling_enabled=profiling_enabled
            )
        except ValidationError as e:
            raise

        self.__in_active_jobs[key] = job
        self._heaper.add_to_heap(job=job)
        self.__sleep_event.set()

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
        
        if job.trigger.value == "cron":
            job.next_runtime = next_runtime
            self._heaper.add_to_heap(job)
            self.__sleep_event.set()
            
        
        coro_func = job.func
        kwargs = job.kwargs
        name = f"Sheduler"

        if isinstance(kwargs, list):
            self._dispatch.dispatch_many(
                basename=name,
                func=coro_func,
                func_kwargs=kwargs
                )
        else:
            self._dispatch.dispatch_one(
                basename=name,
                func=coro_func,
                func_kwargs=kwargs
            )
        
        self._running_jobs.add(job)

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

    async def supervise(self, func, kwargs):
        task_name = "Supervisor-"
        try:
            start = time.perf_counter()
            result = await func(**kwargs)
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
            # self.__log_handler.inform_error_logger(
            #     task_name=task_name,
            #     error_stack=self.__log_handler.format_error(),
            #     reason=type(e).__name__
            # )


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
        except IncompleteReadError:
            # propagate to handler
            raise

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # handler is no longer open-read-write-close.
        try:
            while True:
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
                
                await self.process_cmd(cmd_register, args)
                writer.write(f"Worker: {cmd} Initiated".encode())
                await writer.drain()
        except asyncio.CancelledError:
            raise
        except (BrokenPipeError, OSError, IncompleteReadError) as e:
            # self.__log_handler.inform_error_logger(
            #     task_name=f"Handler-{cmd}",
            #     error_stack=self.__log_handler.format_error(),
            #     reason=type(e).__name__
            # )
            # return
            raise
        except Exception as e:
            # self.__log_handler.inform_error_logger(
            #     task_name=f"Handler-Error",
            #     error_stack=self.__log_handler.format_error(),
            #     reason="Handler Error"
            # )
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

    # def install_signal_handlers(self):
    #     loop = asyncio.get_running_loop()

    #     for sig in (signal.SIGTERM, signal.SIGINT):
    #         loop.add_signal_handler(
    #             sig,
    #             self._worker_shutdown_event.set,
    #         )
        
    async def process_cmd(self, cmd_dict: Mapping[str, str], func_kwargs):

        # Kill-switch for all tasks
        basename = cmd_dict.get("basename")

        if basename == "STOP-PROCESSES":
            await self.stop_processes()
            return
        
        func = cmd_dict.get("func")
        if isinstance(func_kwargs, list):
            self.__dispatch.dispatch_many(basename=basename, func=func, func_kwargs=func_kwargs)
            return
        self.__dispatch.dispatch_one(basename, func, func_kwargs)
        return

