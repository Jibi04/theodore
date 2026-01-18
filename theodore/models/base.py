from contextlib import asynccontextmanager
from sqlalchemy import MetaData, Table
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv

ENV_PATH = find_dotenv()
load_dotenv(ENV_PATH)

def create_engine():
    db_name = os.getenv('DB_NAME')
    BASE_DIR = Path(__file__).parent.parent.resolve()
    DB_PATH = Path(f"{BASE_DIR}/data/{db_name}")

    DB = f"sqlite+aiosqlite:///{DB_PATH}"
    # engine = create_async_engine(DB, echo=True) 

    engine = create_async_engine(DB, echo=False)
    return engine, DB

engine, DB = create_engine()
LOCAL_SESSION = async_sessionmaker(bind=engine)
meta = MetaData()

@asynccontextmanager
async def get_async_session():
    session: AsyncSession = LOCAL_SESSION()
    try:
        yield session
        await session.commit()

    except Exception:
        raise
    finally:
        await session.close()
        pass


async def drop_table(table: Table):
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: table.drop(sync_conn))
    print(f'{table.name} table dropped')


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)
