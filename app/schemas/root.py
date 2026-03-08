from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    version: str
    description: str
    docs: str
    health: str
