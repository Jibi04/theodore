

from pydantic import BaseModel

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
