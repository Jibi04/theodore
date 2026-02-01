"""
Docstring for theodore.system_service

SYSTEM SERVICE uses subprocess.Popen spawn a new process to handle concurrency 
between REPL and CLI, and in the FUTURE, API and WEB requests integration.
Through the help of STATE_LOCKS and 'start_new_session' flag. It maintains the CLI as the primary source for starting SERVERS
automatically starts Servers but ignores the start command if server is already running.
Shutting down is initiated through signal 'SIGINT' maintained by 'supervise' which signals the'start-servers' command. In the event shutdown
signal is ignored 'SIGKILL' is called to ensure total shutdown and avoid Zombie Threads.
It's also responsible for loading SENTENCE transformers for intent recognition.

"""

import os
import time
import signal
import subprocess
import threading

from typing import Optional
from theodore.core.paths import SERVER_STATE_FILE
from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.informers import user_info, user_error



class SystemService:
    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self.shutdown_event = threading.Event()
        self.process: Optional[subprocess.Popen] = None

    def get_model(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        return self.model
    
    def start(self):
        self.process = subprocess.Popen(
            self.cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True
        )

        self.err_thread = threading.Thread(
            target=self._stream_reader, 
            args=(self.process.stderr, "ERROR"),
            daemon=True
            )
        
        self.out_thread = threading.Thread(
            target=self._stream_reader, 
            args=(self.process.stdout, "OUT"),
            daemon=True
            )

        self.err_thread.start()
        self.out_thread.start()

    def supervise(self):
        if self.process is None:
            raise RuntimeError("Cannot supervise process not running")
        
        while True:
            if self.shutdown_event.is_set():
                break

            if self.process.poll() is None:
                break

            time.sleep(0.1)

        if self.process.poll() is None and not self.shutdown_event.is_set():
            self._unexpected_shutdown()
        else:
            self._graceful_shutdown()
        user_info("Daemon Operations shutdown.")

    def _unexpected_shutdown(self):
        rc = self.process.returncode

        self._cleanup()
        base_logger.internal(f"Unexpected shutdown cleaning up...\n RC: {rc}")

    def _graceful_shutdown(self, timeout=5):
        if self.process is None:
            return
        
        try:
            os.killpg(self.process.pid, signal.SIGINT)
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            user_error("Wait exceeded! Killing process.")
            os.killpg(self.process.pid, signal.SIGKILL)
        finally:
            self._cleanup()

    def _cleanup(self):
        
        if self.process:
            for stream in (self.process.stderr, self.process.stdout):
                if stream is None:
                    continue
                stream.close()

        for t in (self.err_thread, self.out_thread):
            if t:
                t.join(timeout=0.5)

        SERVER_STATE_FILE.unlink(missing_ok=True)
        self.process = None
        self.err_thread = None
        self.out_thread = None

    def _stream_reader(self, stream, tag):
        for line in iter(stream.readline, ""):
            if self.shutdown_event.is_set():
                break
            self._log_stream(line=line.strip(), tag=tag)

    def _log_stream(self, line: str, tag: str):
        if tag == "OUT":
            base_logger.internal(line)
        else:
            error_logger.internal(line)

    def stop_processes(self):
        self.shutdown_event.set()
    
    def start_processes(self):
        if SERVER_STATE_FILE.exists():
            user_info("Server Already Running.")
            return 
        self.start()
        user_info("Server Started")

    def is_running(self):
        if self.process is None:
            return False
        return True