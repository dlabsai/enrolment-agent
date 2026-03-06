from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from jinja2 import Environment
from pydantic_ai import Embedder
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools.utils import get_azure_embedding_embedder
from app.core.db import get_session
from app.llm.config import TEMPLATES_DIR
from app.llm.prompts import create_jinja_environment_with_db, get_jinja_environment


def _default_tools() -> list[Any]:
    return []


def _default_session_factory() -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    return get_session


@dataclass
class Deps:
    """Dependencies for PydanticAI agents with tools.

    This is the single source of truth for the is_internal configuration.
    Tools, embedding, and database access are injected here for testability.
    """

    is_internal: bool = False
    db_templates: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    chatbot_version_id: UUID | None = None
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = field(
        default_factory=_default_session_factory
    )
    embedder_override: Embedder | None = field(default=None, repr=False)
    _embedder: Embedder | None = field(default=None, repr=False, init=False)
    _tools: list[Any] = field(default_factory=_default_tools, repr=False)
    _jinja_env: Environment | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.embedder_override is not None:
            self._embedder = self.embedder_override

    @property
    def tools(self) -> list[Any]:
        """Get the appropriate tools list based on internal mode."""
        if not self._tools:
            from app.chat.tools import INTERNAL_TOOLS, PUBLIC_TOOLS  # noqa: PLC0415

            self._tools = INTERNAL_TOOLS if self.is_internal else PUBLIC_TOOLS
        return self._tools

    @property
    def embedder(self) -> Embedder:
        """Get the cached Embedder instance used by RAG tools."""
        if self._embedder is None:
            self._embedder = get_azure_embedding_embedder()
        return self._embedder

    @property
    def jinja_env(self) -> Environment:
        """Get the cached Jinja environment for the template directory and mode."""
        if self._jinja_env is None:
            if self.db_templates:
                # Use database templates (no disk fallback for root templates)
                self._jinja_env = create_jinja_environment_with_db(
                    TEMPLATES_DIR, self.db_templates, is_internal=self.is_internal
                )
            else:
                # Use disk templates only
                self._jinja_env = get_jinja_environment(TEMPLATES_DIR, is_internal=self.is_internal)
        return self._jinja_env


def get_deps(
    *,
    is_internal: bool = False,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    embedder: Embedder | None = None,
) -> Deps:
    """Create a Deps instance with all derived properties.

    This is the main entry point for creating dependencies.
    Uses disk templates by default.
    """
    return (
        Deps(is_internal=is_internal, session_factory=session_factory, embedder_override=embedder)
        if session_factory is not None
        else Deps(is_internal=is_internal, embedder_override=embedder)
    )


def get_deps_with_db_templates(
    *,
    is_internal: bool = False,
    db_templates: dict[str, str],
    chatbot_version_id: UUID | None = None,
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    embedder: Embedder | None = None,
) -> Deps:
    """Create a Deps instance with database template overrides.

    Args:
        is_internal: Whether to use internal mode (affects tools and internal template variants)
        db_templates: Dict of {filename: content} for database template overrides
        chatbot_version_id: The ID of the prompt set version being used (for tracking)
        session_factory: Optional session factory override for tests
        embedder: Optional Embedder override for tests

    """
    return (
        Deps(
            is_internal=is_internal,
            db_templates=db_templates,
            chatbot_version_id=chatbot_version_id,
            session_factory=session_factory,
            embedder_override=embedder,
        )
        if session_factory is not None
        else Deps(
            is_internal=is_internal,
            db_templates=db_templates,
            chatbot_version_id=chatbot_version_id,
            embedder_override=embedder,
        )
    )
