import queue
import threading
from theodore.core.theme import console
from dataclasses import dataclass
from typing import Any

Queue = queue.Queue()

@dataclass
class InputRequest:
    prompt: str
    response_queue: queue.Queue
    table: Any = None

class CommunicationChannel:
    def __init__(self):
        self.task_queue = queue.Queue()
        self._worker = threading.Thread(target=self._main_worker, daemon=True)

        self._worker.start()
    
    def make_request(self, prompt: str, table = None):
        """Function called by thread, gets response from console returns client response"""
        reply_q = queue.Queue()

        self.task_queue.put(InputRequest(prompt=prompt, response_queue=reply_q, table=table))

        return reply_q.get(timeout=60.0)
    
    def _main_worker(self):
        while True:
            request = self.task_queue.get()
            table = request.table

            if table:
                console.print(table)
            response = console.input(request.prompt).lower().strip()
            request.response_queue.put(response)
            
            self.task_queue.task_done()