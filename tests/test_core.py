from unittest.mock import AsyncMock, patch

import pytest

from ran.routing.core import Core


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_core_basic_usage():
    core = Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0")
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.connect()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None
    assert core._opened.is_set()

    await core.close()
    assert core._Core__session.close.called
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None
    assert core._closed.is_set()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_core_context_usage():
    async with Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0") as core:
        assert core._opened.is_set()
    assert core._Core__session.close.called
    assert core._closed.is_set()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_double_connect_no_exc():
    core = Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0")
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.connect()
    assert core._opened.is_set()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None

    # Second connection call
    await core.connect()
    assert core._opened.is_set()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None

    await core.close()
    assert core._Core__session.close.called
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None
    assert core._closed.is_set()


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_double_connect_with_exc():
    core = Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0")
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.connect()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None

    assert core._opened.is_set()
    with pytest.raises(Exception):
        await core.connect(raise_exception=True)


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_double_close_no_exc():
    core = Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0")
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.connect()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None
    assert core._opened.is_set()

    await core.close()
    assert core._Core__session.close.called
    assert core._closed.is_set()
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.close()
    assert core._Core__session.close.called
    assert core._closed.is_set()
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None


@pytest.mark.asyncio
@patch("aiohttp.ClientSession", AsyncMock)
async def test_double_close_with_exc():
    core = Core("token", url="https://dev.cloud.dev.everynet.io/api/v1.0")
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    await core.connect()
    assert core.routing_table is not None
    assert core.upstream is not None
    assert core.downstream is not None
    assert core._opened.is_set()

    await core.close()
    assert core._Core__session.close.called
    assert core._closed.is_set()
    assert core.routing_table is None
    assert core.upstream is None
    assert core.downstream is None

    with pytest.raises(Exception):
        await core.close(raise_exception=True)
