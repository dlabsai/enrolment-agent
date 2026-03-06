import logging
from pathlib import Path

from pydantic import BaseModel

from app.rag.json_io import DEFAULT_INDENT as DEFAULT_INDENT_
from app.rag.json_io import load_models as load_models_
from app.rag.json_io import save_models as save_models_
from app.rag.wordpress.config import (
    WP_CATEGORIES_PATH,
    WP_MEDIA_PATH,
    WP_PAGES_PATH,
    WP_POSTS_PATH,
    WP_PROGRAMS_PATH,
    WP_TAGS_PATH,
)
from app.rag.wordpress.models import Category, Media, Page, Post, Program, Tag

logger = logging.getLogger(__name__)


_model_map_path: dict[type[BaseModel], Path] = {
    Page: WP_PAGES_PATH,
    Category: WP_CATEGORIES_PATH,
    Tag: WP_TAGS_PATH,
    Post: WP_POSTS_PATH,
    Program: WP_PROGRAMS_PATH,
    Media: WP_MEDIA_PATH,
}


def save_models[T: BaseModel](models: list[T], indent: int = DEFAULT_INDENT_) -> None:
    if not models:
        logger.warning("Saving empty model list")

    model_type = type(models[0])
    if model_type not in _model_map_path:
        raise ValueError(f"Unsupported model type: {model_type}")

    save_models_(_model_map_path[model_type], models, indent)


def load_models[T: BaseModel](model_type: type[T]) -> list[T]:
    if model_type not in _model_map_path:
        raise ValueError(f"Unsupported model type: {model_type}")

    return load_models_(_model_map_path[model_type], model_type)
