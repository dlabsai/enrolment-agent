import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship

from app.utils import current_time_utc


def _pascal_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class Base(DeclarativeBase, AsyncAttrs):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, sort_order=-1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=current_time_utc, sort_order=1
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=current_time_utc, onupdate=current_time_utc, sort_order=1
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return _pascal_to_snake(cls.__name__)


class OtelSpan(Base):
    # Standard span identity fields (OTel)
    trace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parent_span_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str | None] = mapped_column(String, nullable=True)

    # Standard span status fields (OTel)
    status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Standard span timing fields (OTel)
    start_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Standard span data fields (OTel)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    events: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    links: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    # Resource + instrumentation scope metadata (OTLP, not span fields)
    resource: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Derived/custom timing fields
    # Normalized timestamp used for analytics ordering/filtering.
    span_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Cached duration computed from span timing.
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)

    # App-specific enrichment
    # LLM model identifier used for the request.
    request_model: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # LLM provider (e.g., openai, azure, openrouter).
    provider_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Provider endpoint host/address.
    server_address: Mapped[str | None] = mapped_column(String, nullable=True)

    # Usage accounting (input tokens).
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Usage accounting (output tokens).
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Estimated cost for the span.
    total_cost: Mapped[float | None] = mapped_column(nullable=True)

    # Request classification flags.
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # Whether the request is an embedding call.
    is_embedding: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Internal vs public request flag.
    is_internal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Conversation/message linkage for analytics.
    conversation_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    # Message linkage for analytics.
    message_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    # End-to-end response time used in analytics.
    total_time: Mapped[float | None] = mapped_column(nullable=True)


class Rating(Enum):
    THUMBS_UP = "thumbsUp"
    THUMBS_DOWN = "thumbsDown"


RatingEnum = ENUM(Rating, name="rating_enum", create_constraint=True, validate_strings=True)


def _user_role_values(enum: type["UserRole"]) -> list[str]:
    return [role.value for role in enum]


class UserRole(str, Enum):
    PUBLIC = "public"
    USER = "user"
    ADMIN = "admin"
    DEV = "dev"


class User(Base):
    email: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=_user_role_values, name="userrole"),
        default=UserRole.USER,
        nullable=False,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="owner", cascade="all, delete"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def is_public_user(self) -> bool:
        return self.role == UserRole.PUBLIC

    def is_internal_user(self) -> bool:
        return self.role == UserRole.USER

    def is_internal_admin_user(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_internal_dev_user(self) -> bool:
        return self.role == UserRole.DEV


class RefreshToken(Base):
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    replaced_by_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class Conversation(Base):
    title: Mapped[str | None] = mapped_column(nullable=False)
    user: Mapped[bool] = mapped_column(default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["ConversationFeedback"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    consent_sync: Mapped["ConversationSync | None"] = relationship(
        back_populates="conversation", uselist=False
    )


class Message(Base):
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("message.id"), nullable=True, index=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    guardrails_blocked: Mapped[bool] = mapped_column(default=False)
    active_child_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("message.id"), nullable=True, index=True
    )

    parent: Mapped["Message | None"] = relationship(
        "Message",
        remote_side="Message.id",
        foreign_keys="Message.parent_id",
        back_populates="children",
    )
    children: Mapped[list["Message"]] = relationship(
        "Message",
        foreign_keys="Message.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    active_child: Mapped["Message | None"] = relationship(
        "Message", remote_side="Message.id", foreign_keys="Message.active_child_id"
    )
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    feedback: Mapped[list["MessageFeedback"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class ConversationFeedback(Base):
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[Rating] = mapped_column(RatingEnum, nullable=False)
    text: Mapped[str | None] = mapped_column()

    conversation: Mapped["Conversation"] = relationship(back_populates="feedback")
    user: Mapped["User"] = relationship()


class MessageFeedback(Base):
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("message.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[Rating] = mapped_column(RatingEnum, nullable=False)
    text: Mapped[str | None] = mapped_column()

    message: Mapped["Message"] = relationship(back_populates="feedback")
    user: Mapped["User"] = relationship()


# TODO: come up with generic WP schema
DocumentTypeEnum = SAEnum(
    "wp_page",
    "wp_post",
    "wp_program",
    "catalog_program",
    "catalog_course",
    name="document_type_enum",
)


class Document(Base):
    type: Mapped[str] = mapped_column(DocumentTypeEnum, nullable=False)
    id_: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    markdown_content: Mapped[str] = mapped_column(String, nullable=False)
    title_embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    document_content_chunks: Mapped[list["DocumentContentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentContentChunk.sequence_number",
    )
    source_created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    def embedding_content(self) -> str:
        return self.title

    __table_args__ = (
        Index(
            "idx_document_title_embedding",
            "title_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"title_embedding": "vector_l2_ops"},
        ),
    )


class DocumentContentChunk(Base):
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    content_embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document: Mapped["Document"] = relationship(back_populates="document_content_chunks")

    def embedding_content(self) -> str:
        return self.content

    __table_args__ = (
        Index(
            "idx_document_content_chunk_content_embedding",
            "content_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"content_embedding": "vector_l2_ops"},
        ),
    )


class ConversationSync(Base):
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    zip: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_message_id: Mapped[str] = mapped_column(String, nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(String, nullable=True)
    program: Mapped[str | None] = mapped_column(String, nullable=True)
    online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    conversation: Mapped["Conversation | None"] = relationship(back_populates="consent_sync")


class AppSettings(Base):
    """Stores optional overrides for app-level settings (single-row)."""

    university_name: Mapped[str | None] = mapped_column(String, nullable=True)
    university_website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    university_admissions_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    university_transcripts_email: Mapped[str | None] = mapped_column(String, nullable=True)
    university_application_url: Mapped[str | None] = mapped_column(String, nullable=True)
    university_accreditation_url: Mapped[str | None] = mapped_column(String, nullable=True)
    guardrails_blocked_message: Mapped[str | None] = mapped_column(Text, nullable=True)


def _chatbot_version_scope_values(enum: type["ChatbotVersionScope"]) -> list[str]:
    return [scope.value for scope in enum]


class ChatbotVersionScope(str, Enum):
    ASSISTANT = "assistant"
    SUMMARY = "summary"
    TITLE = "title"
    TITLE_TRANSCRIPT = "title_transcript"
    RFI_EXTRACTION = "rfi_extraction"


class PromptSetVersion(Base):
    """Represents a specific version of the prompt set configuration."""

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    scope: Mapped[ChatbotVersionScope] = mapped_column(
        SAEnum(
            ChatbotVersionScope,
            values_callable=_chatbot_version_scope_values,
            name="chatbot_version_scope",
        ),
        default=ChatbotVersionScope.ASSISTANT,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deployed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    prompts: Mapped[list["PromptTemplate"]] = relationship(
        back_populates="prompt_set_version", cascade="all, delete-orphan"
    )


class PromptTemplate(Base):
    """Stores prompt template content that overrides disk-based templates."""

    prompt_set_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_set_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    prompt_set_version: Mapped["PromptSetVersion"] = relationship(back_populates="prompts")

    __table_args__ = (
        Index(
            "idx_prompt_template_version_filename", "prompt_set_version_id", "filename", unique=True
        ),
    )
