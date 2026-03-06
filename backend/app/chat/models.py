import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.utils import ensure_dir

logger = logging.getLogger(__name__)

DEFAULT_INDENT = 4
RAG_DATA_DIR = Path(__file__).parent.parent / "rag" / "data"


def _dump_models_to_json_bytes[T: BaseModel](
    models: Sequence[T], indent: int = DEFAULT_INDENT
) -> bytes:
    return TypeAdapter(Sequence[T]).dump_json(models, indent=indent)


def _load_models[T: BaseModel](file_path: Path, model_type: type[T]) -> list[T]:
    return TypeAdapter(list[model_type]).validate_json(file_path.read_bytes())


def _save_models[T: BaseModel](
    file_path: Path, models: Sequence[T], indent: int = DEFAULT_INDENT
) -> None:
    ensure_dir(file_path.parent)
    file_path.write_bytes(_dump_models_to_json_bytes(models, indent))


class BaseRagModel(BaseModel):
    id: str
    title: str
    url: str
    markdown_content: str
    created: datetime | None = None
    updated: datetime | None = None


class CatalogCourse(BaseRagModel):
    code: str
    credits: str
    description: str
    prerequisites: str | None = None
    prereq_codes: list[str] = []


class CatalogProgram(BaseRagModel):
    school: str | None = None
    courses: dict[str, list[str]] = {}


class CatalogPage(BaseRagModel):
    pass


class WordPressPage(BaseRagModel):
    excerpt: str | None = None
    breadcrumbs: list[dict[str, str | int]] = []


class WordPressPost(BaseRagModel):
    excerpt: str | None = None
    categories: list[str] = []
    tags: list[str] = []


class WordPressProgram(BaseRagModel):
    excerpt: str | None = None
    breadcrumbs: list[dict[str, str | int]] = []


_filename_map: dict[type[BaseModel], str] = {
    CatalogCourse: "catalog_courses.json",
    CatalogProgram: "catalog_programs.json",
    WordPressPage: "wordpress_pages.json",
    WordPressPost: "wordpress_posts.json",
    WordPressProgram: "wordpress_programs.json",
}


def _load_mapped_models[T: BaseModel](model_type: type[T]) -> list[T]:
    return _load_models(RAG_DATA_DIR / _filename_map[model_type], model_type=model_type)


def load_wordpress_pages() -> list[WordPressPage]:
    return _load_mapped_models(WordPressPage)


def load_wordpress_posts() -> list[WordPressPost]:
    return _load_mapped_models(WordPressPost)


def load_wordpress_programs() -> list[WordPressProgram]:
    return _load_mapped_models(WordPressProgram)


def load_catalog_courses() -> list[CatalogCourse]:
    return _load_mapped_models(CatalogCourse)


def load_catalog_programs() -> list[CatalogProgram]:
    return _load_mapped_models(CatalogProgram)


def save_models(models: Sequence[BaseModel]) -> None:
    _save_models(RAG_DATA_DIR / _filename_map[type(models[0])], models)
