from pydantic import BaseModel

class TheodoreState(BaseModel):
    cpu: float | None = None
    ram: float | None = None
    memory: float | None = None
    status: str | None = None
    threads: int | None = None
    username: str | None = None
    processID: int | float | None = None
    processName: str | None = None

    numericProfile: dict | None = None
    generalProfile: dict | None = None

