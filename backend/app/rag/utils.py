import logging
from pathlib import Path

from markdownify import markdownify  # pyright: ignore[reportUnknownVariableType]
from rich.logging import RichHandler

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"


def configure_logging(*, level: int = logging.INFO, rich: bool = True) -> None:
    if rich:
        rich_handler = RichHandler(rich_tracebacks=True, markup=True, show_time=True)
        logging.basicConfig(level=level, format="%(message)s", handlers=[rich_handler])
    else:
        logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")


def html_to_markdown(html_string: str) -> str:
    return markdownify(html_string, heading_style="ATX")
