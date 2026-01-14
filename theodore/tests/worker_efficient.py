import asyncio
import json
import psutil
import struct
import time
import traceback
from datetime import datetime as dt, UTC
from pathlib import Path
from typing import Mapping, Any
from asyncio.exceptions import IncompleteReadError
from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.utils import user_info
from theodore.managers.download_manager import DownloadManager


class Signal:
    def __init__(self, client_cb, socket: str | Path = "/tmp/theodore/theodore.sock"):
        self.socket = Path(socket)
        self.client_cb = client_cb
        self.__now = dt.now(UTC)

    async def start(self):
        if self.socket.exists():
            self.socket.unlink(missing_ok=True)

        self._server = await asyncio.start_unix_server(client_connected_cb=self.client_cb, path=self.socket)
        user_info(f"Server Running: since{self.__now}")
        return await self._server.serve_forever()
    
    async def stop(self):
        try:
            if not self._server.is_serving():
                user_info("Server Is Currently not running")
                return
            self._server.close()
        finally:
            if self._server.is_serving():
                self._server.close()
                await self._server.wait_closed()
            self.socket.unlink(missing_ok=True)
            user_info(f"Signal: Server closed! at: {self.__now}")



class SytemMonitor:
    def __init__(self, interval: float = 5.0, cpu_threshold: float = 25.0):
        self.interval = interval
        self.cpu_threshold = cpu_threshold
        self._stop_event = asyncio.Event()
        self.log_handler = LogsHandler()

    def start(self) -> None:

        me = psutil.Process()
        # Start Observer
        user_info("System Monitor running")
        while not self._stop_event.is_set():
            try:
                cpu = me.cpu_percent(None)
                if cpu > 20:
                    mem = me.memory_percent()
                    RAM = me.memory_info().rss / 1024 / 1024
                    threads = me.num_threads()
                    user_info(f"CPU={cpu} Name={me.name()} RAM={RAM: .2f}MB MEM={mem: .2f}% STATUS={me.status()} Threads-Running={threads}")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            except KeyboardInterrupt:
                user_info("Monitor stopped - Keyboard Interupt")
                return
            time.sleep(self.interval)

    def stop(self) -> None:
        if self._stop_event.is_set():
            user_info("System Monitor is currently not running")
            return
        self._stop_event.set()
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
        for task in self.supervisor.tasks:
            task.cancel()
        return await asyncio.gather(*self.supervisor.tasks, return_exceptions=True)

class Supervisor:

    def __init__(self):
        self.__log_handler = LogsHandler()
        self.tasks: set[asyncio.Task] = set()

    async def supervise(self, func, kwargs):
        try:
            start = time.perf_counter()
            result = await func(**kwargs)
            current_task = asyncio.current_task()
            task_name = "Supervisor-"
            if current_task:
                task_name = current_task.get_name()
            user_info(f"Supervisor: Task done - {result} took: {start - time.perf_counter()}s")
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


class Worker:
    def __init__(self):
        self.__signal = Signal(client_cb=self.handler)
        self.__dispatch = Dispatch()
        self.__monitor = SytemMonitor()
        self.__log_handler = LogsHandler()
        self.__downloader = DownloadManager()
        self.__cmd_registry = {
            "STOP-SERVER": {"basename": "Servers Shutdown", "func": self.__signal.stop},
            "STOP-PROCESSES": {"basename": "Processes - Start", "func": self.stop_processes},
            "RESUME": {"basename": "DownloadManager - Resume", "func": self.__downloader.resume},
            "STOP": {"basename": "DownloadManager - Stop", "func": self.__downloader.stop_download},
            "PAUSE": {"basename": "DownloadManager - Pause", "func": self.__downloader.pause},
            "DOWNLOAD": {"basename": "Download Manager - Download", "func": self.__downloader.download_file},
        }

    async def start_processes(self) -> None:
        # Taskgroup takes care of awaits
        asyncio.create_task(self.__signal.start())
        await asyncio.create_task(asyncio.to_thread(self.__monitor.start))

    async def stop_processes(self) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.__dispatch.shutdown())
            self.__monitor.stop()
            tg.create_task(self.__signal.stop())

    async def __parse_message(self, reader: asyncio.StreamReader) -> bytes | None:
        try:
            header = await reader.readexactly(4)

            # unpack from a network stream
            size = struct.unpack("!I", header)[0]
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
                message_str = await asyncio.wait_for(self.__parse_message(reader), timeout=60)
                if message_str is None:
                    writer.write("Reader: could not parse message, check logs for more more info.".encode())
                    await writer.drain()
                    return
                json_message = json.loads(message_str)
                cmd = json_message.get("cmd", None)
                cmd_register = self.__cmd_registry.get(cmd, None)
                if cmd_register is None:
                    writer.write(f"Reader: Could not understand cmd '{cmd}'".encode())
                    await writer.drain()
                    return 
                self.process_cmd(cmd_register, json_message.get("file_args"))
                writer.write(f"Worker: {cmd} Initiated".encode())
                await writer.drain()
        except TimeoutError:
            # client is idle, ignore and proceed to close connection
            pass
        except json.JSONDecodeError:
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-{cmd}",
                error_stack=self.__log_handler.format_error(),
                reason="Json Decode Error"
            )
            writer.write("A Json decode error occurred while decoding message, check logs for more Info.".encode())
            await writer.drain()
        except IncompleteReadError:
            # log error to file
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-{cmd}",
                error_stack=self.__log_handler.format_error(),
                reason="IncompleteReadError"
            )
        except (BrokenPipeError, OSError) as e:
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-{cmd}",
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )
        except Exception as e:
            self.__log_handler.inform_error_logger(
                task_name=f"Handler-{cmd}",
                error_stack=self.__log_handler.format_error(),
                reason=type(e).__name__
            )
        finally:
            writer.close()
            await writer.wait_closed()

    def process_cmd(self, cmd_dict: Mapping[str, str], func_kwargs):
        basename = cmd_dict.get("basename")
        func = cmd_dict.get("func")

        if isinstance(func_kwargs, list):
            self.__dispatch.dispatch_many(basename=basename, func=func, func_kwargs=func_kwargs)
            return
        self.__dispatch.dispatch_one(basename, func, func_kwargs)
        return
