import argparse
import logging
import sys

from app.rag.utils import configure_logging
from app.rag.wordpress.config import MIRROR_URL, WEBSITE_URL
from app.rag.wordpress.converter import convert
from app.rag.wordpress.wordpress_client import WordPressClient


def _setup_logging() -> None:
    configure_logging(level=logging.DEBUG)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and process data from WordPress API")

    fetch_group = parser.add_argument_group("Fetch configuration")
    fetch_group.add_argument("--posts", action="store_true", help="Enable posts fetching")
    fetch_group.add_argument(
        "--pages", action="store_true", help="Enable pages fetching (they are disabled by default)"
    )
    fetch_group.add_argument("--programs", action="store_true", help="Enable programs fetching")
    fetch_group.add_argument("--categories", action="store_true", help="Enable categories fetching")
    fetch_group.add_argument("--tags", action="store_true", help="Enable tags fetching")
    fetch_group.add_argument("--media", action="store_true", help="Enable media fetching")

    retry_group = parser.add_argument_group("Retry configuration")
    retry_group.add_argument(
        "--retry-min-wait",
        type=int,
        default=1,
        help="Minimum wait time between retries in seconds (default: 1)",
    )
    retry_group.add_argument(
        "--retry-max-wait",
        type=int,
        default=15,
        help="Maximum wait time between retries in seconds (default: 15)",
    )
    retry_group.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Maximum number of retry attempts (default: None, meaning unlimited retries)",
    )
    retry_group.add_argument(
        "--skip-after",
        type=int,
        default=None,
        help="Skip to next page after this many retry attempts (default: None, meaning never skip)",
    )

    process_group = parser.add_argument_group("Process configuration")
    process_group.add_argument(
        "--process-only", action="store_true", help="Only process existing data without fetching"
    )
    process_group.add_argument(
        "--data-dir", type=str, help="Directory containing WordPress data files"
    )
    process_group.add_argument(
        "--export-files", action="store_true", help="Export RAG content to markdown and HTML files"
    )
    process_group.add_argument(
        "--filter-ids",
        type=lambda s: [int(x) for x in s.split(",") if x.strip().isdigit()],
        help="Comma-delimited list of integer IDs to filter (e.g., --filter-ids 1,2,3)",
    )
    process_group.add_argument(
        "--replace-url",
        action="store_true",
        help=f"Replace WordPress URL ({MIRROR_URL}) with {WEBSITE_URL}",
    )

    sample_group = parser.add_argument_group("Sample configuration")
    sample_group.add_argument(
        "--sample",
        type=int,
        help="Limit the number of items fetched for each type (e.g., --sample 10)",
    )

    return parser.parse_args()


def main(
    *,
    fetch_posts: bool = False,
    fetch_pages: bool = True,
    fetch_programs: bool = True,
    fetch_categories: bool = False,
    fetch_tags: bool = False,
    fetch_media: bool = False,
    retry_min_wait: int = 1,
    retry_max_wait: int = 15,
    max_retries: int | None = None,
    skip_after: int | None = None,
    sample_size: int | None = None,
    process_only: bool = False,
    export_files: bool = False,
    replace_url: bool = False,
    filter_ids: list[int] | None = None,
) -> None:
    """Fetch and process data from WordPress API.

    Args:
        fetch_posts: Enable posts fetching
        fetch_pages: Enable pages fetching (default: True)
        fetch_programs: Enable programs fetching (default: True)
        fetch_categories: Enable categories fetching (default: True)
        fetch_tags: Enable tags fetching (default: True)
        fetch_media: Enable media fetching
        retry_min_wait: Minimum wait time between retries in seconds
        retry_max_wait: Maximum wait time between retries in seconds
        max_retries: Maximum number of retry attempts
        skip_after: Skip to next page after this many retry attempts
        sample_size: Limit the number of items fetched for each type
        process_only: Only process existing data without fetching
        export_files: Export RAG content to markdown and HTML files
        replace_url: Replace WordPress URL with website URL
        filter_ids: List of integer IDs to filter

    """
    logger = logging.getLogger(__name__)

    if process_only:
        convert(export_files=export_files, replace_url=replace_url, filter_ids=filter_ids)
        return

    logger.info("Starting WordPress data fetcher")
    fetcher = WordPressClient(
        fetch_posts=fetch_posts,
        fetch_pages=fetch_pages,
        fetch_programs=fetch_programs,
        fetch_categories=fetch_categories,
        fetch_tags=fetch_tags,
        fetch_media=fetch_media,
        retry_min_wait=retry_min_wait,
        retry_max_wait=retry_max_wait,
        max_retries=max_retries,
        skip_after=skip_after,
        sample_size=sample_size,
    )
    logger.info("Fetching all WordPress data")
    fetcher.fetch_all()
    logger.info("[bold blue]WordPress data fetching complete[/bold blue]")

    convert(export_files=export_files, replace_url=replace_url, filter_ids=filter_ids)


if __name__ == "__main__":
    _setup_logging()
    args = _parse_args()

    if args.process_only:
        main(
            process_only=True,
            export_files=args.export_files,
            replace_url=args.replace_url,
            filter_ids=args.filter_ids,
        )
        sys.exit(0)

    fetch_posts = args.posts
    fetch_pages = args.pages
    fetch_programs = args.programs
    fetch_categories = args.categories
    fetch_tags = args.tags
    fetch_media = args.media

    # If no specific types are selected, enable defaults
    if not any([args.posts, args.pages, args.programs, args.categories, args.tags, args.media]):
        fetch_pages = fetch_programs = True

    main(
        fetch_posts=fetch_posts,
        fetch_pages=fetch_pages,
        fetch_programs=fetch_programs,
        fetch_categories=fetch_categories,
        fetch_tags=fetch_tags,
        fetch_media=fetch_media,
        retry_min_wait=args.retry_min_wait,
        retry_max_wait=args.retry_max_wait,
        max_retries=args.max_retries,
        skip_after=args.skip_after,
        sample_size=args.sample,
        export_files=args.export_files,
        replace_url=args.replace_url,
        filter_ids=args.filter_ids,
    )
