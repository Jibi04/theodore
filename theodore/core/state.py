from fastapi import FastAPI
from pydantic import BaseModel
from dataclasses import dataclass
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer

from theodore.core.informers import user_info, base_logger, user_error

from theodore.core.paths import TRANSFORMER_MODEL_PATH
from theodore.models.base import AsyncSession, LOCAL_SESSION
from theodore.managers.scheduler import Scheduler, setup_scheduler


class MonitorState(BaseModel):
    cpu: float 
    vm: float 
    disk: float 
    sent: float 
    recv: float 
    ram: float 
    threads: float
    status: str 
    name: str 
    username: str 

@dataclass
class TheodoreState:
    scheduler: Scheduler
    model: SentenceTransformer
    session: AsyncSession


class TheodoreStateManager:
    def __init__(self):
        self._scheduler = Scheduler(setup_scheduler())
        self._session: AsyncSession = LOCAL_SESSION()

        if not TRANSFORMER_MODEL_PATH.exists():
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._model.save(str(TRANSFORMER_MODEL_PATH))
        else:
            self._model = SentenceTransformer(str(TRANSFORMER_MODEL_PATH))

    async def __aenter__(self):
        self._theodore_state = TheodoreState(scheduler=self._scheduler, model=self._model, session=self._session)
        return self._theodore_state

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.update_state()
            return True
        if issubclass(exc_type, (ValueError, ConnectionError)):
            # cleanup and restart state object
            await self._cleanup()
            self.update_state()
            base_logger.internal(f"{exc_type} {exc_val} {exc_tb}\nRestarting session...")
            return True
        await self._cleanup()
        user_error(f"Type: {exc_type} \n Value: {exc_val} \n tb: {exc_tb}")
        raise

    
    def update_state(self):
        self._theodore_state = TheodoreState(scheduler=self._scheduler, model=self._model, session=self._session)
        return

    async def _cleanup(self) -> None:
        import gc

        self._scheduler.stop_jobs()
        await self._session.commit()
        await self._session.close()
        
        del self._theodore_state
        gc.collect()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with TheodoreStateManager() as theodore_state:
        app.state.internals = theodore_state
        yield
    user_info("Theodore Cleanup done. Web Offline.")