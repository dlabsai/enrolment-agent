"""Tests for PydanticAI agents migration."""

from app.chat.engine import _get_transcript  # pyright: ignore[reportPrivateUsage]
from app.chat.tools import Deps
from app.llm.agents.chatbot import create_chatbot_agent
from app.llm.agents.guardrails import GuardrailsDeps, create_guardrails_agent
from app.llm.agents.search import create_search_agent
from app.llm.providers import get_pydantic_ai_model


class TestGetTranscript:
    """Test transcript generation."""

    def test_empty_messages(self):
        assert _get_transcript([]) == ""

    def test_single_user_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        assert _get_transcript(messages) == "User: Hello"

    def test_single_assistant_message(self):
        messages = [{"role": "assistant", "content": "Hi there"}]
        assert _get_transcript(messages) == "Assistant: Hi there"

    def test_conversation(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        expected = "User: Hello\n\nAssistant: Hi there\n\nUser: How are you?"
        assert _get_transcript(messages) == expected

    def test_limit_to_n_last(self):
        messages = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "Third"},
        ]
        result = _get_transcript(messages, limit_to_n_last=2)
        assert result == "Assistant: Second\n\nUser: Third"


class TestDeps:
    """Test Deps dataclass."""

    def test_deps_creation(self):
        deps = Deps()
        assert deps.is_internal is False

    def test_deps_internal(self):
        deps = Deps(is_internal=True)
        assert deps.is_internal is True


class TestGuardrailsDeps:
    """Test GuardrailsDeps dataclass."""

    def test_guardrails_deps_creation(self):
        deps = GuardrailsDeps(response_to_check="Hello world")
        assert deps.response_to_check == "Hello world"

    def test_guardrails_deps_default(self):
        deps = GuardrailsDeps()
        assert deps.response_to_check == ""


class TestAgentCreation:
    """Test agent factory functions."""

    def test_create_chatbot_agent_without_tools(self):
        """Test chatbot agent creation without tools."""
        agent = create_chatbot_agent("azure:gpt-4o", tools=None)
        assert agent is not None

    def test_create_chatbot_agent_with_tools(self):
        """Test chatbot agent creation with tools."""
        # Use a real tool from the app to avoid type annotation issues
        from app.chat.tools import PUBLIC_TOOLS

        # Test with first available tool (if any)
        if PUBLIC_TOOLS:
            agent = create_chatbot_agent("azure:gpt-4o", tools=[PUBLIC_TOOLS[0]])
            assert agent is not None
        else:
            # If no tools available, just test without tools
            agent = create_chatbot_agent("azure:gpt-4o", tools=None)
            assert agent is not None

    def test_create_guardrails_agent(self):
        """Test guardrails agent creation."""
        agent = create_guardrails_agent("azure:gpt-4o")
        assert agent is not None

    def test_create_guardrails_agent_internal(self):
        """Test guardrails agent creation with is_internal=True."""
        agent = create_guardrails_agent("azure:gpt-4o", is_internal=True)
        assert agent is not None

    def test_create_search_agent(self):
        """Test search agent creation with deps."""
        from app.chat.tools import get_deps

        # Test with public deps (is_internal=False)
        deps = get_deps(is_internal=False)
        agent = create_search_agent("azure:gpt-4o", deps)
        assert agent is not None

    def test_create_search_agent_internal(self):
        """Test search agent creation with internal deps."""
        from app.chat.tools import get_deps

        # Test with internal deps (is_internal=True)
        deps = get_deps(is_internal=True)
        agent = create_search_agent("azure:gpt-4o", deps)
        assert agent is not None


class TestModelConversion:
    """Test the model name conversion function."""

    def test_azure_model_conversion(self):
        """Test Azure model name conversion."""
        result = get_pydantic_ai_model("azure:gpt-4o")
        # Should return an OpenAIChatModel instance
        from pydantic_ai.models.openai import OpenAIChatModel

        assert isinstance(result, OpenAIChatModel)

    def test_openrouter_model_passthrough(self):
        """Test OpenRouter model name passthrough."""
        result = get_pydantic_ai_model("openrouter:openai/gpt-4o")
        assert result == "openrouter:openai/gpt-4o"
