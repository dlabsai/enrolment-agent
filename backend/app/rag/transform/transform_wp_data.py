import logging

from app.rag.json_io import load_models as load_models_
from app.rag.models import WordPressPage, WordPressProgram, save_models
from app.rag.utils import configure_logging
from app.rag.wordpress.config import (
    WP_PROCESSED_PAGES_PATH,
    # WP_PROCESSED_POSTS_PATH,
    WP_PROCESSED_PROGRAMS_PATH,
)
from app.rag.wordpress.models import BreadcrumbItem, ProcessedPost, ProcessedProgram

logger = logging.getLogger(__name__)


def _transform_breadcrumbs(breadcrumbs: list[BreadcrumbItem]) -> list[dict[str, str | int]]:
    return [{"id": item.id, "title": item.title, "url": item.url} for item in breadcrumbs]


def _transform_pages() -> list[WordPressPage]:
    logger.info("Transforming WordPress pages")

    pages = load_models_(WP_PROCESSED_PAGES_PATH, model_type=ProcessedPost)

    rag_pages: list[WordPressPage] = []
    for page in pages:
        # Skip any non-page content
        if page.type != "page":
            continue

        rag_page = WordPressPage(
            id=str(page.id),
            title=page.title,
            url=page.url,
            markdown_content=page.markdown_content,
            created=page.created_date,
            updated=page.updated_date,
            excerpt=page.excerpt,
            breadcrumbs=_transform_breadcrumbs(page.breadcrumbs) if page.breadcrumbs else [],
        )
        rag_pages.append(rag_page)

    logger.info(f"Transformed {len(rag_pages)} pages to RAG format")
    return rag_pages


# def _transform_posts() -> list[WordPressPost]:
#     logger.info("Transforming WordPress posts")

#     posts = load_models_(WP_PROCESSED_POSTS_PATH, model_type=ProcessedPost)

#     wordpress_posts: list[WordPressPost] = []
#     for post in posts:
#         # Skip any non-post content
#         if post.type != "post":
#             continue

#         wordpress_post = WordPressPost(
#             id=str(post.id),
#             title=post.title,
#             url=post.url,
#             markdown_content=post.markdown_content,
#             created=post.created_date,
#             updated=post.updated_date,
#             excerpt=post.excerpt,
#             categories=post.categories,
#             tags=post.tags,
#         )
#         wordpress_posts.append(wordpress_post)

#     logger.info(f"Transformed {len(wordpress_posts)} posts to RAG format")
#     return wordpress_posts


def _transform_programs() -> list[WordPressProgram]:
    logger.info("Transforming WordPress programs")

    programs = load_models_(WP_PROCESSED_PROGRAMS_PATH, model_type=ProcessedProgram)

    rag_programs: list[WordPressProgram] = []
    for program in programs:
        # Skip any non-program content
        if program.type != "program":
            continue

        rag_program = WordPressProgram(
            id=str(program.id),
            title=program.title,
            url=program.url,
            markdown_content=program.markdown_content,
            created=program.created_date,
            updated=program.updated_date,
            excerpt=program.excerpt,
            breadcrumbs=_transform_breadcrumbs(program.breadcrumbs) if program.breadcrumbs else [],
        )
        rag_programs.append(rag_program)

    logger.info(f"Transformed {len(rag_programs)} programs to RAG format")
    return rag_programs


def main() -> None:
    save_models(_transform_pages())
    # save_models(_transform_posts())
    save_models(_transform_programs())


if __name__ == "__main__":
    configure_logging()
    main()
