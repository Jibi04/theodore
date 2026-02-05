import json
import queue
import struct
import threading
from rich.table import Table
from dataclasses import dataclass
from typing import Optional, Iterable, Any

from theodore.core.theme import console
from theodore.core.paths import SOCKET_PATH

Queue = queue.Queue()

@dataclass
class InputRequest:
    prompt: str
    response_queue: queue.Queue
    table: Optional[Table] = None

async def send_command(intent: str, file_args: Optional[Iterable] = None) -> Any:

    mail_data = {
        "cmd": intent,
        "file_args": file_args or {}
    }

    message = json.dumps(mail_data).encode()
    header = struct.pack("!I", len(message))

    return await send_signal(header=header, message=message)

async def send_signal(header: bytes, message: bytes) -> str:
        import asyncio
        from asyncio.exceptions import IncompleteReadError
        from theodore.core.informers import LogsHandler

        log_handler = LogsHandler()
        
        try:
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
        except FileNotFoundError:
            raise
        try:
            if writer.is_closing():
                raise
            writer.write(header)
            writer.write(message)
            await writer.drain()

            message = await reader.read(1024)
            # user_info(message.decode())
            return message.decode()
        except (IncompleteReadError, InterruptedError, asyncio.CancelledError):
            log_handler.inform_error_logger(
                task_name="Messenger",
                reason="Connection Interupted",
                error_stack=log_handler.format_error(),
                status="Signal Not sent!"
                )
            raise
        except (BrokenPipeError, OSError):
            log_handler.inform_error_logger(
                task_name="Messenger",
                reason="BrokenPipe",
                error_stack=log_handler.format_error(),
                status="Signal Not sent!"
                )
            raise
        except Exception as e:
            log_handler.inform_error_logger(
                task_name="Messenger",
                reason=type(e).__name__,
                error_stack=log_handler.format_error(),
                status="Signal Not sent!"
                )
            raise
        finally:
            if writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

class CommunicationChannel:
    def __init__(self):
        self.task_queue = queue.Queue()
        self._worker = threading.Thread(target=self._main_worker, daemon=True)

        self._worker.start()
    
    def make_request(self, prompt: str, table: Table | None = None) -> str:
        """Function called by thread, gets response from console returns client response"""
        reply_q = queue.Queue()

        self.task_queue.put(InputRequest(prompt=prompt, response_queue=reply_q, table=table))

        try:
            return reply_q.get()
        except Exception:
            return "q"
    
    def _main_worker(self):
        while True:
            try:
                request = self.task_queue.get()

                if request is None:
                    break

                table = request.table

                if table:
                    console.print(table)
                response = console.input(request.prompt).lower().strip()
                request.response_queue.put(response)
                
            except queue.Empty:
                request.response_queue.put("q")
            finally:
                self.task_queue.task_done()