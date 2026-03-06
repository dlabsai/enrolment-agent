from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RenderedContent(BaseModel):
    rendered: str


class Guid(BaseModel):
    rendered: str


class WordPressBase(BaseModel):
    id: int
    date: datetime
    date_gmt: datetime
    modified: datetime
    modified_gmt: datetime
    slug: str
    status: str
    type: str
    link: str


class Program(WordPressBase):
    guid: Guid
    title: RenderedContent
    content: RenderedContent
    excerpt: RenderedContent
    parent: int = 0


class Post(WordPressBase):
    guid: Guid
    title: RenderedContent
    content: RenderedContent
    excerpt: RenderedContent
    featured_media: int
    categories: list[int] = Field(default_factory=list[int])
    tags: list[int] = Field(default_factory=list[int])


class Page(WordPressBase):
    guid: Guid
    title: RenderedContent
    content: RenderedContent
    excerpt: RenderedContent
    featured_media: int
    parent: int


class Category(BaseModel):
    id: int
    count: int
    description: str
    link: str
    name: str
    slug: str
    taxonomy: str
    parent: int


class Tag(BaseModel):
    id: int
    count: int
    description: str
    link: str
    name: str
    slug: str
    taxonomy: str


class Media(WordPressBase):
    guid: Guid
    title: RenderedContent
    featured_media: int
    media_type: str
    mime_type: str
    source_url: str
    description: RenderedContent
    alt_text: str = ""
    media_details: dict[str, Any] = Field(default_factory=dict)


class BreadcrumbItem(BaseModel):
    id: int
    title: str
    url: str


class ProcessedBase(BaseModel):
    id: int
    title: str
    slug: str
    html_content: str
    markdown_content: str
    type: Literal["post", "page", "program"]
    url: str
    date: datetime
    created_date: datetime
    updated_date: datetime
    excerpt: str | None = None
    breadcrumbs: list[BreadcrumbItem] = Field(default_factory=list[BreadcrumbItem])


class ProcessedPage(ProcessedBase):
    pass


class ProcessedProgram(ProcessedBase):
    pass


class ProcessedPost(ProcessedBase):
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


type Item = Category | Tag | Post | Page | Program

type ProcessedItem = ProcessedPost | ProcessedPage | ProcessedProgram
