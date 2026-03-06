import logging
from collections import defaultdict
from typing import Literal

from bs4 import BeautifulSoup

from app.rag.json_io import save_models
from app.rag.wordpress.cleaner import (
    clean_wordpress_content,
    extract_and_clean_excerpt,
    html_to_markdown,
)
from app.rag.wordpress.config import MIRROR_URL, WEBSITE_URL, WP_PROCESSED_DIR
from app.rag.wordpress.exporter import export_rag_files
from app.rag.wordpress.json_io import load_models
from app.rag.wordpress.models import (
    BreadcrumbItem,
    Category,
    Item,
    Page,
    Post,
    ProcessedItem,
    ProcessedPost,
    Program,
    Tag,
)

logger = logging.getLogger(__name__)

_IGNORE_IDS = [
    66298  # https://example.com/academics/undergraduate-degrees-certificates/as-in-accounting-test-2/
]
_IGNORE_TITLES = ["thank you", "confirm subscription", "404 error"]


def _extract_categories(post: Post, categories_map: dict[int, Category]) -> list[str]:
    return [categories_map[cat_id].name for cat_id in post.categories if cat_id in categories_map]


def _extract_tags(post: Post, tags_map: dict[int, Tag]) -> list[str]:
    return [tags_map[tag_id].name for tag_id in post.tags if tag_id in tags_map]


def _extract_breadcrumbs(
    *,
    content_data: Post | Page | Program,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
    max_depth: int = 10,
) -> list[BreadcrumbItem]:
    breadcrumbs: list[BreadcrumbItem] = []
    current_id = getattr(content_data, "parent", None)
    depth = 0
    current_content = content_data

    while current_id and current_id > 0 and depth < max_depth:
        # Try to find the parent in the appropriate map
        parent = None

        # Check the appropriate map first based on the content type
        if isinstance(current_content, Program):
            # For programs, check programs_map first
            if programs_map and current_id in programs_map:
                parent = programs_map[current_id]
            # Then check pages_map if parent not found
            elif pages_map and current_id in pages_map:
                parent = pages_map[current_id]
        # For posts and pages, check pages_map first
        elif pages_map and current_id in pages_map:
            parent = pages_map[current_id]
        # Then check programs_map if parent not found
        elif programs_map and current_id in programs_map:
            parent = programs_map[current_id]

        # If parent not found in either map, break
        if not parent:
            break

        # Create breadcrumb from parent
        breadcrumb = BreadcrumbItem(
            id=parent.id,
            title=BeautifulSoup(parent.title.rendered, "html.parser").get_text(strip=True),
            url=parent.link,
        )
        breadcrumbs.insert(0, breadcrumb)  # Insert at beginning to maintain order

        # Update for next iteration - use parent as the new content_data
        current_id = getattr(parent, "parent", None)
        current_content = parent
        depth += 1

    return breadcrumbs


def _convert_content_base(
    *,
    content_data: Post | Page | Program,
    content_type: Literal["post", "page", "program"],
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
) -> ProcessedPost:
    html_content = clean_wordpress_content(content_data.content.rendered)
    markdown_content = html_to_markdown(html_content)

    excerpt = None
    if hasattr(content_data, "excerpt") and content_data.excerpt and content_data.excerpt.rendered:
        excerpt = extract_and_clean_excerpt(
            content_data.excerpt.rendered, content_data.content.rendered
        )

    breadcrumbs = []

    # Extract breadcrumbs only if the content has a parent and we have maps
    parent_id = getattr(content_data, "parent", None)

    if parent_id and parent_id > 0 and (pages_map or programs_map):
        breadcrumbs = _extract_breadcrumbs(
            content_data=content_data, pages_map=pages_map, programs_map=programs_map
        )

    return ProcessedPost(
        id=content_data.id,
        title=BeautifulSoup(content_data.title.rendered, "html.parser").get_text(strip=True),
        slug=content_data.slug,
        html_content=html_content,
        markdown_content=markdown_content,
        type=content_type,
        url=content_data.link,
        date=content_data.date,
        created_date=content_data.date,
        updated_date=content_data.modified,
        excerpt=excerpt,
        breadcrumbs=breadcrumbs,
    )


def _convert_post(
    *,
    content_data: Post,
    categories_map: dict[int, Category] | None = None,
    tags_map: dict[int, Tag] | None = None,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
) -> ProcessedPost:
    base_content = _convert_content_base(
        content_data=content_data,
        content_type="post",
        pages_map=pages_map,
        programs_map=programs_map,
    )

    categories = []
    if categories_map:
        categories = _extract_categories(post=content_data, categories_map=categories_map)

    tags = []
    if tags_map:
        tags = _extract_tags(post=content_data, tags_map=tags_map)

    return ProcessedPost(
        id=base_content.id,
        title=base_content.title,
        slug=base_content.slug,
        html_content=base_content.html_content,
        markdown_content=base_content.markdown_content,
        type=base_content.type,
        url=base_content.url,
        date=base_content.date,
        created_date=base_content.created_date,
        updated_date=base_content.updated_date,
        excerpt=base_content.excerpt,
        breadcrumbs=base_content.breadcrumbs,
        categories=categories,
        tags=tags,
    )


def _convert_page(
    *,
    content_data: Page,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
) -> ProcessedPost:
    return _convert_content_base(
        content_data=content_data,
        content_type="page",
        pages_map=pages_map,
        programs_map=programs_map,
    )


def _convert_program(
    *,
    content_data: Program,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
) -> ProcessedPost:
    return _convert_content_base(
        content_data=content_data,
        content_type="program",
        pages_map=pages_map,
        programs_map=programs_map,
    )


def _create_id_item_map[T: Item](items: list[T]) -> dict[int, T]:
    return {item.id: item for item in items}


def _replace_url(text: str) -> str:
    return text.replace(MIRROR_URL, WEBSITE_URL)


def _replace_urls_in_content(content: ProcessedItem) -> None:
    content.url = _replace_url(content.url)
    content.html_content = _replace_url(content.html_content)
    content.markdown_content = _replace_url(content.markdown_content)
    for breadcrumb in content.breadcrumbs:
        breadcrumb.url = _replace_url(breadcrumb.url)


def _convert_item(
    *,
    item: Item,
    categories_map: dict[int, Category] | None = None,
    tags_map: dict[int, Tag] | None = None,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
    url_replace: bool = False,
) -> ProcessedItem:
    if isinstance(item, Post):
        content = _convert_post(
            content_data=item,
            categories_map=categories_map,
            tags_map=tags_map,
            pages_map=pages_map,
            programs_map=programs_map,
        )
    elif isinstance(item, Page):
        content = _convert_page(content_data=item, pages_map=pages_map, programs_map=programs_map)
    elif isinstance(item, Program):
        content = _convert_program(
            content_data=item, pages_map=pages_map, programs_map=programs_map
        )
    else:
        raise TypeError(f"Unsupported item type: {type(item)}")

    if url_replace:
        _replace_urls_in_content(content)

    return content


def _convert_items[T: Item](
    *,
    items: list[T],
    categories_map: dict[int, Category] | None = None,
    tags_map: dict[int, Tag] | None = None,
    pages_map: dict[int, Page] | None = None,
    programs_map: dict[int, Program] | None = None,
    replace_url: bool = False,
) -> list[ProcessedItem]:
    return [
        _convert_item(
            item=item,
            categories_map=categories_map,
            tags_map=tags_map,
            pages_map=pages_map,
            programs_map=programs_map,
            url_replace=replace_url,
        )
        for item in items
    ]


def _filter_content[T: Post | Page | Program](
    items: list[T],
    ignore_titles: list[str] | None = None,
    ignore_ids: list[int] | None = None,
    filter_by_ids: list[int] | None = None,
) -> list[T]:
    result = items
    if ignore_titles:
        result = [
            item
            for item in result
            if not any(
                ignore_title in item.title.rendered.lower() for ignore_title in ignore_titles
            )
        ]

    if ignore_ids:
        result = [item for item in result if item.id not in ignore_ids]

    if filter_by_ids:
        result = [item for item in result if item.id in filter_by_ids]

    return result


def _save(rag_contents: list[ProcessedItem]) -> None:
    content_by_type: dict[str, list[ProcessedItem]] = defaultdict(list)
    for content in rag_contents:
        content_by_type[content.type].append(content)

    for content_type, contents in content_by_type.items():
        type_path = WP_PROCESSED_DIR / f"{content_type}s_processed.json"
        save_models(type_path, contents)


def convert(
    *, export_files: bool = False, replace_url: bool = False, filter_ids: list[int] | None = None
) -> list[ProcessedItem]:
    logger.info("[bold green]Processing WordPress content into RAG-ready format[/bold green]")

    # all_posts_list = load_models(Post)
    all_pages_list = load_models(Page)
    all_programs_list = load_models(Program)
    # all_categories_list = load_models(Category)
    # all_tags_list = load_models(Tag)

    # categories_map = _create_id_item_map(all_categories_list)
    # tags_map = _create_id_item_map(all_tags_list)
    global_pages_map = _create_id_item_map(all_pages_list)
    global_programs_map = _create_id_item_map(all_programs_list)

    # posts_to_convert = all_posts_list
    pages_to_convert = all_pages_list
    programs_to_convert = all_programs_list

    if _IGNORE_TITLES:
        logger.info(f"Ignoring titles containing: {_IGNORE_TITLES}")
    if _IGNORE_IDS:
        logger.info(f"Ignoring IDs: {_IGNORE_IDS}")
    if filter_ids:
        logger.info(f"Filtering content to be converted by IDs: {filter_ids}")

    # posts_to_convert = _filter_content(all_posts_list, _IGNORE_TITLES, _IGNORE_IDS, filter_ids)
    pages_to_convert = _filter_content(all_pages_list, _IGNORE_TITLES, _IGNORE_IDS, filter_ids)
    programs_to_convert = _filter_content(
        all_programs_list, _IGNORE_TITLES, _IGNORE_IDS, filter_ids
    )

    contents: list[ProcessedItem] = []
    contents.extend(
        _convert_items(
            items=pages_to_convert,
            pages_map=global_pages_map,
            programs_map=global_programs_map,
            replace_url=replace_url,
        )
    )
    # contents.extend(
    #     _convert_items(
    #         items=posts_to_convert,
    #         categories_map=categories_map,
    #         tags_map=tags_map,
    #         pages_map=global_pages_map,
    #         programs_map=global_programs_map,
    #         replace_url=replace_url,
    #     )
    # )
    contents.extend(
        _convert_items(
            items=programs_to_convert,
            pages_map=global_pages_map,
            programs_map=global_programs_map,
            replace_url=replace_url,
        )
    )

    _save(contents)

    content_types: defaultdict[str, int] = defaultdict(int)
    for content in contents:
        content_types[content.type] += 1
    logger.info("Content type counts:")
    for content_type, count in content_types.items():
        logger.info(f"  {content_type}: {count}")

    logger.info(f"Output saved to {WP_PROCESSED_DIR}")

    if export_files:
        export_rag_files(contents)

    logger.info("[bold blue]WordPress content processing complete[/bold blue]")

    return contents
