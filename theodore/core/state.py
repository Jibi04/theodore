from pydantic import BaseModel, field_validator

class TheodoreState(BaseModel):
    cpu: float | None = None
    ram: float | None = None
    memory: float | None = None
    status: str | None = None
    threads: int | None = None
    username: str | None = None
    processID: int | float | None = None
    processName: str | None = None


    @field_validator('cpu')
    @classmethod
    def round_cpu(cls, v: float):
        return round(v, 3)
    

    numericProfile: dict | None = None
    generalProfile: dict | None = None

