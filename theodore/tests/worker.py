import asyncio
import psutil
import time
import traceback
from theodore.core.utils import user_info, user_error, base_logger
from theodore.managers.download_manager import DownloadManager
from json import encoder, decoder, JSONDecodeError
from pathlib import Path
from datetime import datetime as dt, UTC

class SystemMonitor:
    def __init__(self):
        self.stop_event = asyncio.Event()

    async def start(self):
        me = psutil.Process()
        while not self.stop_event.is_set():
            CPU_LOAD = me.cpu_percent()
            if CPU_LOAD > 20:
                MEM = me.memory_info().rss/ 1024/ 1024
                STATUS = me.status()
                NUM_THREADS = me.num_threads()
                CORE_NUM = me.cpu_num()
                RUNNING_SINCE = me.create_time()
                PROCESS_NAME = me.name()
                me.memory_info().text()

            


    def stop(self):
        self.stop_event.set()

class Signal:
    def __init__(self, socket: str = "/tmp/theodore/theodore.sock"):
        self.socket = Path(socket)

    async def start_server(self, handler) -> asyncio.AbstractServer:
        if self.socket.exists(): self.socket.unlink()
        self.server = await asyncio.start_unix_server(path=str(self.socket), client_connected_cb=handler)
        return self.server.serve_forever()
    
    async def stop_server(self) -> None:
        self.server.close()
        await self.server.wait_closed()
        self.socket.unlink()


class ErrorHandler:
    async def log_error(self, current_task: asyncio.Task | None = None, exception: Exception | None = None):
        current_task = asyncio.current_task()
        if current_task:
            base_logger.internal(f"""
            "task name": {current_task.get_name()} 
            "error stack": {current_task.get_stack()}
            "coro": {current_task.get_coro()}
                """)
        elif exception:
            base_logger.internal(f"""
            "error type": {type(exception).__name__} 
            "error stack": {traceback.format_exc(exception)}
            "coro": 
                """)


class Dispatcher:
    def __init__(self, signal: Signal):
        self.error_handler = ErrorHandler()
        self.__signal = signal

    async def supervisor(self, func: asyncio._CoroutineLike, func_kwargs):
        try:
            start = time.perf_counter()
            response = await func(**func_kwargs)
            end = time.perf_counter()
            user_info(f"Total time: {end - start}s [{response}]")
        except (ConnectionResetError, BrokenPipeError) as e:
            user_error("Connection Lost cleaning up...")
            self.error_handler.log_error()
        except Exception as e:
            self.error_handler.log_error(exception=e)

    def name_and_schedule(self, basename, index, **kwargs):
        asyncio.create_task(
            self.supervisor(**kwargs),
            name=f"{basename}-{index}-{dt.now(tz=UTC).timestamp()}"
        )
        

    async def parse(self, cmd: str, func, file_args: dict, basename: str):
        i = 1
        match cmd:
            case "SHUTDOWN":
                await self.__signal.stop_server()
            case "DOWNLOAD":
                user_info(f"Starting {len(file_args)} downloads...")
                # Task naming & scheduling
                for u_map in file_args:
                    self.name_and_schedule(
                        basename=basename,
                        index=i,
                        func=func,
                        func_kwargs=u_map,
                    )
                    i += 1
            case _:
                self.name_and_schedule(
                    basename=basename,
                    index=i,
                    func=func,
                    func_kwargs=file_args,
                    )



class Worker:
    def __init__(self):
        self.signal = Signal()

        self.__dispatch = Dispatcher(signal=self.signal)
        self.__download_manager = DownloadManager()
        self.__monitor = SystemMonitor()
        self.__cmd_registry = {
            "DOWNLOAD": {"basename": "DownloadManager", "func": self.__download_manager.download_movie},
        }

    async def signal_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        signal = await reader.read(3000)
        try:
            message = decoder.JSONDecoder().decode(signal.decode())
            cmd = message.get("cmd")

            task_handler = self.__cmd_registry.get(cmd, None)
            if task_handler is None:
                writer.write(f"UNKNOWN Command '{cmd}'".encode())
                await writer.drain()
                return
            
            basename = task_handler.get("basename")
            func = task_handler.get("func")
            file_args = message.get("file_args", {})

            await self.__dispatch.parse(
                    cmd=cmd, 
                    basename=basename, 
                    func=func, 
                    file_args=file_args, 
                )
            if not writer.is_closing():
                writer.write(f"{basename} Job started.")
                await writer.drain()
        except JSONDecodeError:
            writer.write(f"Unable to parse message")
            await writer.drain()
        except (KeyboardInterrupt, asyncio.CancelledError):
            user_info(f"Shutdown Initiated, shutting down...")
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()


