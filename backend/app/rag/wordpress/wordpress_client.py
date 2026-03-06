import logging
from http import HTTPStatus
from typing import Any

import requests
import tenacity
from pydantic import BaseModel

# TODO: make sure raw WP data is saved as-is
from app.rag.json_io import save_models as save_json_data
from app.rag.wordpress.config import MIRROR_URL, WP_DATA_DIR
from app.rag.wordpress.json_io import save_models
from app.rag.wordpress.models import Category, Media, Page, Post, Program, Tag

logger = logging.getLogger(__name__)

_TIMEOUT = 300
_PER_PAGE = 100


class WordPressClient:
    def __init__(
        self,
        base_url: str = MIRROR_URL,
        *,
        retry_min_wait: int = 1,
        retry_max_wait: int = 3,
        max_retries: int | None = None,
        skip_after: int | None = None,
        sample_size: int | None = None,
        fetch_posts: bool = True,
        fetch_pages: bool = True,
        fetch_programs: bool = True,
        fetch_categories: bool = True,
        fetch_tags: bool = True,
        fetch_media: bool = True,
    ) -> None:
        self.base_url = base_url
        self.api_url = f"{base_url}/wp-json/wp/v2"

        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.max_retries = max_retries
        self.skip_after = skip_after

        self.sample_size = sample_size

        self.fetch_posts_enabled = fetch_posts
        self.fetch_pages_enabled = fetch_pages
        self.fetch_programs_enabled = fetch_programs
        self.fetch_categories_enabled = fetch_categories
        self.fetch_tags_enabled = fetch_tags
        self.fetch_media_enabled = fetch_media

    def _get_retry_decorator(self) -> tenacity.Retrying:
        stop_strategy = (
            tenacity.stop_after_attempt(self.max_retries)
            if self.max_retries is not None
            else tenacity.stop_never
        )

        wait_strategy = tenacity.wait_random(min=self.retry_min_wait, max=self.retry_max_wait)

        return tenacity.Retrying(
            retry=tenacity.retry_if_exception_type(requests.exceptions.HTTPError),
            stop=stop_strategy,
            wait=wait_strategy,
            before_sleep=lambda retry_state: logger.info(
                f"Retrying after error (attempt {retry_state.attempt_number}, "
                f"waiting "
                f"{retry_state.next_action.sleep if retry_state.next_action else 'unknown'} "
                f"seconds)..."
            ),
        )

    def _make_request(
        self, endpoint: str, page: int = 1, per_page: int = _PER_PAGE, entity_name: str = ""
    ) -> tuple[requests.Response, list[dict[str, Any]]] | None:
        url = f"{self.api_url}/{endpoint}/?per_page={per_page}&page={page}"
        logger.info(f"Making request to: {url}")

        retry_decorator = self._get_retry_decorator()
        attempt_count = 0

        def _request_with_retry() -> requests.Response:
            nonlocal attempt_count
            attempt_count += 1

            if self.skip_after is not None and attempt_count > self.skip_after:
                logger.warning(
                    f"Skipping {entity_name} page {page} after {attempt_count - 1} retry attempts"
                )
                raise ValueError("Skip page due to too many retry attempts")

            response = requests.get(url, timeout=_TIMEOUT, allow_redirects=True)

            if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
                self._log_error_content(response)
                response.raise_for_status()

            return response

        try:
            response = retry_decorator(lambda: _request_with_retry())
        except ValueError as e:
            if str(e) == "Skip page due to too many retry attempts":
                logger.info(f"Skipped {entity_name} page {page} after multiple retry attempts")
                return None
            raise
        except tenacity.RetryError:
            logger.exception(f"Max retries exceeded for URL: {url}")
            return None

        logger.info(f"Response status code: {response.status_code}")

        if response.status_code == HTTPStatus.OK:
            try:
                data = response.json()
                logger.info(f"Received {len(data)} {entity_name} on page {page}")
                self._save_raw_data(f"{entity_name}_raw_page{page}.json", data)
            except Exception:
                logger.exception(f"Failed to parse JSON for {entity_name} page {page}")
                return None
            else:
                return response, data

        logger.error(f"Failed to fetch {entity_name} page {page}: {response.status_code}")
        self._log_error_content(response)
        return None

    def _log_error_content(self, response: requests.Response) -> None:
        try:
            error_content = response.text[:1000]
            logger.error(f"Error response content: {error_content}")

            if "memory size" in error_content and "exhausted" in error_content:
                logger.warning("Server memory exhaustion detected, this may be a temporary issue")
        except Exception:
            logger.exception("Failed to extract error content from response")

    def _save_raw_data(self, filename: str, data: Any) -> None:
        path = WP_DATA_DIR / filename
        save_json_data(path, data)

    def _parse_items[T: BaseModel](
        self, data: list[dict[str, Any]], model: type[T], entity_name: str, page: int
    ) -> list[T]:
        parsed_items: list[T] = []

        for i, item in enumerate(data):
            try:
                logger.debug(f"Parsing {entity_name} {i + 1}/{len(data)} on page {page}")
                parsed_item = model.model_validate(item)
                parsed_items.append(parsed_item)

                # Log title for certain entity types
                # Check if it's a model with a title field
                if isinstance(parsed_item, (Post, Page, Program, Media)):
                    try:
                        logger.debug(
                            f"Successfully parsed {entity_name}: {parsed_item.title.rendered}"
                        )
                    except Exception:
                        # Log errors in title logging at debug level
                        logger.debug(f"Could not log title for {entity_name} item {i + 1}")
            except Exception:
                logger.exception(
                    f"Failed to parse {entity_name} {i + 1}/{len(data)} on page {page}"
                )

        return parsed_items

    def _fetch_entity[M: BaseModel](
        self, endpoint: str, model: type[M], entity_name: str, per_page: int = _PER_PAGE
    ) -> list[M]:
        logger.info(f"Fetching {entity_name}")
        items: list[M] = []
        page = 1
        total_pages = 1

        # Adjust per_page for sample mode
        if self.sample_size is not None:
            per_page = min(per_page, self.sample_size)
            logger.info(f"Sample mode enabled: Limiting to {self.sample_size} {entity_name}")

        while page <= total_pages:
            # Check if sample size reached
            if self.sample_size is not None and len(items) >= self.sample_size:
                logger.info(f"Sample size limit reached ({self.sample_size} items)")
                break

            logger.info(f"Fetching {entity_name} page {page}")

            response_data = self._make_request(
                endpoint=endpoint, page=page, per_page=per_page, entity_name=entity_name
            )

            if not response_data:
                logger.warning(
                    f"Failed to fetch {entity_name} page {page}, continuing with next page"
                )
                page += 1
                continue

            response, data = response_data

            # Calculate total pages on first page
            if page == 1:
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                logger.info(f"Total {entity_name} pages: {total_pages}")

                # Adjust total pages for sample mode
                if self.sample_size is not None:
                    estimated_pages = (self.sample_size + per_page - 1) // per_page
                    total_pages = min(total_pages, estimated_pages)
                    logger.info(f"Sample mode: Limiting to approximately {total_pages} pages")

            parsed_items = self._parse_items(data, model, entity_name, page)

            # Limit items by remaining sample size
            if self.sample_size is not None:
                remaining = self.sample_size - len(items)
                if remaining < len(parsed_items):
                    parsed_items = parsed_items[:remaining]

            items.extend(parsed_items)
            page += 1

        # Final sample size enforcement
        if self.sample_size is not None and len(items) > self.sample_size:
            items = items[: self.sample_size]

        logger.info(f"Successfully fetched {len(items)} {entity_name}")
        if items:
            save_models(items)
        return items

    def _fetch_programs(self) -> list[Program]:
        return self._fetch_entity(
            endpoint="programs", model=Program, entity_name="programs", per_page=_PER_PAGE
        )

    def _fetch_posts(self) -> list[Post]:
        return self._fetch_entity(
            endpoint="posts", model=Post, entity_name="posts", per_page=_PER_PAGE
        )

    def _fetch_pages(self) -> list[Page]:
        return self._fetch_entity(
            endpoint="pages", model=Page, entity_name="pages", per_page=_PER_PAGE
        )

    def _fetch_categories(self) -> list[Category]:
        return self._fetch_entity(
            endpoint="categories", model=Category, entity_name="categories", per_page=_PER_PAGE
        )

    def _fetch_tags(self) -> list[Tag]:
        return self._fetch_entity(
            endpoint="tags", model=Tag, entity_name="tags", per_page=_PER_PAGE
        )

    def _fetch_media(self) -> list[Media]:
        return self._fetch_entity(
            endpoint="media", model=Media, entity_name="media", per_page=_PER_PAGE
        )

    def fetch_all(self) -> None:
        """Fetch all enabled entity types."""
        if self.fetch_programs_enabled:
            self._fetch_programs()
        else:
            logger.info("Programs fetching is disabled")

        if self.fetch_posts_enabled:
            self._fetch_posts()
        else:
            logger.info("Posts fetching is disabled")

        if self.fetch_pages_enabled:
            self._fetch_pages()
        else:
            logger.info("Pages fetching is disabled")

        if self.fetch_categories_enabled:
            self._fetch_categories()
        else:
            logger.info("Categories fetching is disabled")

        if self.fetch_tags_enabled:
            self._fetch_tags()
        else:
            logger.info("Tags fetching is disabled")

        if self.fetch_media_enabled:
            self._fetch_media()
        else:
            logger.info("Media fetching is disabled")
