from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str


class Citation(BaseModel):
    section_id: str
    title: str
    version: str
    url: str


class ChatResponse(BaseModel):
    status: Literal["answered", "insufficient_context"]
    answer: str
    citations: list[Citation]


class SourceResponse(BaseModel):
    section_id: str
    title: str
    version: str
    content: str
