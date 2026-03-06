"""API routes for prompt template management and prompt set versioning."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_user, require_user_roles
from app.llm.config import TEMPLATES_DIR
from app.llm.prompts import clear_deployed_templates_cache, get_template_filenames_for_scope
from app.models import ChatbotVersionScope, PromptSetVersion, PromptTemplate, User, UserRole

router = APIRouter(
    prefix="/prompts",
    tags=["prompts"],
    dependencies=[Depends(require_user_roles(get_current_user, UserRole.ADMIN, UserRole.DEV))],
)


# ============================================================================
# Schemas
# ============================================================================


class PromptFileOut(BaseModel):
    """Response schema for a prompt file from disk."""

    filename: str
    content: str


class PromptTemplateOut(BaseModel):
    """Response schema for a saved prompt template."""

    id: UUID
    filename: str
    content: str


class PromptTemplateIn(BaseModel):
    """Input schema for creating/updating a prompt template."""

    filename: str
    content: str


class PromptSetVersionBase(BaseModel):
    """Base schema for prompt set version."""

    name: str
    description: str | None = None
    is_internal: bool = False
    scope: ChatbotVersionScope = ChatbotVersionScope.ASSISTANT


class PromptSetVersionCreate(PromptSetVersionBase):
    """Schema for creating a new prompt set version."""

    prompts: list[PromptTemplateIn]


class PromptSetVersionOut(PromptSetVersionBase):
    """Response schema for prompt set version."""

    id: UUID
    version_number: int
    is_deployed: bool
    created_by_id: UUID
    created_by_name: str
    created_at: str
    prompts: list[PromptTemplateOut]


class PromptSetVersionListOut(PromptSetVersionBase):
    """Response schema for prompt set version list (without prompts)."""

    id: UUID
    version_number: int
    is_deployed: bool
    created_by_id: UUID
    created_by_name: str
    created_at: str
    modified_prompt_count: int


class DeployVersionRequest(BaseModel):
    """Request schema for deploying a version."""

    version_id: UUID


class ActiveVersionOut(BaseModel):
    """Response schema for the currently deployed version."""

    id: UUID | None
    version_number: int | None
    name: str | None


# ============================================================================
# Disk Template Endpoints
# ============================================================================


@router.get("/disk-templates", response_model=list[PromptFileOut])
async def list_disk_templates() -> Any:
    """List all .j2 template files from disk (only root level, no subdirs)."""
    templates: list[PromptFileOut] = []

    for file_path in TEMPLATES_DIR.glob("*.j2"):
        if file_path.is_file():
            templates.append(PromptFileOut(filename=file_path.name, content=file_path.read_text()))

    templates.sort(key=lambda t: t.filename)
    return templates


# ============================================================================
# Prompt Set Version Endpoints
# ============================================================================


@router.get("/versions", response_model=list[PromptSetVersionListOut])
async def list_versions(
    session: SessionDep,
    *,
    is_internal: bool | None = None,
    scope: ChatbotVersionScope = ChatbotVersionScope.ASSISTANT,
) -> Any:
    """List all prompt set versions."""
    stmt = (
        select(PromptSetVersion, User.name.label("created_by_name"))
        .join(User, PromptSetVersion.created_by_id == User.id)
        .order_by(desc(PromptSetVersion.version_number))
    )
    if is_internal is not None:
        stmt = stmt.where(PromptSetVersion.is_internal == is_internal)
    stmt = stmt.where(PromptSetVersion.scope == scope)

    result = await session.execute(stmt)
    rows = result.all()

    version_ids = [row.PromptSetVersion.id for row in rows]
    prompts_by_version: dict[UUID, list[PromptTemplate]] = {}
    if version_ids:
        prompts_stmt = select(PromptTemplate).where(
            PromptTemplate.prompt_set_version_id.in_(version_ids)
        )
        prompts_result = await session.execute(prompts_stmt)
        for prompt in prompts_result.scalars().all():
            prompts_by_version.setdefault(prompt.prompt_set_version_id, []).append(prompt)

    disk_templates = {
        file_path.name: file_path.read_text()
        for file_path in TEMPLATES_DIR.glob("*.j2")
        if file_path.is_file()
    }

    versions: list[PromptSetVersionListOut] = []
    for row in rows:
        version = row.PromptSetVersion
        prompts = prompts_by_version.get(version.id, [])
        modified_count = sum(
            1 for prompt in prompts if disk_templates.get(prompt.filename) != prompt.content
        )

        versions.append(
            PromptSetVersionListOut(
                id=version.id,
                version_number=version.version_number,
                name=version.name,
                description=version.description,
                is_internal=version.is_internal,
                scope=version.scope,
                is_deployed=version.is_deployed,
                created_by_id=version.created_by_id,
                created_by_name=row.created_by_name,
                created_at=version.created_at.isoformat(),
                modified_prompt_count=modified_count,
            )
        )

    return versions


@router.get("/versions/deployed", response_model=ActiveVersionOut)
async def get_deployed_version(
    session: SessionDep,
    *,
    is_internal: bool = False,
    scope: ChatbotVersionScope = ChatbotVersionScope.ASSISTANT,
) -> Any:
    """Get the currently deployed prompt set version."""
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
        return ActiveVersionOut(id=None, version_number=None, name=None)

    return ActiveVersionOut(id=version.id, version_number=version.version_number, name=version.name)


@router.get("/versions/{version_id}", response_model=PromptSetVersionOut)
async def get_version(version_id: UUID, session: SessionDep) -> Any:
    """Get a specific prompt set version with its prompts."""
    stmt = (
        select(PromptSetVersion, User.name.label("created_by_name"))
        .join(User, PromptSetVersion.created_by_id == User.id)
        .where(PromptSetVersion.id == version_id)
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    version = row.PromptSetVersion

    # Load prompts
    prompts_stmt = select(PromptTemplate).where(PromptTemplate.prompt_set_version_id == version_id)
    prompts_result = await session.execute(prompts_stmt)
    prompts = prompts_result.scalars().all()

    return PromptSetVersionOut(
        id=version.id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        is_internal=version.is_internal,
        scope=version.scope,
        is_deployed=version.is_deployed,
        created_by_id=version.created_by_id,
        created_by_name=row.created_by_name,
        created_at=version.created_at.isoformat(),
        prompts=[
            PromptTemplateOut(id=p.id, filename=p.filename, content=p.content) for p in prompts
        ],
    )


@router.post("/versions", response_model=PromptSetVersionOut, status_code=status.HTTP_201_CREATED)
async def create_version(
    version_in: PromptSetVersionCreate, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Create a new prompt set version with prompt overrides."""
    disk_templates = [
        file_path.name for file_path in TEMPLATES_DIR.glob("*.j2") if file_path.is_file()
    ]
    expected_templates = set(
        get_template_filenames_for_scope(scope=version_in.scope, is_internal=version_in.is_internal)
    )
    missing_on_disk = sorted(expected_templates - set(disk_templates))
    if missing_on_disk:
        raise HTTPException(
            status_code=400, detail=f"Missing templates on disk: {', '.join(missing_on_disk)}"
        )

    submitted_templates = {prompt.filename for prompt in version_in.prompts}
    if len(submitted_templates) != len(version_in.prompts):
        raise HTTPException(status_code=400, detail="Duplicate templates provided.")
    missing = sorted(expected_templates - submitted_templates)
    extra = sorted(submitted_templates - expected_templates)

    if missing:
        raise HTTPException(
            status_code=400, detail=f"Missing templates for version: {', '.join(missing)}"
        )
    if extra:
        raise HTTPException(
            status_code=400, detail=f"Unexpected templates for version: {', '.join(extra)}"
        )

    # Get the next version number for this scope
    stmt = select(func.coalesce(func.max(PromptSetVersion.version_number), 0)).where(
        PromptSetVersion.is_internal == version_in.is_internal,
        PromptSetVersion.scope == version_in.scope,
    )
    result = await session.execute(stmt)
    max_version = result.scalar()
    next_version = (max_version or 0) + 1

    # Create the version
    version = PromptSetVersion(
        version_number=next_version,
        is_internal=version_in.is_internal,
        scope=version_in.scope,
        name=version_in.name,
        description=version_in.description,
        is_deployed=False,
        created_by_id=current_user.id,
    )
    session.add(version)
    await session.flush()  # Get the version ID

    # Create prompt templates
    for prompt_in in version_in.prompts:
        prompt = PromptTemplate(
            prompt_set_version_id=version.id, filename=prompt_in.filename, content=prompt_in.content
        )
        session.add(prompt)

    await session.commit()
    await session.refresh(version)

    # Load prompts for response
    prompts_stmt = select(PromptTemplate).where(PromptTemplate.prompt_set_version_id == version.id)
    prompts_result = await session.execute(prompts_stmt)
    prompts = prompts_result.scalars().all()

    return PromptSetVersionOut(
        id=version.id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        is_internal=version.is_internal,
        scope=version.scope,
        is_deployed=version.is_deployed,
        created_by_id=version.created_by_id,
        created_by_name=current_user.name,
        created_at=version.created_at.isoformat(),
        prompts=[
            PromptTemplateOut(id=p.id, filename=p.filename, content=p.content) for p in prompts
        ],
    )


@router.post("/versions/{version_id}/deploy", response_model=PromptSetVersionOut)
async def deploy_version(version_id: UUID, session: SessionDep) -> Any:
    """Deploy a specific prompt set version (undeploys any other deployed version)."""
    # Get the version to deploy
    stmt = (
        select(PromptSetVersion, User.name.label("created_by_name"))
        .join(User, PromptSetVersion.created_by_id == User.id)
        .where(PromptSetVersion.id == version_id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    version = row.PromptSetVersion

    # Undeploy all other versions
    undeploy_stmt = (
        select(PromptSetVersion)
        .where(PromptSetVersion.is_deployed == True)  # noqa: E712
        .where(PromptSetVersion.id != version_id)
        .where(PromptSetVersion.is_internal == version.is_internal)
        .where(PromptSetVersion.scope == version.scope)
    )
    undeploy_result = await session.execute(undeploy_stmt)
    for v in undeploy_result.scalars().all():
        v.is_deployed = False

    # Deploy this version
    version.is_deployed = True
    await session.commit()
    await session.refresh(version)

    # Clear template cache to pick up new deployed version
    clear_deployed_templates_cache()

    # Load prompts for response
    prompts_stmt = select(PromptTemplate).where(PromptTemplate.prompt_set_version_id == version.id)
    prompts_result = await session.execute(prompts_stmt)
    prompts = prompts_result.scalars().all()

    return PromptSetVersionOut(
        id=version.id,
        version_number=version.version_number,
        name=version.name,
        description=version.description,
        is_internal=version.is_internal,
        scope=version.scope,
        is_deployed=version.is_deployed,
        created_by_id=version.created_by_id,
        created_by_name=row.created_by_name,
        created_at=version.created_at.isoformat(),
        prompts=[
            PromptTemplateOut(id=p.id, filename=p.filename, content=p.content) for p in prompts
        ],
    )


@router.post("/versions/undeploy", response_model=ActiveVersionOut)
async def undeploy_version(
    session: SessionDep,
    *,
    is_internal: bool = False,
    scope: ChatbotVersionScope = ChatbotVersionScope.ASSISTANT,
) -> Any:
    """Undeploy the currently deployed prompt set version for a scope."""
    stmt = (
        select(PromptSetVersion)
        .where(PromptSetVersion.is_deployed == True)  # noqa: E712
        .where(PromptSetVersion.is_internal == is_internal)
        .where(PromptSetVersion.scope == scope)
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    for version in versions:
        version.is_deployed = False

    if versions:
        await session.commit()
        clear_deployed_templates_cache()

    return ActiveVersionOut(id=None, version_number=None, name=None)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(version_id: UUID, session: SessionDep) -> None:
    """Delete a prompt set version."""
    version = await session.get(PromptSetVersion, version_id)

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    if version.is_deployed:
        raise HTTPException(
            status_code=400, detail="Cannot delete deployed version. Undeploy first."
        )

    await session.delete(version)
    await session.commit()
