import json

import pytest

from ran.routing.core import Core
from ran.routing.core.domains import (
    DownstreamAckMessage,
    DownstreamMessage,
    DownstreamResultCode,
    DownstreamResultMessage,
    MulticastDownstreamMessage,
)


@pytest.mark.asyncio
async def test_downstream_creation(core: Core, client_session, client_session_ws):
    async with core.downstream() as _:
        # Will stop listener
        client_session_ws.shutdown.set()

    assert client_session.ws_connect.called


@pytest.mark.asyncio
async def test_downstream_creation_ctx(core: Core, client_session, client_session_ws):
    conn = await core.downstream.create_connection()
    # Will stop listener
    client_session_ws.shutdown.set()
    conn.close()
    await conn.wait_closed()

    assert client_session.ws_connect.called


@pytest.mark.asyncio
async def test_downstream_send_downstream_ctx(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        await downstream_conn.send_downstream(
            transaction_id=1,
            dev_eui=1,
            tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
            phy_payload=b"fff",
        )
        assert client_session_ws.sent_messages[0] == json.dumps(
            {
                "ProtocolVersion": 1,
                "TransactionID": 1,
                "DevEUI": 1,
                "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
                "PHYPayload": [102, 102, 102],
            }
        )
        # Will stop listener
        client_session_ws.shutdown.set()


@pytest.mark.asyncio
async def test_downstream_send_downstream(core: Core, client_session_ws):
    downstream_conn = await core.downstream.create_connection()
    await downstream_conn.send_downstream(
        transaction_id=1,
        dev_eui=1,
        tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
        phy_payload=b"fff",
    )
    assert client_session_ws.sent_messages[0] == json.dumps(
        {
            "ProtocolVersion": 1,
            "TransactionID": 1,
            "DevEUI": 1,
            "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
            "PHYPayload": [102, 102, 102],
        }
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    downstream_conn.close()
    await downstream_conn.wait_closed()


@pytest.mark.asyncio
async def test_downstream_send_downstream_obj_ctx(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        await downstream_conn.send_downstream_object(
            DownstreamMessage.parse_obj(
                dict(
                    protocol_version=1,
                    transaction_id=1,
                    dev_eui=1,
                    tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
                    phy_payload=b"fff",
                )
            )
        )
        assert client_session_ws.sent_messages[0] == json.dumps(
            {
                "ProtocolVersion": 1,
                "TransactionID": 1,
                "DevEUI": 1,
                "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
                "PHYPayload": [102, 102, 102],
            }
        )
        # Will stop listener
        client_session_ws.shutdown.set()


@pytest.mark.asyncio
async def test_downstream_send_downstream_obj(core: Core, client_session_ws):
    downstream_conn = await core.downstream.create_connection()
    await downstream_conn.send_downstream_object(
        DownstreamMessage.parse_obj(
            dict(
                protocol_version=1,
                transaction_id=1,
                dev_eui=1,
                tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
                phy_payload=b"fff",
            )
        )
    )
    assert client_session_ws.sent_messages[0] == json.dumps(
        {
            "ProtocolVersion": 1,
            "TransactionID": 1,
            "DevEUI": 1,
            "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
            "PHYPayload": [102, 102, 102],
        }
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    downstream_conn.close()
    await downstream_conn.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_session_ws",
    [
        (
            DownstreamAckMessage(
                protocol_version=1,
                transaction_id=1,
                mailbox_id=1,
            ),
        ),
    ],
    indirect=True,
)
async def test_downstream_stream_ack(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        # We will receive one message, so we just unblock listener after receiving first message from stream.
        # Listener will receive "WS_CLOSED_MESSAGE" after setting this event, and "stream" must exit gracefully.
        client_session_ws.shutdown.set()

        async for msg in downstream_conn.stream():
            assert msg == client_session_ws.recvd_messages[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_session_ws",
    [
        (
            DownstreamResultMessage(
                protocol_version=1,
                transaction_id=1,
                result_code=DownstreamResultCode.Success,
                result_message="Success",
                mailbox_id=1,
            ),
        ),
    ],
    indirect=True,
)
async def test_downstream_stream_result(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        # We will receive one message, so we just unblock listener after receiving first message from stream.
        # Listener will receive "WS_CLOSED_MESSAGE" after setting this event, and "stream" must exit gracefully.
        client_session_ws.shutdown.set()

        async for msg in downstream_conn.stream():
            assert msg == client_session_ws.recvd_messages[0]


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Multicast downstream


@pytest.mark.asyncio
async def test_downstream_send_multicast_downstream_ctx(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        await downstream_conn.send_multicast_downstream(
            transaction_id=1,
            addr=1,
            tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
            phy_payload=b"fff",
        )
        assert client_session_ws.sent_messages[0] == json.dumps(
            {
                "ProtocolVersion": 1,
                "TransactionID": 1,
                "Addr": 1,
                "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
                "PHYPayload": [102, 102, 102],
            }
        )
        # Will stop listener
        client_session_ws.shutdown.set()


@pytest.mark.asyncio
async def test_downstream_send_multicast_downstream(core: Core, client_session_ws):
    downstream_conn = await core.downstream.create_connection()
    await downstream_conn.send_multicast_downstream(
        transaction_id=1,
        addr=1,
        tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
        phy_payload=b"fff",
    )
    assert client_session_ws.sent_messages[0] == json.dumps(
        {
            "ProtocolVersion": 1,
            "TransactionID": 1,
            "Addr": 1,
            "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
            "PHYPayload": [102, 102, 102],
        }
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    downstream_conn.close()
    await downstream_conn.wait_closed()


@pytest.mark.asyncio
async def test_downstream_send_multicast_downstream_obj_ctx(core: Core, client_session_ws):
    async with core.downstream() as downstream_conn:
        await downstream_conn.send_downstream_object(
            MulticastDownstreamMessage.parse_obj(
                dict(
                    protocol_version=1,
                    transaction_id=1,
                    addr=1,
                    tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
                    phy_payload=b"fff",
                )
            )
        )
        assert client_session_ws.sent_messages[0] == json.dumps(
            {
                "ProtocolVersion": 1,
                "TransactionID": 1,
                "Addr": 1,
                "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
                "PHYPayload": [102, 102, 102],
            }
        )
        # Will stop listener
        client_session_ws.shutdown.set()


@pytest.mark.asyncio
async def test_downstream_send_multicast_downstream_obj(core: Core, client_session_ws):
    downstream_conn = await core.downstream.create_connection()
    await downstream_conn.send_downstream_object(
        MulticastDownstreamMessage.parse_obj(
            dict(
                protocol_version=1,
                transaction_id=1,
                addr=1,
                tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
                phy_payload=b"fff",
            )
        )
    )
    assert client_session_ws.sent_messages[0] == json.dumps(
        {
            "ProtocolVersion": 1,
            "TransactionID": 1,
            "Addr": 1,
            "TxWindow": {"Radio": {"Frequency": 868300000, "LoRa": {"Spreading": 1, "Bandwidth": 1}}, "Delay": 1},
            "PHYPayload": [102, 102, 102],
        }
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    downstream_conn.close()
    await downstream_conn.wait_closed()
