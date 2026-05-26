from pydantic import BaseModel
from typing import List, Optional

class QueryRequest(BaseModel):
    text: str

class QueryResponse(BaseModel):
    status: str
    response: str

class ChatRequest(BaseModel):
    session_id: str
    text: str

class ChatResponse(BaseModel):
    status: str
    session_id: str
    response: str
    diff: Optional[List] = None
    architecture_snapshot: Optional[dict] = None
    turn: int

