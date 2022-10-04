import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.http_websocket import WS_CLOSED_MESSAGE, WSMessage, WSMsgType

from ran.routing.core import Core
from ran.routing.core.domains import (
    Coverage,
    DownstreamAckMessage,
    DownstreamMessage,
    DownstreamResultMessage,
    UpstreamMessage,
)
from ran.routing.core.serializers.json import (
    DownstreamAckOrResultSerializer,
    DownstreamMessageSerializer,
    UpstreamMessageSerializer,
)

# - - -


@pytest.fixture(scope="function")
def client_session_ws(request):
    # Usage examples:
    # @pytest.mark.parametrize("client_session_ws", ["some packed json"], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [b"some packed json"], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [UpstreamMessage(...)], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [DownstreamMessage(...)], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [DownstreamAckMessage(...)], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [DownstreamResultMessage(...)], indirect=True)
    # @pytest.mark.parametrize("client_session_ws", [WSMessage(...)], indirect=True)

    ws_mock = MagicMock()
    ws_mock.shutdown = asyncio.Event()
    ws_mock.recvd_messages = []
    ws_mock.sent_messages = []

    # Buffer for messages to be sent
    messages = []
    if hasattr(request, "param"):
        # Magic for handling different types of messages
        for param_msg in request.param:
            ws_mock.recvd_messages.append(param_msg)
            if isinstance(param_msg, UpstreamMessage):
                messages.append(
                    WSMessage(type=WSMsgType.TEXT, data=UpstreamMessageSerializer.serialize(param_msg), extra=None)
                )
            elif isinstance(param_msg, DownstreamMessage):
                messages.append(
                    WSMessage(type=WSMsgType.TEXT, data=DownstreamMessageSerializer.serialize(param_msg), extra=None)
                )
            elif isinstance(param_msg, (DownstreamAckMessage, DownstreamResultMessage)):
                messages.append(
                    WSMessage(
                        type=WSMsgType.TEXT, data=DownstreamAckOrResultSerializer.serialize(param_msg), extra=None
                    )
                )
            elif isinstance(param_msg, WSMessage):
                messages.append(param_msg)
            elif isinstance(param_msg, str):
                messages.append(WSMessage(type=WSMsgType.TEXT, data=param_msg, extra=None))
            elif isinstance(param_msg, bytes):
                messages.append(WSMessage(WSMsgType.BINARY, data=param_msg, extra=None))

    async def receive(timeout):
        if len(messages):
            return messages.pop()
        # Receiver will block, until someone calls "ws_mock.shutdown.set()"
        # This is required to prevent listener to close connection too early.
        # After unblocking, listener will receive WS_CLOSED_MESSAGE, it will cause graceful shutdown of listener
        await ws_mock.shutdown.wait()
        return WS_CLOSED_MESSAGE

    def send(data):
        ws_mock.sent_messages.append(data)

    ws_mock.receive = AsyncMock(side_effect=receive)
    ws_mock.send_str = AsyncMock(side_effect=send)
    ws_mock.send_bytes = AsyncMock(side_effect=send)

    return ws_mock


@pytest.fixture(scope="function")
def client_session(client_session_ws):
    mock = MagicMock()
    mock.close = AsyncMock()
    mock.ws_connect.return_value.__aenter__.return_value = client_session_ws
    return mock


@pytest.fixture(scope="function")
async def core(client_session):
    with patch("aiohttp.ClientSession", lambda *a, **kw: client_session):
        async with Core("token", Coverage.DEV) as core:
            yield core
