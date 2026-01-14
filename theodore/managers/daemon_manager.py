import asyncio
import getpass
import json
import psutil
import struct
import time
import threading
import traceback
from asyncio.exceptions import IncompleteReadError
from datetime import datetime as dt, UTC
from pathlib import Path
from typing import Mapping, Any
from watchdog.observers import Observer
from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.utils import user_info
from theodore.managers.download_manager import DownloadManager
from theodore.managers.file_handler import FileEventManager


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
        user_info(
            f"Signal: Server closed! at: {dt.now(UTC).strftime("%d/%m/%y, %H:%M:%S")} UTC"
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
            self._monitor_shutdown_event.wait(interval)

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
        except (KeyboardInterrupt, InterruptedError):
            self.__log_handler.inform_error_logger(
                task_name=task_name,
                error_stack=self.__log_handler.format_error(),
                reason="Task Interupted"
            )
        except (OSError, RuntimeError) as e:
            self.__log_handler.inform_error_logger(
                task_name=task_name,
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )
        except Exception as e:
            self.__log_handler.inform_error_logger(
                task_name=task_name,
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )


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

        self.signal_task = asyncio.create_task(
            self.__signal.start(),
            name="unix-server"
            )
        
        await self._worker_shutdown_event.wait()


    async def stop_processes(self) -> None:

        await self.__dispatch.shutdown()
        self.__monitor.stop()
        self.__file_event_handler.stop()
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
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-{cmd}",
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )
            return
        except Exception as e:
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-Error",
                error_stack=self.__log_handler.format_error(),
                reason="Handler Error"
            )
        finally:
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
            if not writer.is_closing():
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

