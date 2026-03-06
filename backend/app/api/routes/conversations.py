from datetime import datetime
from typing import Annotated, Any, Literal, overload
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Float, String, case, cast, delete, desc, func, literal, or_, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser, SessionDep, get_current_user, require_user_roles
from app.api.schemas import PaginationParams
from app.chat.engine import Feedback, MessageOut
from app.chat.title import build_fallback_title, generate_conversation_title_from_transcript
from app.chat.transcripts import build_transcript
from app.chat.tree_utils import get_current_branch_path, update_active_child_for_branch_switch
from app.core.authz import ensure_owner_or_roles, forbidden, require_roles
from app.models import (
    Conversation,
    ConversationFeedback,
    ConversationSync,
    Message,
    MessageFeedback,
    OtelSpan,
    User,
    UserRole,
)
from app.models import Rating as MessageRating
from app.utils import logger

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    dependencies=[
        Depends(require_user_roles(get_current_user, UserRole.USER, UserRole.ADMIN, UserRole.DEV))
    ],
)

# --- Conversation Management for Internal Users ---

_PREVIEW_MAX_LENGTH = 60


class ConversationSummary(BaseModel):
    """Summary of a conversation for list display."""

    id: UUID
    title: str | None
    summary: str | None = None
    last_message_preview: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    user_name: str | None = None
    user_email: str | None = None


class ConversationMessage(BaseModel):
    """A message within a conversation."""

    id: UUID
    role: str
    content: str
    parent_id: UUID | None
    created_at: datetime


class ConversationMessageFeedback(BaseModel):
    """Current user's feedback for a message (internal app only)."""

    id: UUID
    rating: MessageRating
    text: str | None = None
    user_id: UUID
    user_name: str
    is_current_user: bool
    created_at: datetime
    updated_at: datetime


class ConversationMessageWithFeedback(ConversationMessage):
    feedback: list[ConversationMessageFeedback] = []


class ConversationDetail(BaseModel):
    """Full conversation with all messages."""

    id: UUID
    title: str | None
    summary: str | None = None
    messages: list[ConversationMessageWithFeedback]
    created_at: datetime
    updated_at: datetime


class ConversationListItem(BaseModel):
    """Paginated conversation list row for internal analytics."""

    id: UUID
    title: str | None
    summary: str | None = None
    last_message_preview: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    user_name: str | None = None
    user_email: str | None = None
    total_cost: float | None = None
    feedback_up: int = 0
    feedback_down: int = 0


class ConversationListPage(BaseModel):
    items: list[ConversationListItem]
    total: int


class ConversationUserOption(BaseModel):
    name: str | None = None
    email: str
    platform: Literal["internal", "public"]


class ConversationTitleUpdate(BaseModel):
    title: str


class ConversationTitleOut(BaseModel):
    title: str


class ConversationSearchResult(BaseModel):
    id: UUID
    title: str | None
    snippet: str
    updated_at: datetime


def _format_message_preview(content: str) -> str:
    """Truncate message content for preview."""
    if len(content) > _PREVIEW_MAX_LENGTH:
        return content[:_PREVIEW_MAX_LENGTH] + "..."
    return content


def _build_search_snippet(content: str) -> str:
    if content == "":
        return ""

    return content


def _build_conversation_search_conditions(search: str) -> list[Any]:
    pattern = f"%{search}%"
    message_match = (
        select(Message.id)
        .where(Message.conversation_id == Conversation.id, Message.content.ilike(pattern))
        .exists()
    )

    return [Conversation.title.ilike(pattern), Conversation.summary.ilike(pattern), message_match]


@router.get("", response_model=list[ConversationSummary], response_model_exclude_none=True)
async def list_internal_conversations(session: SessionDep, current_user: CurrentUser) -> Any:
    """List all conversations for the current internal user.

    Returns conversations sorted by most recently updated first.
    """
    # Subquery for last message content
    last_message_subquery = select(
        Message.conversation_id,
        Message.content,
        func.row_number()
        .over(partition_by=Message.conversation_id, order_by=desc(Message.created_at))
        .label("rn"),
    ).subquery()

    # Subquery for latest message time
    latest_message_time_subquery = (
        select(Message.conversation_id, func.max(Message.created_at).label("latest_message_time"))
        .group_by(Message.conversation_id)
        .subquery()
    )

    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
            last_message_subquery.c.content.label("last_message_content"),
            func.coalesce(
                latest_message_time_subquery.c.latest_message_time, Conversation.created_at
            ).label("effective_updated_at"),
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .outerjoin(
            last_message_subquery,
            (Conversation.id == last_message_subquery.c.conversation_id)
            & (last_message_subquery.c.rn == 1),
        )
        .outerjoin(
            latest_message_time_subquery,
            Conversation.id == latest_message_time_subquery.c.conversation_id,
        )
        .where(Conversation.is_public.is_(False))  # Exclude public conversations
    )

    # Apply filters based on role
    # DEV/ADMIN: own conversations only
    # USER: only own conversations
    stmt = stmt.where(Conversation.user_id == current_user.id)

    stmt = stmt.group_by(
        Conversation.id,
        last_message_subquery.c.content,
        latest_message_time_subquery.c.latest_message_time,
    ).order_by(
        desc(
            func.coalesce(
                latest_message_time_subquery.c.latest_message_time, Conversation.created_at
            )
        )
    )

    result = await session.execute(stmt)
    conversations_with_data = result.all()

    logger.debug(f"Found {len(conversations_with_data)} conversations")

    return [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            summary=conversation.summary,
            last_message_preview=(_format_message_preview(last_content) if last_content else None),
            message_count=message_count,
            created_at=conversation.created_at,
            updated_at=effective_updated_at,
            is_public=False,
            user_name=None,
            user_email=None,
        )
        for (
            conversation,
            message_count,
            last_content,
            effective_updated_at,
        ) in conversations_with_data
    ]


@router.get(
    "/search", response_model=list[ConversationSearchResult], response_model_exclude_none=True
)
async def search_internal_conversations(
    session: SessionDep,
    current_user: CurrentUser,
    search: Annotated[str, Query(min_length=1)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Any:
    search_term = search.strip()
    if search_term == "":
        return []

    pattern = f"%{search_term}%"

    latest_message_time_subquery = (
        select(Message.conversation_id, func.max(Message.created_at).label("latest_message_time"))
        .group_by(Message.conversation_id)
        .subquery()
    )

    message_match_subquery = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id, Message.content.ilike(pattern))
        .order_by(desc(Message.created_at))
        .limit(1)
        .scalar_subquery()
    )

    message_match_exists = (
        select(Message.id)
        .where(Message.conversation_id == Conversation.id, Message.content.ilike(pattern))
        .exists()
    )

    effective_updated_at = func.coalesce(
        latest_message_time_subquery.c.latest_message_time, Conversation.created_at
    ).label("effective_updated_at")

    stmt = (
        select(Conversation, message_match_subquery.label("message_match"), effective_updated_at)
        .outerjoin(
            latest_message_time_subquery,
            Conversation.id == latest_message_time_subquery.c.conversation_id,
        )
        .where(Conversation.is_public.is_(False))
        .where(Conversation.user_id == current_user.id)
        .where(
            or_(
                Conversation.title.ilike(pattern),
                Conversation.summary.ilike(pattern),
                message_match_exists,
            )
        )
        .order_by(desc(effective_updated_at))
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    items: list[ConversationSearchResult] = []
    for conversation, message_match, updated_at in rows:
        candidate = (message_match or "").strip()

        summary = (conversation.summary or "").strip()
        title = (conversation.title or "").strip()

        if candidate == "":
            if summary and search_term.lower() in summary.lower():
                candidate = summary
            elif title and search_term.lower() in title.lower():
                candidate = title
            elif summary:
                candidate = summary
            else:
                candidate = title

        snippet = _build_search_snippet(candidate)

        items.append(
            ConversationSearchResult(
                id=conversation.id, title=conversation.title, snippet=snippet, updated_at=updated_at
            )
        )

    return items


@router.get("/users", response_model=list[ConversationUserOption], response_model_exclude_none=True)
async def list_conversation_users(
    session: SessionDep,
    current_user: CurrentUser,
    search: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Any:
    if platform is not None and platform not in {"internal", "public"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    include_public = platform in (None, "public")
    include_internal = platform in (None, "internal")

    if include_public:
        require_roles(current_user, UserRole.DEV, UserRole.ADMIN)

    pattern = f"%{search.strip()}%" if search is not None and search.strip() != "" else None

    statements: list[Any] = []

    if include_internal:
        internal_stmt = (
            select(
                User.name.label("name"),
                User.email.label("email"),
                literal("internal").label("platform"),
            )
            .join(Conversation, Conversation.user_id == User.id)
            .where(Conversation.is_public.is_(False))
        )
        if current_user.role in (UserRole.DEV, UserRole.ADMIN):
            internal_stmt = internal_stmt.where(
                (User.role == UserRole.USER) | (Conversation.user_id == current_user.id)
            )
        else:
            internal_stmt = internal_stmt.where(Conversation.user_id == current_user.id)

        if pattern:
            internal_stmt = internal_stmt.where(
                or_(User.name.ilike(pattern), User.email.ilike(pattern))
            )
        statements.append(internal_stmt)

    if include_public:
        public_name = func.trim(
            func.concat(ConversationSync.first_name, " ", ConversationSync.last_name)
        )
        public_stmt = (
            select(
                public_name.label("name"),
                ConversationSync.email.label("email"),
                literal("public").label("platform"),
            )
            .select_from(Conversation)
            .join(ConversationSync, Conversation.id == ConversationSync.conversation_id)
            .where(Conversation.is_public.is_(True))
            .where(ConversationSync.email.isnot(None))
        )
        if pattern:
            public_stmt = public_stmt.where(
                or_(
                    public_name.ilike(pattern),
                    ConversationSync.first_name.ilike(pattern),
                    ConversationSync.last_name.ilike(pattern),
                    ConversationSync.email.ilike(pattern),
                )
            )
        statements.append(public_stmt)

    if not statements:
        return []

    combined = statements[0]
    for stmt in statements[1:]:
        combined = combined.union_all(stmt)

    subquery = combined.subquery()
    stmt = (
        select(subquery.c.name, subquery.c.email, subquery.c.platform)
        .distinct()
        .order_by(subquery.c.name.asc(), subquery.c.email.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    items: list[ConversationUserOption] = []
    for row in rows:
        name = row.name.strip() if isinstance(row.name, str) else None
        items.append(
            ConversationUserOption(
                name=name if name else None, email=row.email, platform=row.platform
            )
        )

    return items


@router.get("/paginated", response_model=ConversationListPage, response_model_exclude_none=True)
async def list_internal_conversations_paginated(
    session: SessionDep,
    current_user: CurrentUser,
    page_params: Annotated[PaginationParams, Depends()],
    search: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    user_email: Annotated[str | None, Query()] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> Any:
    if platform is not None and platform not in {"internal", "public"}:
        raise HTTPException(status_code=400, detail="Invalid platform")

    if start and end and start > end:
        raise HTTPException(status_code=400, detail="Invalid time range")

    include_public = platform in (None, "public")
    include_internal = platform in (None, "internal")

    if include_public:
        require_roles(current_user, UserRole.DEV, UserRole.ADMIN)

    message_count_subquery = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.count(Message.id).label("message_count"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    last_message_subquery = select(
        Message.conversation_id,
        Message.content,
        func.row_number()
        .over(partition_by=Message.conversation_id, order_by=desc(Message.created_at))
        .label("rn"),
    ).subquery()

    latest_message_time_subquery = (
        select(Message.conversation_id, func.max(Message.created_at).label("latest_message_time"))
        .group_by(Message.conversation_id)
        .subquery()
    )

    def _build_cost_subquery(conversation_ids: list[UUID] | None = None) -> Any:
        trace_context_subquery = (
            select(
                OtelSpan.trace_id.label("trace_id"),
                func.max(cast(OtelSpan.conversation_id, String)).label("conversation_id"),
            )
            .where(OtelSpan.conversation_id.is_not(None))
            .group_by(OtelSpan.trace_id)
            .subquery()
        )

        conversation_id_expr = func.coalesce(
            OtelSpan.conversation_id, cast(trace_context_subquery.c.conversation_id, PGUUID)
        )
        stmt = (
            select(
                conversation_id_expr.label("conversation_id"),
                func.sum(OtelSpan.total_cost).label("total_cost"),
            )
            .outerjoin(
                trace_context_subquery, trace_context_subquery.c.trace_id == OtelSpan.trace_id
            )
            .where(OtelSpan.total_cost.is_not(None))
            .where(conversation_id_expr.is_not(None))
        )
        if conversation_ids:
            stmt = stmt.where(conversation_id_expr.in_(conversation_ids))
        return stmt.group_by(conversation_id_expr).subquery()

    message_feedback_subquery = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.sum(case((MessageFeedback.rating == MessageRating.THUMBS_UP, 1), else_=0)).label(
                "message_feedback_up"
            ),
            func.sum(case((MessageFeedback.rating == MessageRating.THUMBS_DOWN, 1), else_=0)).label(
                "message_feedback_down"
            ),
        )
        .join(MessageFeedback, MessageFeedback.message_id == Message.id)
        .group_by(Message.conversation_id)
        .subquery()
    )

    conversation_feedback_subquery = (
        select(
            ConversationFeedback.conversation_id.label("conversation_id"),
            func.sum(
                case((ConversationFeedback.rating == MessageRating.THUMBS_UP, 1), else_=0)
            ).label("conversation_feedback_up"),
            func.sum(
                case((ConversationFeedback.rating == MessageRating.THUMBS_DOWN, 1), else_=0)
            ).label("conversation_feedback_down"),
        )
        .group_by(ConversationFeedback.conversation_id)
        .subquery()
    )

    message_count = func.coalesce(message_count_subquery.c.message_count, 0).label("message_count")
    feedback_up = (
        func.coalesce(message_feedback_subquery.c.message_feedback_up, 0)
        + func.coalesce(conversation_feedback_subquery.c.conversation_feedback_up, 0)
    ).label("feedback_up")
    feedback_down = (
        func.coalesce(message_feedback_subquery.c.message_feedback_down, 0)
        + func.coalesce(conversation_feedback_subquery.c.conversation_feedback_down, 0)
    ).label("feedback_down")
    effective_updated_at = func.coalesce(
        latest_message_time_subquery.c.latest_message_time, Conversation.created_at
    ).label("effective_updated_at")

    user_name_expr = case(
        (
            Conversation.is_public.is_(True),
            func.concat(ConversationSync.first_name, " ", ConversationSync.last_name),
        ),
        else_=User.name,
    ).label("user_name")
    user_email_expr = case(
        (Conversation.is_public.is_(True), ConversationSync.email), else_=User.email
    ).label("user_email")

    include_cost_in_query = page_params.sort_by == "total_cost"

    base_stmt = (
        select(
            Conversation,
            message_count,
            last_message_subquery.c.content.label("last_message_content"),
            effective_updated_at,
            feedback_up,
            feedback_down,
            user_name_expr,
            user_email_expr,
        )
        .outerjoin(User, Conversation.user_id == User.id)
        .outerjoin(ConversationSync, Conversation.id == ConversationSync.conversation_id)
        .outerjoin(
            message_count_subquery, Conversation.id == message_count_subquery.c.conversation_id
        )
        .outerjoin(
            last_message_subquery,
            (Conversation.id == last_message_subquery.c.conversation_id)
            & (last_message_subquery.c.rn == 1),
        )
        .outerjoin(
            latest_message_time_subquery,
            Conversation.id == latest_message_time_subquery.c.conversation_id,
        )
        .outerjoin(
            message_feedback_subquery,
            Conversation.id == message_feedback_subquery.c.conversation_id,
        )
        .outerjoin(
            conversation_feedback_subquery,
            Conversation.id == conversation_feedback_subquery.c.conversation_id,
        )
    )

    total_cost = cast(literal(None), Float).label("total_cost")  # pyright: ignore[reportUnknownVariableType]
    cost_subquery: Any | None = None
    if include_cost_in_query:
        cost_subquery_local = _build_cost_subquery()
        cost_subquery = cost_subquery_local
        total_cost = cast(cost_subquery_local.c.total_cost, Float).label("total_cost")  # pyright: ignore[reportUnknownVariableType]

    platform_conditions: list[Any] = []
    if include_public:
        platform_conditions.append(Conversation.is_public.is_(True))
    if include_internal:
        internal_condition = Conversation.is_public.is_(False)
        if current_user.role in (UserRole.DEV, UserRole.ADMIN):
            internal_condition = internal_condition & (
                (User.role == UserRole.USER) | (Conversation.user_id == current_user.id)
            )
        else:
            internal_condition = internal_condition & (Conversation.user_id == current_user.id)
        platform_conditions.append(internal_condition)

    base_stmt = base_stmt.where(or_(*platform_conditions))

    time_filters: list[Any] = []
    if start is not None:
        time_filters.append(effective_updated_at >= start)
    if end is not None:
        time_filters.append(effective_updated_at <= end)
    if time_filters:
        base_stmt = base_stmt.where(*time_filters)

    if search is not None and search.strip() != "":
        search_conditions = _build_conversation_search_conditions(search.strip())
        base_stmt = base_stmt.where(or_(*search_conditions))

    if user_email is not None and user_email.strip() != "":
        user_conditions: list[Any] = []
        if include_internal:
            user_conditions.append(User.email == user_email.strip())
        if include_public:
            user_conditions.append(ConversationSync.email == user_email.strip())
        if user_conditions:
            base_stmt = base_stmt.where(or_(*user_conditions))

    stmt = base_stmt.add_columns(total_cost)  # pyright: ignore[reportUnknownArgumentType]
    if include_cost_in_query and cost_subquery is not None:
        stmt = stmt.outerjoin(
            cost_subquery, Conversation.id == cast(cost_subquery.c.conversation_id, PGUUID)
        )

    sort_map = {  # pyright: ignore[reportUnknownVariableType]
        "updated_at": effective_updated_at,
        "created_at": Conversation.created_at,
        "message_count": message_count,
        "total_cost": total_cost,
        "feedback_up": feedback_up,
        "feedback_down": feedback_down,
        "title": Conversation.title,
    }
    sort_column = sort_map.get(page_params.sort_by, effective_updated_at)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    stmt = stmt.order_by(sort_column.desc() if page_params.descending else sort_column.asc())  # pyright: ignore[reportUnknownArgumentType]

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset(page_params.offset)
    if page_params.limit:
        stmt = stmt.limit(page_params.limit)

    result = await session.execute(stmt)
    rows = result.all()

    cost_map: dict[UUID, float | None] = {}
    if not include_cost_in_query and rows:
        conversation_ids = [conversation.id for (conversation, *_) in rows]
        cost_subquery_local = _build_cost_subquery(conversation_ids)
        cost_total = cast(cost_subquery_local.c.total_cost, Float).label("total_cost")  # pyright: ignore[reportUnknownVariableType]
        conversation_id_label = (  # pyright: ignore[reportUnknownVariableType]
            cast(cost_subquery_local.c.conversation_id, PGUUID).label("conversation_id")
        )
        cost_stmt = select(conversation_id_label, cost_total)  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
        cost_rows = (await session.execute(cost_stmt)).mappings().all()  # pyright: ignore[reportUnknownArgumentType]
        cost_map = {row["conversation_id"]: row["total_cost"] for row in cost_rows}

    items = [
        ConversationListItem(
            id=conversation.id,
            title=conversation.title,
            summary=conversation.summary,
            last_message_preview=(_format_message_preview(last_content) if last_content else None),
            message_count=message_count_value,
            created_at=conversation.created_at,
            updated_at=effective_updated_at_value,
            is_public=conversation.is_public,
            user_name=user_name_value,
            user_email=user_email_value,
            total_cost=total_cost_value if include_cost_in_query else cost_map.get(conversation.id),
            feedback_up=feedback_up_value,
            feedback_down=feedback_down_value,
        )
        for (
            conversation,
            message_count_value,
            last_content,
            effective_updated_at_value,
            feedback_up_value,
            feedback_down_value,
            user_name_value,
            user_email_value,
            total_cost_value,
        ) in rows
    ]

    return ConversationListPage(items=items, total=total)


@router.get(
    "/{conversation_id}", response_model=ConversationDetail, response_model_exclude_none=True
)
async def get_internal_conversation(
    conversation_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """Get a specific conversation with all its messages.

    Messages are returned in chronological order following the active branch path.
    Admins can view public conversations as well as internal user conversations.
    """
    # Get conversation
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    _ensure_conversation_access(conversation, current_user)

    # Get all messages for this conversation
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    # Build the active branch path by following active_child_id from root messages
    active_message_ids: set[UUID] = set()

    # Find root messages (no parent)
    root_messages = [m for m in messages if m.parent_id is None]

    # Build a lookup for children by parent_id
    children_by_parent: dict[UUID, list[Message]] = {}
    for msg in messages:
        if msg.parent_id:
            if msg.parent_id not in children_by_parent:
                children_by_parent[msg.parent_id] = []
            children_by_parent[msg.parent_id].append(msg)

    # Follow active child path from each root
    def follow_active_path(message: Message) -> None:
        active_message_ids.add(message.id)
        if message.active_child_id:
            # Find and follow the active child
            children = children_by_parent.get(message.id, [])
            for child in children:
                if child.id == message.active_child_id:
                    follow_active_path(child)
                    return
        # If no active_child_id, follow the first child (for older conversations)
        children = children_by_parent.get(message.id, [])
        if children:
            # Sort by created_at and take the latest
            children_sorted = sorted(children, key=lambda m: m.created_at)
            follow_active_path(children_sorted[-1])

    for root in root_messages:
        follow_active_path(root)

    # Filter to only active branch messages and sort by created_at
    active_messages = sorted(
        [m for m in messages if m.id in active_message_ids], key=lambda m: m.created_at
    )

    # Fetch all feedbacks for the active messages in one query.
    feedback_by_message_id: dict[UUID, list[MessageFeedback]] = {}
    if active_messages:
        active_ids = [m.id for m in active_messages]
        feedback_stmt = (
            select(MessageFeedback)
            .options(joinedload(MessageFeedback.user))
            .where(MessageFeedback.message_id.in_(active_ids))
        )
        feedback_result = await session.execute(feedback_stmt)
        feedback_items = feedback_result.scalars().all()
        for item in feedback_items:
            if item.message_id not in feedback_by_message_id:
                feedback_by_message_id[item.message_id] = []
            feedback_by_message_id[item.message_id].append(item)

    # Get latest message time for updated_at
    latest_message_time = max((m.created_at for m in messages), default=conversation.created_at)

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        summary=conversation.summary,
        messages=[
            ConversationMessageWithFeedback(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                parent_id=msg.parent_id,
                created_at=msg.created_at,
                feedback=[
                    ConversationMessageFeedback(
                        id=fb.id,
                        rating=fb.rating,
                        text=fb.text,
                        user_id=fb.user_id,
                        user_name=fb.user.name,
                        is_current_user=fb.user_id == current_user.id,
                        created_at=fb.created_at,
                        updated_at=fb.updated_at,
                    )
                    for fb in feedback_by_message_id.get(msg.id, [])
                ],
            )
            for msg in active_messages
        ],
        created_at=conversation.created_at,
        updated_at=latest_message_time,
    )


@router.put("/{conversation_id}/title", response_model=ConversationTitleOut)
async def update_internal_conversation_title(
    conversation_id: UUID,
    request: ConversationTitleUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.is_public:
        forbidden()
    ensure_owner_or_roles(conversation.user_id, current_user)

    title = request.title.strip()
    if title == "":
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    conversation.title = title
    await session.commit()
    await session.refresh(conversation)

    return ConversationTitleOut(title=title)


@router.post("/{conversation_id}/title/regenerate", response_model=ConversationTitleOut)
async def regenerate_internal_conversation_title(
    conversation_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.is_public:
        forbidden()
    ensure_owner_or_roles(conversation.user_id, current_user)

    path_ids = await get_current_branch_path(session, conversation_id)
    if not path_ids:
        return ConversationTitleOut(title=conversation.title or "")

    stmt = select(Message).where(Message.id.in_(path_ids))
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    messages_by_id = {message.id: message for message in messages}
    ordered_messages = [
        messages_by_id[message_id] for message_id in path_ids if message_id in messages_by_id
    ]

    if not ordered_messages:
        return ConversationTitleOut(title=conversation.title or "")

    transcript = build_transcript(ordered_messages, is_internal=True)
    fallback = conversation.title or build_fallback_title(ordered_messages[0].content)

    title = await generate_conversation_title_from_transcript(
        transcript, conversation_id=conversation_id, is_internal=True, fallback=fallback
    )

    conversation.title = title
    await session.commit()
    await session.refresh(conversation)

    return ConversationTitleOut(title=title)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_internal_conversation(
    conversation_id: UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    """Delete a conversation and all its messages.

    Only the owner can delete their conversation.
    """
    # Get conversation
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership - only the owner can delete their conversation
    ensure_owner_or_roles(conversation.user_id, current_user)

    # Delete all messages first (cascade should handle this, but being explicit)
    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))

    # Delete conversation
    await session.delete(conversation)
    await session.commit()


# --- Conversation Tree + Message Feedback ---


class FeedbackIn(BaseModel):
    rating: MessageRating
    text: str | None = None


class FeedbackOut(BaseModel):
    id: UUID
    rating: MessageRating
    text: str | None = None
    user_id: UUID
    user_name: str
    is_current_user: bool
    created_at: datetime
    updated_at: datetime


class MessageTreeNodeOut(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    message: MessageOut
    message_tree_nodes: list["MessageTreeNodeOut"] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]


class ConversationTreeOut(BaseModel):
    message_tree_nodes: dict[UUID, MessageTreeNodeOut] = Field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]
    current_branch_path: list[UUID] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    subtree_active_paths: dict[UUID, list[UUID]] = Field(default_factory=dict)  # pyright: ignore[reportUnknownVariableType]


class ConversationDetailOut(BaseModel):
    id: UUID
    title: str | None
    user: bool
    conversation_tree: ConversationTreeOut
    feedback: FeedbackOut | None = None
    created_at: datetime
    updated_at: datetime


async def _get_or_404[T](session: AsyncSession, model: type[T], entity_id: UUID, detail: str) -> T:
    entity = await session.get(model, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=detail)
    return entity


async def _get_conversation_or_404(session: AsyncSession, conversation_id: UUID) -> Conversation:
    return await _get_or_404(session, Conversation, conversation_id, "Conversation not found")


async def _get_message_or_404(session: AsyncSession, message_id: UUID) -> Message:
    return await _get_or_404(session, Message, message_id, "Message not found")


def _ensure_conversation_access(conversation: Conversation, current_user: CurrentUser) -> None:
    if conversation.is_public:
        require_roles(current_user, UserRole.ADMIN, UserRole.DEV)
    else:
        ensure_owner_or_roles(conversation.user_id, current_user, UserRole.ADMIN, UserRole.DEV)


async def _get_message_feedback_or_404(session: AsyncSession, feedback_id: UUID) -> MessageFeedback:
    stmt = (
        select(MessageFeedback)
        .join(User, MessageFeedback.user_id == User.id)
        .where(MessageFeedback.id == feedback_id)
    )
    result = await session.execute(stmt)
    feedback = result.scalar_one_or_none()

    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    return feedback


async def _get_feedback_query[T: ConversationFeedback | MessageFeedback](
    session: AsyncSession, model_class: type[T], entity_id: UUID
) -> list[T]:
    if model_class == ConversationFeedback:
        stmt = (
            select(model_class)
            .options(joinedload(ConversationFeedback.user))
            .where(ConversationFeedback.conversation_id == entity_id)
        )
    else:
        stmt = (
            select(model_class)
            .options(joinedload(MessageFeedback.user))
            .where(MessageFeedback.message_id == entity_id)
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_user_feedback_query[T: ConversationFeedback | MessageFeedback](
    session: AsyncSession, model_class: type[T], entity_id: UUID, user_id: UUID
) -> T | None:
    if model_class == ConversationFeedback:
        stmt = select(model_class).where(
            ConversationFeedback.conversation_id == entity_id,
            ConversationFeedback.user_id == user_id,
        )
    else:
        stmt = select(model_class).where(
            MessageFeedback.message_id == entity_id, MessageFeedback.user_id == user_id
        )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


@overload
async def _create_or_update_feedback(
    session: AsyncSession,
    model_class: type[ConversationFeedback],
    entity_id: UUID,
    feedback_request: FeedbackIn,
    user_id: UUID,
) -> ConversationFeedback: ...


@overload
async def _create_or_update_feedback(
    session: AsyncSession,
    model_class: type[MessageFeedback],
    entity_id: UUID,
    feedback_request: FeedbackIn,
    user_id: UUID,
) -> MessageFeedback: ...


async def _create_or_update_feedback(
    session: AsyncSession,
    model_class: type[ConversationFeedback] | type[MessageFeedback],
    entity_id: UUID,
    feedback_request: FeedbackIn,
    user_id: UUID,
) -> ConversationFeedback | MessageFeedback:
    existing_feedback = await _get_user_feedback_query(session, model_class, entity_id, user_id)

    if existing_feedback:
        existing_feedback.rating = feedback_request.rating
        existing_feedback.text = feedback_request.text
        await session.commit()
        await session.refresh(existing_feedback)
        return existing_feedback

    if model_class == ConversationFeedback:
        feedback = ConversationFeedback(
            conversation_id=entity_id,
            user_id=user_id,
            rating=feedback_request.rating,
            text=feedback_request.text,
        )
    else:
        feedback = MessageFeedback(
            message_id=entity_id,
            user_id=user_id,
            rating=feedback_request.rating,
            text=feedback_request.text,
        )

    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def _build_conversation_tree(
    session: AsyncSession,
    messages: list[Message],
    conversation: Conversation,
    current_user: CurrentUser,
) -> ConversationTreeOut:
    current_branch_path = await get_current_branch_path(session, conversation.id)

    message_outs: dict[UUID, MessageOut] = {}
    for message in messages:
        # Convert feedback to array format for frontend
        feedback_array: list[Feedback] = []
        for feedback in message.feedback:
            feedback_array.append(
                Feedback(
                    id=feedback.id,
                    rating=feedback.rating,
                    text=feedback.text,
                    user_id=feedback.user_id,
                    user_name=feedback.user.name,
                    is_current_user=feedback.user_id == current_user.id,
                    created_at=feedback.created_at,
                    updated_at=feedback.updated_at,
                )
            )

        message_outs[message.id] = MessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            parent_id=message.parent_id,
            feedback=feedback_array,
            created_at=message.created_at,
            guardrails_blocked=message.guardrails_blocked,
        )

    nodes: dict[UUID, MessageTreeNodeOut] = {}
    children_map: dict[UUID, list[UUID]] = {}

    for message_id in message_outs:
        children_map[message_id] = []

    for message_id, message_out in message_outs.items():
        if message_out.parent_id:
            children_map[message_out.parent_id].append(message_id)

    def build_node(message_id: UUID) -> MessageTreeNodeOut:
        message_out = message_outs[message_id]
        children = [build_node(child_id) for child_id in children_map[message_id]]
        return MessageTreeNodeOut(message=message_out, message_tree_nodes=children)

    for message_id, message_out in message_outs.items():
        if message_out.parent_id is None:
            nodes[message_id] = build_node(message_id)

    current_branch_path = await get_current_branch_path(session, conversation.id)

    return ConversationTreeOut(
        message_tree_nodes=nodes, current_branch_path=current_branch_path, subtree_active_paths={}
    )


@router.get("/{conversation_id}/tree", response_model=ConversationDetailOut)
async def get_conversation_tree(
    conversation_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    conversation = await _get_conversation_with_messages(session, conversation_id)
    _ensure_conversation_access(conversation, current_user)
    messages = await _get_messages_with_feedback(session, conversation_id)
    tree = await _build_conversation_tree(session, messages, conversation, current_user)

    # Find current user's feedback from the list
    current_user_feedback = None
    if conversation.feedback:
        for feedback in conversation.feedback:
            if feedback.user_id == current_user.id:
                current_user_feedback = FeedbackOut(
                    id=feedback.id,
                    rating=feedback.rating,
                    text=feedback.text,
                    user_id=feedback.user_id,
                    user_name=feedback.user.name,
                    is_current_user=True,
                    created_at=feedback.created_at,
                    updated_at=feedback.updated_at,
                )
                break

    return ConversationDetailOut(
        id=conversation.id,
        title=conversation.title,
        user=conversation.user,
        conversation_tree=tree,
        feedback=current_user_feedback,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.post("/messages/{message_id}/feedback", response_model=FeedbackOut)
async def create_message_feedback(
    message_id: UUID, feedback_request: FeedbackIn, session: SessionDep, current_user: CurrentUser
) -> Any:
    message = await _get_message_or_404(session, message_id)
    conversation = await _get_conversation_or_404(session, message.conversation_id)
    _ensure_conversation_access(conversation, current_user)
    feedback = await _create_or_update_feedback(
        session, MessageFeedback, message_id, feedback_request, current_user.id
    )

    return FeedbackOut(
        id=feedback.id,
        rating=feedback.rating,
        text=feedback.text,
        user_id=feedback.user_id,
        user_name=feedback.user.name,
        is_current_user=feedback.user_id == current_user.id,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
    )


@router.get("/messages/{message_id}/feedback", response_model=list[FeedbackOut])
async def get_message_feedback(
    message_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    message = await _get_message_or_404(session, message_id)
    conversation = await _get_conversation_or_404(session, message.conversation_id)
    _ensure_conversation_access(conversation, current_user)
    feedback_entries = await _get_feedback_query(session, MessageFeedback, message_id)

    result: list[FeedbackOut] = []
    for feedback in feedback_entries:
        result.append(
            FeedbackOut(
                id=feedback.id,
                rating=feedback.rating,
                text=feedback.text,
                user_id=feedback.user_id,
                user_name=feedback.user.name,
                is_current_user=feedback.user_id == current_user.id,
                created_at=feedback.created_at,
                updated_at=feedback.updated_at,
            )
        )

    return result


@router.delete("/messages/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message_feedback(
    feedback_id: UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    feedback = await _get_message_feedback_or_404(session, feedback_id)
    message = await _get_message_or_404(session, feedback.message_id)
    conversation = await _get_conversation_or_404(session, message.conversation_id)
    _ensure_conversation_access(conversation, current_user)
    ensure_owner_or_roles(feedback.user_id, current_user)
    await session.delete(feedback)
    await session.commit()


class UpdateActiveChildIn(BaseModel):
    active_child_id: str | None


@router.put("/messages/{message_id}/active-child")
async def update_message_active_child(
    message_id: UUID, request: UpdateActiveChildIn, session: SessionDep, current_user: CurrentUser
) -> None:
    message = await _get_message_or_404(session, message_id)
    conversation = await _get_conversation_or_404(session, message.conversation_id)

    if conversation.is_public:
        require_roles(current_user, UserRole.ADMIN, UserRole.DEV)
    else:
        ensure_owner_or_roles(conversation.user_id, current_user, UserRole.ADMIN, UserRole.DEV)

    active_child_id = UUID(request.active_child_id) if request.active_child_id else None
    if active_child_id:
        active_child = await _get_message_or_404(session, active_child_id)
        if active_child.parent_id != message_id:
            raise HTTPException(
                status_code=400, detail="Active child must be a direct child of this message"
            )

    await update_active_child_for_branch_switch(session, message_id, active_child_id)


async def _get_conversation_with_messages(
    session: AsyncSession, conversation_id: UUID
) -> Conversation:
    stmt = (
        select(Conversation)
        .options(joinedload(Conversation.feedback))
        .where(Conversation.id == conversation_id)
    )
    result = await session.execute(stmt)
    conversation = result.unique().scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


async def _get_messages_with_feedback(
    session: AsyncSession, conversation_id: UUID
) -> list[Message]:
    stmt = (
        select(Message)
        .options(joinedload(Message.feedback).joinedload(MessageFeedback.user))
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )

    result = await session.execute(stmt)
    return list(result.scalars().unique().all())
