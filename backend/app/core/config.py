from typing import Annotated, Any, Literal

from pydantic import AnyUrl, BeforeValidator, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    if isinstance(v, list):
        return [str(item) for item in v]  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
    if isinstance(v, str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_ignore_empty=True, extra="ignore")

    API_STR: str = "/api"
    FRONTEND_HOST: str = "http://localhost:9000"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []

    @computed_field
    @property
    def ALL_CORS_ORIGINS(self) -> list[str]:  # noqa: N802
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str = "va"
    POSTGRES_SERVER: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> MultiHostUrl:  # noqa: N802
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    MODELS: str = "azure:gpt-5.2-chat,openrouter:*"

    UNIVERSITY_NAME: str = "Demo University"
    UNIVERSITY_WEBSITE_URL: str = "https://example.com"
    UNIVERSITY_ADMISSIONS_PHONE: str = "111.222.3333"
    UNIVERSITY_TRANSCRIPTS_EMAIL: str = "transcripts@example.com"
    UNIVERSITY_APPLICATION_URL: str = "https://apply.example.com/?utm_source=VA"
    UNIVERSITY_ACCREDITATION_URL: str = "https://example.com/about/accreditation-and-recognition/"

    # Azure OpenAI Resource 1 settings
    AZURE_API_KEY_1: str = ""
    AZURE_API_BASE_1: str = ""
    AZURE_API_VERSION_1: str = "2024-12-01-preview"

    # Azure OpenAI Resource 2 settings
    AZURE_API_KEY_2: str = ""
    AZURE_API_BASE_2: str = ""
    AZURE_API_VERSION_2: str = "2025-04-01-preview"

    # Azure OpenAI Resource 3 settings
    AZURE_API_KEY_3: str = ""
    AZURE_API_BASE_3: str = ""
    AZURE_API_VERSION_3: str = "2025-04-01-preview"

    # Model to Azure resource mapping (e.g., "gpt-5.1:2,gpt-4.1:3")
    # Models not listed default to resource 1
    AZURE_MODEL_RESOURCE_MAP: str = ""

    # OpenAI settings
    OPENAI_API_KEY: str = ""

    # OpenRouter settings
    OPENROUTER_API_KEY: str = ""

    # LLM Model Settings
    # Model for chatbot responses
    CHATBOT_MODEL: str = "azure:gpt-5.2-chat"
    CHATBOT_MODEL_TEMPERATURE: float | None = None
    CHATBOT_MODEL_MAX_TOKENS: int | None = None

    # Model for extractors (variables)
    EXTRACTOR_MODEL: str = "azure:gpt-5.2-chat"
    EXTRACTOR_MODEL_TEMPERATURE: float | None = None
    EXTRACTOR_MODEL_MAX_TOKENS: int | None = None

    # Model for guardrails
    GUARDRAIL_MODEL: str = "azure:gpt-5.2-chat"
    GUARDRAIL_MODEL_TEMPERATURE: float | None = None
    GUARDRAIL_MODEL_MAX_TOKENS: int | None = None

    # Guardrails configuration
    ENABLE_GUARDRAILS: bool = True
    MAX_GUARDRAILS_RETRIES: int = 2
    GUARDRAILS_BLOCKED_MESSAGE: str = ""

    # Model for search agent
    SEARCH_AGENT_MODEL: str = "azure:gpt-5.2-chat"
    SEARCH_AGENT_MODEL_TEMPERATURE: float | None = None
    SEARCH_AGENT_MODEL_MAX_TOKENS: int | None = None

    # Model for evaluation/judge
    EVALUATION_MODEL: str = "azure:gpt-5.2-chat"
    EVALUATION_MODEL_TEMPERATURE: float | None = None
    EVALUATION_MODEL_MAX_TOKENS: int | None = None

    # Model for summarization
    SUMMARIZER_MODEL: str = "azure:gpt-5.2-chat"

    # HTTP request timeout for LLM calls (seconds)
    LLM_REQUEST_TIMEOUT: float = 5 * 60.0  # 5 minutes

    USER_REGISTRATION_TOKEN: str | None = None
    ADMIN_REGISTRATION_TOKEN: str | None = None
    DEV_REGISTRATION_TOKEN: str | None = None
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_COOKIE_NAME: str = "va_refresh_token"  # noqa: S105
    REFRESH_TOKEN_COOKIE_PATH: str | None = None
    REFRESH_TOKEN_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"  # noqa: S105
    REFRESH_TOKEN_COOKIE_SECURE: bool | None = None

    SCHEDULER: bool = False

    def model_post_init(self, __context: Any, /) -> None:
        if not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set")

        if self.REFRESH_TOKEN_COOKIE_PATH is None:
            object.__setattr__(self, "REFRESH_TOKEN_COOKIE_PATH", f"{self.API_STR}/auth")

        if self.REFRESH_TOKEN_COOKIE_SECURE is None:
            object.__setattr__(self, "REFRESH_TOKEN_COOKIE_SECURE", self.ENVIRONMENT != "local")

        if not self.GUARDRAILS_BLOCKED_MESSAGE:
            object.__setattr__(
                self,
                "GUARDRAILS_BLOCKED_MESSAGE",
                "I'm not able to help with that, but our Admissions Advisors would be happy to "
                f"assist! You can reach them at {self.UNIVERSITY_ADMISSIONS_PHONE}.",
            )


settings = Settings()
