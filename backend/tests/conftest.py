import os
import uuid
from collections.abc import AsyncGenerator, Mapping

import docker
import pytest
import pytest_asyncio
from docker.models.containers import Container
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Base, User
from tests.rag_fixtures import create_session_factory

# Fixed UUID for centralized test user
TEST_USER_ID = uuid.UUID("12345678-1234-5678-9abc-123456789012")

# Module-scoped postgres container for all tests
_test_engine = None
_test_session_factory = None

# Container settings for persistent RAG data
_PERSISTENT_CONTAINER_NAME = "virtual-assistant-test-postgres"
_POSTGRES_IMAGE = "pgvector/pgvector:pg17"
_POSTGRES_USER = "test"
_POSTGRES_PASSWORD = "test"  # noqa: S105
_POSTGRES_DB = "test"


def _build_database_url_from_env(env: Mapping[str, str]) -> str | None:
    server = env.get("POSTGRES_SERVER")
    user = env.get("POSTGRES_USER")
    password = env.get("POSTGRES_PASSWORD")
    db = env.get("POSTGRES_DB")
    if not server or not user or not password or not db:
        return None
    port = env.get("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--rebuild-rag",
        action="store_true",
        default=False,
        help="Force rebuild of RAG data (expensive - calls embedding API)",
    )
    parser.addoption(
        "--fresh-db",
        action="store_true",
        default=False,
        help="Start with a fresh database container (removes persistent RAG data)",
    )
    parser.addoption(
        "--repeat",
        "-R",
        action="store",
        type=int,
        default=1,
        help="Number of times to repeat each LLM judge test case (default: 1)",
    )
    parser.addoption(
        "--max-concurrency",
        "-C",
        action="store",
        type=int,
        default=5,
        help="Maximum concurrent LLM calls per test case (default: 5)",
    )
    parser.addoption(
        "--test-cases",
        "-T",
        action="store",
        type=str,
        default=None,
        help="Comma-separated list of test case IDs to run "
        "(e.g., 'greeting_response,accreditation_inquiry')",
    )
    parser.addoption(
        "--pass-threshold",
        "-P",
        action="store",
        type=float,
        default=0.9,
        help="Minimum pass rate threshold for each test case (default: 0.9 = 90%%)",
    )
    parser.addoption(
        "--chatbot-model",
        action="store",
        type=str,
        default=None,
        help="Override the chatbot model for evals.",
    )
    parser.addoption(
        "--guardrail-model",
        action="store",
        type=str,
        default=None,
        help="Override the guardrails model for evals.",
    )
    parser.addoption(
        "--search-model",
        action="store",
        type=str,
        default=None,
        help="Override the search model for evals.",
    )
    parser.addoption(
        "--extractor-model",
        action="store",
        type=str,
        default=None,
        help="Override the extractor model for evals.",
    )
    parser.addoption(
        "--evaluation-model",
        action="store",
        type=str,
        default=None,
        help="Override the evaluation model for evals.",
    )


def _get_container_host_port(container: Container) -> tuple[str, int]:
    """Extract host and port from container port mapping."""
    container.reload()
    port_mapping = container.ports.get("5432/tcp", [{}])[0]
    host_port = int(port_mapping.get("HostPort", 5432))
    host: str = port_mapping.get("HostIp", "localhost")
    if host == "0.0.0.0":  # noqa: S104
        host = "localhost"
    return host, host_port


def _wait_for_container(container: Container, *, check_postgres: bool = False) -> None:
    """Wait for container to be ready."""
    import time

    for _ in range(30):
        container.reload()
        if container.status == "running":
            if not check_postgres:
                break
            # Check if postgres is ready
            exit_code, _ = container.exec_run("pg_isready -U test")
            if exit_code == 0:
                break
        time.sleep(1)


def _get_or_create_container() -> tuple[str, int]:
    """Get existing container or create a new one. Returns (host, port)."""
    client = docker.from_env()

    # Check for existing container
    containers: list[Container] = client.containers.list(
        all=True, filters={"name": _PERSISTENT_CONTAINER_NAME}
    )

    if containers:
        container = containers[0]
        if container.status != "running":
            print(f"\n🔄 Starting existing container '{_PERSISTENT_CONTAINER_NAME}'...")
            container.start()
            _wait_for_container(container)

        host, host_port = _get_container_host_port(container)
        print(
            f"\n🔄 Reusing existing test database container "
            f"'{_PERSISTENT_CONTAINER_NAME}' at {host}:{host_port}"
        )
        return host, host_port

    # Create new container
    print(f"\n🆕 Creating new test database container '{_PERSISTENT_CONTAINER_NAME}'...")
    container = client.containers.run(
        _POSTGRES_IMAGE,
        name=_PERSISTENT_CONTAINER_NAME,
        environment={
            "POSTGRES_USER": _POSTGRES_USER,
            "POSTGRES_PASSWORD": _POSTGRES_PASSWORD,
            "POSTGRES_DB": _POSTGRES_DB,
        },
        ports={"5432/tcp": None},  # Auto-assign host port
        detach=True,
        remove=False,  # Don't auto-remove when stopped
    )

    _wait_for_container(container, check_postgres=True)

    host, host_port = _get_container_host_port(container)
    print(f"✅ Container ready at {host}:{host_port}")
    return host, host_port


def _remove_container() -> None:
    """Remove the persistent test container."""
    try:
        client = docker.from_env()
        containers: list[Container] = client.containers.list(
            all=True, filters={"name": _PERSISTENT_CONTAINER_NAME}
        )
        for container in containers:
            print(f"\n🗑️ Removing container '{_PERSISTENT_CONTAINER_NAME}'...")
            container.remove(force=True)
    except Exception as e:
        print(f"Warning: Could not remove container: {e}")


def pytest_configure(config: pytest.Config) -> None:
    """Start PostgreSQL container before any tests run.

    Uses a persistent named container to preserve RAG data between test sessions.
    RAG data is expensive to create (embedding API calls) so we keep it persistent.
    """
    if "TELEMETRY_DATABASE_URL" not in os.environ:
        telemetry_url = _build_database_url_from_env(os.environ)
        if telemetry_url is not None:
            os.environ["TELEMETRY_DATABASE_URL"] = telemetry_url

    fresh_db = config.getoption("--fresh-db", default=False)

    if fresh_db:
        _remove_container()

    # Get or create container
    host, port = _get_or_create_container()

    # Set environment variables
    os.environ["POSTGRES_SERVER"] = host
    os.environ["POSTGRES_PORT"] = str(port)
    os.environ["POSTGRES_USER"] = _POSTGRES_USER
    os.environ["POSTGRES_PASSWORD"] = _POSTGRES_PASSWORD
    os.environ["POSTGRES_DB"] = _POSTGRES_DB

    from app.core import config as config_module
    from app.core import db

    config_module.settings = config_module.Settings()
    db.init_engine()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Keep PostgreSQL container running for RAG data persistence."""
    print(
        f"\n💾 Test database container '{_PERSISTENT_CONTAINER_NAME}' "
        "kept running for RAG data persistence"
    )
    print("   Use --fresh-db to start with a clean database")


def _build_async_url() -> str:
    """Build async database URL from environment variables."""
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ["POSTGRES_PORT"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


@pytest_asyncio.fixture(scope="session")
async def db_engine(request: pytest.FixtureRequest):
    """Create the database engine and tables once per test session.

    Handles both new containers and reused persistent containers.
    If --rebuild-rag is passed, will rebuild RAG data (expensive).
    """
    global _test_engine, _test_session_factory  # noqa: PLW0603

    from tests.rag_fixtures import check_rag_data_exists, get_rag_data_stats, populate_rag_data

    # Build URL from environment variables (works for both new and reused containers)
    async_url = _build_async_url()

    _test_engine = create_async_engine(async_url, echo=False)
    _test_session_factory = create_session_factory(_test_engine)

    # Create pgvector extension and all tables (idempotent)
    async with _test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # Check if RAG data needs to be populated
    rebuild_rag = request.config.getoption("--rebuild-rag", default=False)
    rag_exists = await check_rag_data_exists(_test_engine)

    if rebuild_rag or not rag_exists:
        if rebuild_rag:
            print("\n🔨 Rebuilding RAG data (--rebuild-rag flag set)...")
        else:
            print("\n📦 No RAG data found, populating database...")

        await populate_rag_data(_test_engine)
        stats = await get_rag_data_stats(_test_engine)
        print(
            f"✅ RAG data populated: {stats['total_documents']} documents, "
            f"{stats['total_chunks']} chunks"
        )
    else:
        stats = await get_rag_data_stats(_test_engine)
        print(
            f"\n✅ Using existing RAG data: {stats['total_documents']} documents, "
            f"{stats['total_chunks']} chunks"
        )

    yield _test_engine

    await _test_engine.dispose()


@pytest_asyncio.fixture
async def session(db_engine: object) -> AsyncGenerator[AsyncSession]:
    """Create a test database session with transaction rollback.

    Each test gets its own transaction that is rolled back after the test completes,
    ensuring test isolation. Any data created during the test will not persist.
    """
    if _test_session_factory is None:
        raise RuntimeError("Test session factory not initialized")
    if _test_engine is None:
        raise RuntimeError("Test engine not initialized")

    # Get a connection and start a transaction
    async with _test_engine.connect() as connection:
        # Start a transaction that will be rolled back
        transaction = await connection.begin()

        # Create a session bound to this connection
        async with _test_session_factory(bind=connection) as session:
            # Disable the session's ability to commit (nested transactions go to savepoints)
            yield session

        # Rollback the transaction after the test
        await transaction.rollback()


@pytest_asyncio.fixture
async def clean_session(db_engine: object) -> AsyncGenerator[AsyncSession]:
    """Create a test database session that cleans non-RAG tables before the test.

    Use this fixture for integration tests that need a clean slate for
    conversations/messages but want to preserve RAG data (Document, DocumentContentChunk).
    """
    from tests.rag_fixtures import clear_non_rag_tables

    if _test_session_factory is None:
        raise RuntimeError("Test session factory not initialized")

    async with _test_session_factory() as session:
        # Clean non-RAG tables before the test
        await clear_non_rag_tables(session)
        yield session


@pytest_asyncio.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a centralized test user for testing."""
    # Check if user already exists by ID
    existing_user = await session.get(User, TEST_USER_ID)
    if existing_user:
        return existing_user

    # Check if user exists by email (in case of ID mismatch)
    stmt = select(User).filter_by(email="test@example.com")
    result = await session.execute(stmt)
    existing_user_by_email = result.scalar_one_or_none()
    if existing_user_by_email:
        return existing_user_by_email

    # Use a pre-generated bcrypt hash for "testpass123" to avoid bcrypt issues in tests
    # This is a valid bcrypt hash generated for "testpass123"
    precomputed_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.R.HqhAW5a3QBGG"

    user = User(
        id=TEST_USER_ID,
        email="test@example.com",
        name="Test User",
        password_hash=precomputed_hash,
        is_active=True,
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)

    except Exception:
        await session.rollback()
        # If commit failed, try to get the user again (race condition)
        existing_user = await session.get(User, TEST_USER_ID)
        if existing_user:
            return existing_user
        stmt = select(User).filter_by(email="test@example.com")
        result = await session.execute(stmt)
        existing_user_by_email = result.scalar_one_or_none()
        if existing_user_by_email:
            return existing_user_by_email
        raise
    else:
        return user


@pytest.fixture
def model() -> str:
    from app.core.config import settings

    return settings.CHATBOT_MODEL
