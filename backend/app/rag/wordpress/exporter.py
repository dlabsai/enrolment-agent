import logging
from collections import defaultdict
from pathlib import Path  # noqa: TC003 # TODO: is it a false positive?

from slugify import slugify

from app.rag.wordpress.config import WP_EXPORT_DIR
from app.rag.wordpress.models import ProcessedItem, ProcessedPost
from app.utils import ensure_dir

logger = logging.getLogger(__name__)

_MD_DIR = WP_EXPORT_DIR / "markdown"
_HTML_DIR = WP_EXPORT_DIR / "html"

ensure_dir(WP_EXPORT_DIR)
ensure_dir(_MD_DIR)
ensure_dir(_HTML_DIR)


def _render_markdown(content: ProcessedItem) -> str:
    md_content = f"# {content.title}\n\n"
    md_content += f"**Type:** {content.type}\n"
    md_content += f"**ID:** {content.id}\n"
    md_content += f"**URL:** {content.url}\n"
    md_content += f"**Date:** {content.date}\n"
    md_content += f"**Created:** {content.created_date}\n"
    md_content += f"**Updated:** {content.updated_date}\n\n"

    if content.excerpt:
        md_content += f"**Excerpt:** {content.excerpt}\n\n"

    if isinstance(content, ProcessedPost):
        if content.categories:
            md_content += f"**Categories:** {', '.join(content.categories)}\n"

        if content.tags:
            md_content += f"**Tags:** {', '.join(content.tags)}\n"

    md_content += "\n---\n\n"
    md_content += content.markdown_content

    return md_content


def _render_html(content: ProcessedItem) -> str:
    html_content = "<!DOCTYPE html>\n<html>\n<head>\n"
    html_content += f"<title>{content.title}</title>\n"
    html_content += '<meta charset="UTF-8">\n'
    html_content += "</head>\n<body>\n"

    html_content += f"<h1>{content.title}</h1>\n"
    html_content += "<div>\n"
    html_content += f"<p><strong>Type:</strong> {content.type}</p>\n"
    html_content += f"<p><strong>ID:</strong> {content.id}</p>\n"
    html_content += f'<p><strong>URL:</strong> <a href="{content.url}">{content.url}</a></p>\n'
    html_content += f"<p><strong>Date:</strong> {content.date}</p>\n"
    html_content += f"<p><strong>Created:</strong> {content.created_date}</p>\n"
    html_content += f"<p><strong>Updated:</strong> {content.updated_date}</p>\n"

    if content.excerpt:
        html_content += f"<p><strong>Excerpt:</strong> {content.excerpt}</p>\n"

    if isinstance(content, ProcessedPost):
        if content.categories:
            html_content += f"<p><strong>Categories:</strong> {', '.join(content.categories)}</p>\n"

        if content.tags:
            html_content += f"<p><strong>Tags:</strong> {', '.join(content.tags)}</p>\n"

    html_content += "</div>\n"
    html_content += f"<div>\n{content.html_content}\n</div>\n"
    html_content += "</body>\n</html>"

    return html_content


def export_rag_files(rag_contents: list[ProcessedItem]) -> None:
    logger.info("[bold green]Exporting RAG content to markdown and HTML files[/bold green]")

    content_types = {content.type for content in rag_contents}
    type_dirs: dict[str, Path] = {}

    for content_type in content_types:
        md_type_dir = _MD_DIR / content_type
        html_type_dir = _HTML_DIR / content_type
        ensure_dir(md_type_dir)
        ensure_dir(html_type_dir)
        type_dirs[f"markdown/{content_type}"] = md_type_dir
        type_dirs[f"html/{content_type}"] = html_type_dir

    type_counts: defaultdict[str, int] = defaultdict(int)

    for content in rag_contents:
        title_slug = slugify(content.title)
        file_base_name = f"{content.id}-{title_slug}"

        md_content = _render_markdown(content)
        md_path = type_dirs[f"markdown/{content.type}"] / f"{file_base_name}.md"
        md_path.write_text(md_content)

        html_content = _render_html(content)
        html_path = type_dirs[f"html/{content.type}"] / f"{file_base_name}.html"
        html_path.write_text(html_content)

        type_counts[content.type] += 1

    total_count = len(rag_contents)
    logger.info(f"Exported {total_count} files to {WP_EXPORT_DIR}")
    logger.info(f"  Markdown files: {_MD_DIR}")
    logger.info(f"  HTML files: {_HTML_DIR}")

    logger.info("Export counts by type:")
    for content_type, count in type_counts.items():
        logger.info(f"  {content_type}: {count}")
