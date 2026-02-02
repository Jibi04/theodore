import json
import queue
import struct
import threading
from rich.table import Table
from dataclasses import dataclass
from typing import Optional, Iterable

from theodore.core.theme import console
from theodore.core.lazy import get_worker


Queue = queue.Queue()

@dataclass
class InputRequest:
    prompt: str
    response_queue: queue.Queue
    table: Optional[Table] = None

async def send_command(intent: str, file_args: Optional[Iterable] = None) -> None:

    mail_data = {
        "cmd": intent,
        "file_args": file_args or {}
    }

    message = json.dumps(mail_data).encode()
    header = struct.pack("!I", len(message))

    return await get_worker().send_signal(header=header, message=message)

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