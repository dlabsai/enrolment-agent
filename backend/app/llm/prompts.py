from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select

from app.core.app_settings import get_effective_value
from app.core.db import get_session
from app.llm.config import TEMPLATES_DIR
from app.models import ChatbotVersionScope, PromptSetVersion, PromptTemplate


def get_template_globals() -> dict[str, str]:
    """Shared Jinja globals for prompt templates."""
    return {
        "university_name": get_effective_value("university_name", "UNIVERSITY_NAME"),
        "university_website_url": get_effective_value(
            "university_website_url", "UNIVERSITY_WEBSITE_URL"
        ),
        "admissions_phone": get_effective_value(
            "university_admissions_phone", "UNIVERSITY_ADMISSIONS_PHONE"
        ),
        "transcripts_email": get_effective_value(
            "university_transcripts_email", "UNIVERSITY_TRANSCRIPTS_EMAIL"
        ),
        "application_url": get_effective_value(
            "university_application_url", "UNIVERSITY_APPLICATION_URL"
        ),
        "accreditation_url": get_effective_value(
            "university_accreditation_url", "UNIVERSITY_ACCREDITATION_URL"
        ),
    }


def get_template_context() -> dict[str, str]:
    """Shared render context for prompt templates."""
    return get_template_globals()


_ASSISTANT_TEMPLATE_BASES = ("search_agent", "chatbot_agent", "guardrails_agent")
_HELPER_TEMPLATE_BASES: dict[ChatbotVersionScope, str] = {
    ChatbotVersionScope.SUMMARY: "summary_agent",
    ChatbotVersionScope.TITLE: "title_agent",
    ChatbotVersionScope.TITLE_TRANSCRIPT: "title_agent_transcript",
    ChatbotVersionScope.RFI_EXTRACTION: "rfi_extraction_agent",
}


def get_template_bases_for_scope(scope: ChatbotVersionScope) -> list[str]:
    if scope == ChatbotVersionScope.ASSISTANT:
        return list(_ASSISTANT_TEMPLATE_BASES)
    base = _HELPER_TEMPLATE_BASES.get(scope)
    if base is None:
        return []
    return [base]


def get_template_filenames_for_scope(*, scope: ChatbotVersionScope, is_internal: bool) -> list[str]:
    bases = get_template_bases_for_scope(scope)
    suffix = "_internal.j2" if is_internal else ".j2"
    return [f"{base}{suffix}" for base in bases]


class InternalTemplateLoader(BaseLoader):
    """Custom Jinja2 loader that prefers _internal.j2 templates when is_internal is True.

    For a template request like "chatbot_agent.j2", this loader will:
    1. Load "chatbot_agent_internal.j2" if is_internal is True
    2. Otherwise load "chatbot_agent.j2"
    """

    def __init__(self, template_dir: Path, *, is_internal: bool = False) -> None:
        self.template_dir = template_dir
        self.is_internal = is_internal
        self.fallback_loader = FileSystemLoader(template_dir)

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        if self.is_internal and template.endswith(".j2"):
            if template.endswith("_internal.j2"):
                return self.fallback_loader.get_source(environment, template)

            internal_template = template[:-3] + "_internal.j2"
            return self.fallback_loader.get_source(environment, internal_template)

        return self.fallback_loader.get_source(environment, template)

    def list_templates(self) -> list[str]:
        return self.fallback_loader.list_templates()


class DatabaseOverrideLoader(BaseLoader):
    """Custom Jinja2 loader that checks database for template overrides.

    For templates at the root level (e.g., "chatbot_agent.j2"), this loader will:
    1. Load from the deployed/tested DB version for the requested scope
    2. Raise if the template is missing from the DB version

    Templates in subdirectories always use disk.
    """

    def __init__(
        self, template_dir: Path, db_templates: dict[str, str], *, is_internal: bool = False
    ) -> None:
        self.template_dir = template_dir
        self.db_templates = db_templates  # filename -> content
        self.is_internal = is_internal
        self.fallback_loader = InternalTemplateLoader(template_dir, is_internal=is_internal)

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        # Only check DB for root-level .j2 files (no path separator)
        if "/" not in template and template.endswith(".j2"):
            if self.is_internal:
                internal_template = (
                    template
                    if template.endswith("_internal.j2")
                    else template[:-3] + "_internal.j2"
                )
                if internal_template in self.db_templates:
                    content = self.db_templates[internal_template]
                    return content, None, lambda: False
                raise TemplateNotFound(internal_template)

            if template in self.db_templates:
                content = self.db_templates[template]
                return content, None, lambda: False
            raise TemplateNotFound(template)

        return self.fallback_loader.get_source(environment, template)

    def list_templates(self) -> list[str]:
        disk_templates = set(self.fallback_loader.list_templates())
        db_templates = set(self.db_templates.keys())
        return list(disk_templates | db_templates)


def create_jinja_environment(template_dir: Path, *, is_internal: bool = False) -> Environment:
    return Environment(loader=InternalTemplateLoader(template_dir, is_internal=is_internal))


def create_jinja_environment_with_db(
    template_dir: Path, db_templates: dict[str, str], *, is_internal: bool = False
) -> Environment:
    """Create a Jinja environment that checks DB for template overrides."""
    return Environment(
        loader=DatabaseOverrideLoader(template_dir, db_templates, is_internal=is_internal)
    )


# Cached environments for public and internal modes
_jinja_environments: dict[tuple[Path, bool], Environment] = {}


def get_jinja_environment(template_dir: Path, *, is_internal: bool = False) -> Environment:
    """Get a cached Jinja environment for the given template directory and mode."""
    key = (template_dir, is_internal)
    if key not in _jinja_environments:
        _jinja_environments[key] = create_jinja_environment(template_dir, is_internal=is_internal)
    return _jinja_environments[key]


# Cache for deployed templates (version_id -> {filename -> content})
_deployed_templates_cache: dict[UUID | None, dict[str, str]] = {}


async def get_deployed_templates(
    *, is_internal: bool, scope: ChatbotVersionScope
) -> dict[str, str]:
    """Get templates from the currently deployed version for the given scope.

    Returns a dict of {filename: content} for all prompts in the deployed version.
    Returns empty dict if no version is deployed (use disk templates).
    """
    async with get_session() as session:
        # Find deployed version
        stmt = (
            select(PromptSetVersion)
            .where(PromptSetVersion.is_deployed == True)  # noqa: E712
            .where(PromptSetVersion.is_internal == is_internal)
            .where(PromptSetVersion.scope == scope)
            .limit(1)
        )
        result = await session.execute(stmt)
        version = result.scalar_one_or_none()

        if not version:
            return {}

        # Check cache
        if version.id in _deployed_templates_cache:
            return _deployed_templates_cache[version.id]

        # Load prompts
        prompts_stmt = select(PromptTemplate).where(
            PromptTemplate.prompt_set_version_id == version.id
        )
        prompts_result = await session.execute(prompts_stmt)
        prompts = prompts_result.scalars().all()

        templates = {p.filename: p.content for p in prompts}

        # Cache it
        _deployed_templates_cache[version.id] = templates

        return templates


async def get_templates_for_version(version_id: UUID) -> dict[str, str]:
    """Get templates for a specific version.

    Returns a dict of {filename: content} for all prompts in the specified version.
    """
    # Check cache
    if version_id in _deployed_templates_cache:
        return _deployed_templates_cache[version_id]

    async with get_session() as session:
        prompts_stmt = select(PromptTemplate).where(
            PromptTemplate.prompt_set_version_id == version_id
        )
        prompts_result = await session.execute(prompts_stmt)
        prompts = prompts_result.scalars().all()

        templates = {p.filename: p.content for p in prompts}

        # Cache it
        _deployed_templates_cache[version_id] = templates

        return templates


def clear_deployed_templates_cache() -> None:
    """Clear the deployed templates cache. Call after deploying/undeploying versions."""
    _deployed_templates_cache.clear()
    # Also clear the jinja environments cache to force reload
    _jinja_environments.clear()


def resolve_jinja_environment(
    *, is_internal: bool, db_templates: dict[str, str] | None = None
) -> Environment:
    """Return a Jinja environment with optional DB overrides."""
    if db_templates:
        return create_jinja_environment_with_db(
            TEMPLATES_DIR, db_templates, is_internal=is_internal
        )
    return get_jinja_environment(TEMPLATES_DIR, is_internal=is_internal)


async def get_jinja_environment_for_scope(
    *, scope: ChatbotVersionScope, is_internal: bool
) -> Environment:
    """Return a Jinja environment for a scope using deployed templates if present."""
    db_templates = await get_deployed_templates(is_internal=is_internal, scope=scope)
    return resolve_jinja_environment(is_internal=is_internal, db_templates=db_templates or None)
