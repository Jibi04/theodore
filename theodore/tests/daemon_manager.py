import asyncio
import json
import psutil
from pathlib import Path
from pydantic import BaseModel, ConfigDict
from theodore.core.utils import user_info, user_error
from theodore.managers.download_manager import DownloadManager


class ValidateSignal(BaseModel):
    message: str


class ValidateFileArgs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    filename: str
    filepath: str | Path | None
    downloads_instance: DownloadManager


class Signal:

    async def start(self, path: Path, signal_handler) -> None:
        _path = Path(path)
        if _path.exists(): _path.unlink()

        try:
            server = await asyncio.start_unix_server(signal_handler, path=path)
            return server
        except KeyboardInterrupt:
            self.stop(server, socket=path)
    
    async def stop(self, server: asyncio.AbstractServer, socket: Path) -> None:
        try:
            server.close()
            await server.wait_closed()
            _path = Path(socket)
            if _path.exists():
                _path.unlink()
            user_info('Server closed')
            return
        except:
            raise


class SystemMonitor:
    def __init__(self, interval: float = 5.0, cpu_threshold: float = 25.0):
        self.interval = interval
        self.cpu_threshold = cpu_threshold
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        me = psutil.Process()
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
                user_error("Monitor stopped - Keyboard Interupt")
                return
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._stop_event.set()
        user_info("System Monitor Stopped")
        


class Worker:

    def __init__(self, workers = 4):
        self.downloads_instance: DownloadManager = DownloadManager()
        self.signal_instance: Signal = Signal()
        self.server: asyncio.AbstractServer = None
        self.server_socket: str = "theodore.sock"
        self.system_monitor: SystemMonitor = SystemMonitor()
        self._workers = asyncio.Semaphore(workers)



        self.registry = {
            "PAUSE": self.handle_pause,
            "DOWNLOAD": self.downloads_instance.download_movie,
            "RESUME": self.handle_resume,
            "CANCEL": self.handle_cancel,
            "SHUTDOWN": self.stop_processes
        }


    def start_processes(self):
        tasks = [
            self.start_server(),
            self.start_monitor()
        ]
        return tasks


    async def stop_processes(self):
        processes_to_stop = self.stop_monitor()
        processes_to_stop.append(self.stop_server())

        # If Iterable is empty asyncio.gather returns empty List obj
        return await asyncio.gather(*processes_to_stop, return_exceptions=True)


    async def start_monitor(self):
        # if not self.system_monitor._stop_event.is_set():
        #     user_info("System Monitor already running")
        #     return
        return await self.system_monitor.start()
    

    async def stop_monitor(self):
        if self.system_monitor._stop_event.is_set():
            user_info("System Monitor currently not running")
            return
        self.system_monitor.stop()

    
    async def start_server(self) -> None:
        if self.server is not None:
            user_error('Server already running')
            return
        self.server = await self.signal_instance.start(path=self.server_socket, signal_handler=self.handle_signal)
        user_info(f"Starting Server")
        return await self.server.serve_forever()
    

    async def stop_server(self) -> None:
        if self.server is None:
            user_error('Server currently not running')
            return
        await self.signal_instance.stop(self.server, self.server_socket)


    async def handle_signal(self, reader, writer) -> None:
        message = await reader.read(3024)

        try:
            message: dict = message.decode()
            json_obj = json.decoder.JSONDecoder().decode(message)

            cmd = json_obj.get("cmd")

            if cmd not in self.registry:
                writer.write(f"Unknown Command {cmd}".encode())
                await writer.drain()
                return
            
            func = self.registry.get(cmd)
            file_args = json_obj.get("file_args")

            match cmd:
                case "SHUTDOWN":
                    await func()
                    writer.write(f"{cmd} Processed.".encode())
                    await writer.drain()
                case "DOWNLOAD":
                    async with asyncio.TaskGroup() as tg:
                        for url_map in file_args:
                            tg.create_task(func(**url_map))
                case _:
                    response = await func(**file_args)
                    writer.write(f"{cmd} resposne. {response}".encode())
                    await writer.drain()
            print(f"{cmd} Starting...")
        except json.JSONDecodeError:
            writer.write(f"could not process Json object".encode())
            await writer.drain()
        except Exception as e:
            return f"""
                An exception caught by signal handler
                {type(e).__name__}: {e.with_traceback()}
            """
        finally:
            writer.close()
            await writer.wait_closed()

        
    async def send_signal(self, message: str):
        if not Path(self.server_socket).exists():
            return f"Cannot Send signal, Server not running {self}"
        
        reader, writer = await asyncio.open_unix_connection(self.server_socket)
        try:
            msg_obj = ValidateSignal(message=message)


            message = msg_obj.message.encode()
            writer.write(message)
            await writer.drain()

            if not writer.is_closing():
                response = await reader.read(3000)
                return response.decode()
        except Exception as e:
            return f"""
                An exception caught by send signal 
                {type(e).__name__}: {e.with_traceback()}
            """
        finally:
            writer.close()
            await writer.wait_closed()

    
    async def handle_downloads(self, **kwargs):
        async with self._workers:
            await self.downloads_instance.download_movie(**kwargs)


    async def handle_pause(self, filename: str, filepath: Path = None) -> None:
        async with self._workers:
            file_obj = self.validate_file_args(filename, filepath, self.downloads_instance)
            _filename = file_obj.filename

            event: asyncio.Event = self.downloads_instance.active_events.get(_filename, None)
            if event is None:
                user_error(f"Cannot pause {_filename}, Not downloading")
                return
            
            event.clear()
            user_info(f"{_filename} Paused.")


    async def handle_resume(self, filename: str, filepath: Path) -> None:
        async with self._workers:
            file_obj = self.validate_file_args(filename, filepath, self.downloads_instance)
            _filename = file_obj.filename

            event: asyncio.Event = self.downloads_instance.active_events.get(_filename, None)
            if event is None:
                user_error(f"Cannot resume {_filename}, Not downloading")
                return
            
            event.set()
            user_info(f"{_filename} Resumed")


    async def handle_cancel(self, filename: str, filepath: Path) -> None:
        async with self._workers:
            file_obj = self.validate_file_args(filename, filepath, self.downloads_instance)
            _filename = file_obj.filename

            if _filename not in self.downloads_instance.active_events:
                user_error(f"Cannot cancel {_filename}, Not downloading")
                return
            
            await self.downloads_instance.stop_download(filename=_filename, filepath=file_obj.filepath)
            user_info(f"{_filename} Cancelled")

    def validate_file_args(self, filename: str, filepath: Path | str, downloads_instance: DownloadManager):
        try:
            file_obj = ValidateFileArgs(filename=filename, filepath=filepath, downloads_instance=downloads_instance)
            return file_obj
        except Exception:
            raise

    def __str__(self):
        return f"Server: {self.server} Socket: {self.server_socket}"
