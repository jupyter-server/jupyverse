from pydantic import BaseModel


class CreateDocumentSession(BaseModel):
    format: str
    type: str
