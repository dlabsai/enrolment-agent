"""Tests for the handle_conversation_turn function in engine.py."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.engine import MessageOut, handle_conversation_turn
from app.core.config import settings
from app.llm.runtime import ModelSettings
from app.models import Conversation, Message, User


@pytest.fixture
def model_settings() -> ModelSettings:
    """Create default model settings for tests."""
    return ModelSettings(
        model=settings.CHATBOT_MODEL,
        temperature=settings.CHATBOT_MODEL_TEMPERATURE,
        max_tokens=settings.CHATBOT_MODEL_MAX_TOKENS,
    )


@pytest.fixture
def mock_chatbot_result():
    """Create a mock result for chatbot agent."""
    mock_result = MagicMock()
    mock_result.output = "Hello! How can I help you today?"
    mock_usage = MagicMock()
    mock_usage.input_tokens = 200
    mock_usage.output_tokens = 100
    mock_result.usage.return_value = mock_usage
    mock_result.all_messages.return_value = []
    return mock_result


def setup_mock_agents(
    mock_create_chatbot: MagicMock,
    mock_create_search: MagicMock,
    mock_get_deps: MagicMock,
    mock_chatbot_result: MagicMock,
) -> AsyncMock:
    """Set up mock agents for tests."""
    # Search agent
    mock_search_result = MagicMock()
    mock_search_result.output = "Search results here"
    mock_search_result.usage.return_value = mock_chatbot_result.usage()
    mock_search_result.all_messages.return_value = []
    mock_search_agent = AsyncMock()
    mock_search_agent.run = AsyncMock(return_value=mock_search_result)
    mock_create_search.return_value = mock_search_agent

    # Chatbot agent
    mock_chatbot_agent = AsyncMock()
    mock_chatbot_agent.run = AsyncMock(return_value=mock_chatbot_result)
    mock_create_chatbot.return_value = mock_chatbot_agent

    # Deps with properly mocked jinja_env
    mock_deps = MagicMock()
    mock_template = MagicMock()
    mock_template.render.return_value = "Mock system prompt template"
    mock_deps.jinja_env.get_template.return_value = mock_template
    mock_get_deps.return_value = mock_deps

    return mock_chatbot_agent


class TestHandleConversationTurnNewConversation:
    """Tests for starting a new conversation."""

    @pytest.mark.asyncio
    async def test_creates_new_conversation(
        self,
        session: AsyncSession,
        test_user: User,
        model_settings: ModelSettings,
        mock_chatbot_result: MagicMock,
    ):
        """Test that handle_conversation_turn creates a new conversation."""
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
            patch(
                "app.chat.title.generate_conversation_title", AsyncMock(return_value="Help request")
            ),
        ):
            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result
            )

            _user_message_id, assistant_message = await handle_conversation_turn(
                conversation_id=None,
                parent_message_id=None,
                user_prompt="Hello, I need help",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            # Verify response
            assert isinstance(assistant_message, MessageOut)
            assert assistant_message.role == "assistant"
            assert assistant_message.content == "Hello! How can I help you today?"
            assert assistant_message.conversation_id is not None

            # Verify conversation was created
            conversation = await session.get(Conversation, assistant_message.conversation_id)
            assert conversation is not None
            assert conversation.title == "Help request"

            # Verify messages were created
            stmt = select(Message).filter_by(conversation_id=conversation.id)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            assert len(messages) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_returns_correct_user_message_id(
        self,
        session: AsyncSession,
        test_user: User,
        model_settings: ModelSettings,
        mock_chatbot_result: MagicMock,
    ):
        """Test that the returned user_message_id is correct."""
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
            patch(
                "app.chat.title.generate_conversation_title",
                AsyncMock(return_value="Test message title"),
            ),
        ):
            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result
            )

            user_message_id, _assistant_message = await handle_conversation_turn(
                conversation_id=None,
                parent_message_id=None,
                user_prompt="Test message",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            # Verify user message exists
            user_message = await session.get(Message, user_message_id)
            assert user_message is not None
            assert user_message.role == "user"
            assert user_message.content == "Test message"


class TestHandleConversationTurnContinuation:
    """Tests for continuing an existing conversation."""

    @pytest.mark.asyncio
    async def test_continues_existing_conversation(
        self,
        session: AsyncSession,
        test_user: User,
        model_settings: ModelSettings,
        mock_chatbot_result: MagicMock,
    ):
        """Test that handle_conversation_turn can continue an existing conversation."""
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
            patch(
                "app.chat.title.generate_conversation_title",
                AsyncMock(return_value="First message title"),
            ),
        ):
            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result
            )

            # First turn: create a new conversation
            _, first_assistant_message = await handle_conversation_turn(
                conversation_id=None,
                parent_message_id=None,
                user_prompt="First message",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            conversation_id = first_assistant_message.conversation_id
            first_assistant_id = first_assistant_message.id

        # Second turn needs fresh mocks
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
        ):
            # Update mock response for second turn
            mock_chatbot_result_2 = MagicMock()
            mock_chatbot_result_2.output = "Here's more help for you!"
            mock_chatbot_result_2.usage.return_value = mock_chatbot_result.usage()
            mock_chatbot_result_2.all_messages.return_value = []

            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result_2
            )

            # Second turn: continue the conversation
            _, second_assistant_message = await handle_conversation_turn(
                conversation_id=conversation_id,
                parent_message_id=first_assistant_id,
                user_prompt="Second message",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            # Verify same conversation
            assert second_assistant_message.conversation_id == conversation_id

            # Verify messages count
            stmt = select(Message).filter_by(conversation_id=conversation_id)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            assert len(messages) == 4  # 2 user + 2 assistant


class TestHandleConversationTurnRegeneration:
    """Tests for message regeneration."""

    @pytest.mark.asyncio
    async def test_regenerates_response(
        self,
        session: AsyncSession,
        test_user: User,
        model_settings: ModelSettings,
        mock_chatbot_result: MagicMock,
    ):
        """Test that handle_conversation_turn can regenerate a response."""
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
            patch(
                "app.chat.title.generate_conversation_title",
                AsyncMock(return_value="Help me title"),
            ),
        ):
            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result
            )

            # First turn: create initial conversation
            user_message_id, first_assistant_message = await handle_conversation_turn(
                conversation_id=None,
                parent_message_id=None,
                user_prompt="Help me",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            conversation_id = first_assistant_message.conversation_id
            original_content = first_assistant_message.content

        # Regeneration needs fresh mocks
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
        ):
            # Update mock for regeneration
            mock_chatbot_result_regen = MagicMock()
            mock_chatbot_result_regen.output = "A better response!"
            mock_chatbot_result_regen.usage.return_value = mock_chatbot_result.usage()
            mock_chatbot_result_regen.all_messages.return_value = []

            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result_regen
            )

            # Regenerate from the user message
            regen_user_id, regenerated_message = await handle_conversation_turn(
                conversation_id=conversation_id,
                parent_message_id=user_message_id,
                user_prompt="Help me",  # Same prompt
                is_regeneration=True,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            # Verify regenerated response is different
            assert regenerated_message.content == "A better response!"
            assert regenerated_message.content != original_content

            # Verify the user_message_id is the same (parent for regeneration)
            assert regen_user_id == user_message_id

            # Verify conversation still has correct number of messages
            # (original user + original assistant + regenerated assistant)
            stmt = select(Message).filter_by(conversation_id=conversation_id)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            assert len(messages) == 3


class TestHandleConversationTurnErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_raises_error_for_nonexistent_conversation(
        self, session: AsyncSession, test_user: User, model_settings: ModelSettings
    ):
        """Test that an error is raised for non-existent conversation."""
        fake_conversation_id = uuid4()
        fake_message_id = uuid4()

        with pytest.raises(ValueError, match=r"Conversation with ID .* not found"):
            await handle_conversation_turn(
                conversation_id=fake_conversation_id,
                parent_message_id=fake_message_id,
                user_prompt="Test",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
            )

    @pytest.mark.asyncio
    async def test_raises_error_for_nonexistent_parent_message(
        self,
        session: AsyncSession,
        test_user: User,
        model_settings: ModelSettings,
        mock_chatbot_result: MagicMock,
    ):
        """Test that an error is raised for non-existent parent message."""
        # First create a conversation
        with (
            patch("app.chat.engine.create_chatbot_agent") as mock_create_chatbot,
            patch("app.chat.engine.create_search_agent") as mock_create_search,
            patch("app.chat.engine.get_deps") as mock_get_deps,
            patch(
                "app.chat.title.generate_conversation_title", AsyncMock(return_value="Test title")
            ),
        ):
            setup_mock_agents(
                mock_create_chatbot, mock_create_search, mock_get_deps, mock_chatbot_result
            )

            _, assistant_message = await handle_conversation_turn(
                conversation_id=None,
                parent_message_id=None,
                user_prompt="Test",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
                enable_guardrails=False,
                is_internal=True,
            )

            conversation_id = assistant_message.conversation_id

        # Now try to continue with a fake parent message
        fake_message_id = uuid4()

        with pytest.raises(ValueError, match=r"Parent message with ID .* not found"):
            await handle_conversation_turn(
                conversation_id=conversation_id,
                parent_message_id=fake_message_id,
                user_prompt="Continue",
                is_regeneration=False,
                chatbot_model_settings=model_settings,
                guardrail_model_settings=model_settings,
                search_model_settings=model_settings,
                user_id=test_user.id,
                session=session,
            )
