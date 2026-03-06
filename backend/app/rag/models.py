import logging
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel

from app.rag.json_io import load_models as load_models_
from app.rag.json_io import save_models as save_models_
from app.rag.utils import DATA_DIR

logger = logging.getLogger(__name__)


class BaseRagModel(BaseModel):
    id: str
    title: str
    url: str
    markdown_content: str
    created: datetime | None = None
    updated: datetime | None = None


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


class CatalogCourse(BaseRagModel):
    code: str
    credits: str
    description: str
    prerequisites: str | None = None
    prereq_codes: list[str] = []


class CatalogProgram(BaseRagModel):
    school: str | None = None
    courses: dict[str, list[str]] = {}


_filename_map: dict[type[BaseModel], str] = {
    CatalogCourse: "catalog_courses.json",
    CatalogProgram: "catalog_programs.json",
    WordPressPage: "wordpress_pages.json",
    WordPressPost: "wordpress_posts.json",
    WordPressProgram: "wordpress_programs.json",
}


def _load_mapped_models[T: BaseModel](model_type: type[T]) -> list[T]:
    try:
        return load_models_(DATA_DIR / _filename_map[model_type], model_type=model_type)
    except Exception:
        logger.warning(f"Failed to load models of type {model_type.__name__}", exc_info=True)
        return []


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
    save_models_(DATA_DIR / _filename_map[type(models[0])], models)
