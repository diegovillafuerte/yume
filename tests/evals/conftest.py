"""Eval test fixtures and helpers.

These fixtures use a real database and real OpenAI API calls.
Each test gets a clean DB (tables created/dropped per test).
"""

import asyncio
from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base
from app.models.function_trace import FunctionTrace
from app.services.message_router import MessageRouter
from app.services.tracing import (
    clear_trace_context,
    save_pending_traces,
    start_trace_context,
)
from app.services.whatsapp import WhatsAppClient

settings = get_settings()
TEST_DATABASE_URL = settings.async_database_url.replace("/parlo", "/parlo_test")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def eval_engine():
    """Create test database engine, create/drop tables per test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def eval_db(eval_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session for evals."""
    session_factory = async_sessionmaker(
        eval_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


async def simulate_message(
    db: AsyncSession,
    sender_phone: str,
    recipient_phone: str,
    body: str,
    sender_name: str | None = None,
) -> tuple[dict, UUID]:
    """Send a simulated message through the full routing pipeline.

    Returns:
        Tuple of (result dict from route_message, correlation_id)
    """
    message_id = f"eval_{uuid4().hex[:16]}"
    correlation_id = start_trace_context(phone_number=sender_phone)

    try:
        whatsapp_client = WhatsAppClient(mock_mode=True)
        router = MessageRouter(db=db, whatsapp_client=whatsapp_client)

        result = await router.route_message(
            phone_number_id=recipient_phone,
            sender_phone=sender_phone,
            message_id=message_id,
            message_content=body,
            sender_name=sender_name,
        )

        await save_pending_traces(db)
        await db.commit()

        return result, correlation_id

    finally:
        clear_trace_context()


async def get_tool_calls(db: AsyncSession, correlation_id: UUID) -> list[str]:
    """Get list of AI tool names called during a traced request.

    Queries FunctionTrace for entries with trace_type='ai_tool' and
    extracts the tool_name from input_summary.
    """
    result = await db.execute(
        select(FunctionTrace).where(
            FunctionTrace.correlation_id == correlation_id,
            FunctionTrace.trace_type == "ai_tool",
        ).order_by(FunctionTrace.sequence_number)
    )
    traces = result.scalars().all()

    tool_names = []
    for trace in traces:
        # Tool name is typically in input_summary.tool_name or function_name
        tool_name = None
        if trace.input_summary and isinstance(trace.input_summary, dict):
            tool_name = trace.input_summary.get("tool_name")
        if not tool_name:
            tool_name = trace.function_name
        tool_names.append(tool_name)

    return tool_names
