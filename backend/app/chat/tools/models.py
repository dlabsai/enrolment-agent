from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type DocumentType = Literal["wp_page", "wp_program", "catalog_program", "catalog_course"]


class Document(BaseModel):
    type: DocumentType
    id: int
    title: str
    url: str
    content: str
    updated_at: datetime | None = None


class NotFoundIds(BaseModel):
    not_found_wp_page: list[int] = []
    not_found_wp_program: list[int] = []
    not_found_catalog_program: list[int] = []
    not_found_catalog_course: list[int] = []


class TruncatedDocInfo(BaseModel):
    truncated_docs: list[tuple[DocumentType, int, str]] = []  # (type, id, title)
    omitted_docs: list[tuple[DocumentType, int, str]] = []  # (type, id, title)


class DocumentChunkResult(BaseModel):
    type: DocumentType
    id: int
    title: str
    sequence_number: int
    content: str


class DocumentTitleResult(BaseModel):
    type: DocumentType
    id: int
    title: str
