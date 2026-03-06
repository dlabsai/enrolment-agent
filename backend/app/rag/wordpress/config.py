import os
from pathlib import Path

from dotenv import load_dotenv

from app.rag.utils import DATA_DIR

_ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(_ENV_PATH)

WP_DATA_DIR = DATA_DIR / "wordpress"
WP_PROCESSED_DIR = WP_DATA_DIR / "processed"
WP_EXPORT_DIR = WP_PROCESSED_DIR / "export"
WP_TEMP_DIR = WP_DATA_DIR / "temp"

WP_PROGRAMS_PATH = WP_DATA_DIR / "programs.json"
WP_PAGES_PATH = WP_DATA_DIR / "pages.json"
WP_CATEGORIES_PATH = WP_DATA_DIR / "categories.json"
WP_TAGS_PATH = WP_DATA_DIR / "tags.json"
WP_POSTS_PATH = WP_DATA_DIR / "posts.json"
WP_MEDIA_PATH = WP_DATA_DIR / "media.json"
WP_PROCESSED_POSTS_PATH = WP_PROCESSED_DIR / "posts_processed.json"
WP_PROCESSED_PAGES_PATH = WP_PROCESSED_DIR / "pages_processed.json"
WP_PROCESSED_PROGRAMS_PATH = WP_PROCESSED_DIR / "programs_processed.json"

WEBSITE_URL = os.getenv("WORDPRESS_WEBSITE_URL", "https://example.com")
MIRROR_URL = os.getenv("WORDPRESS_MIRROR_URL", "https://example.com")
