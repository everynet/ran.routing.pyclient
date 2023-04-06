import json

import pytest

from ran.routing.core import Core
from ran.routing.core.domains import Gps, LoRaModulation, UpstreamMessage, UpstreamRadio, UpstreamRejectResultCode


@pytest.mark.asyncio
async def test_upstream_creation(core: Core, client_session, client_session_ws):
    async with core.upstream() as _:
        # Will stop listener
        client_session_ws.shutdown.set()

    assert client_session.ws_connect.called


@pytest.mark.asyncio
async def test_upstream_creation_ctx(core: Core, client_session, client_session_ws):
    conn = await core.upstream.create_connection()
    # Will stop listener
    client_session_ws.shutdown.set()
    conn.close()
    await conn.wait_closed()

    assert client_session.ws_connect.called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_session_ws",
    [
        (
            UpstreamMessage(
                protocol_version=1,
                transaction_id=1,
                outdated=None,
                dev_euis=[0x7ABE1B8C93D7174F],
                radio=UpstreamRadio(
                    frequency=868100000,
                    lora=LoRaModulation(spreading=12, bandwidth=125000),
                    fsk=None,
                    fhss=None,
                    rssi=-50.0,
                    snr=2.0,
                ),
                phy_payload_no_mic=[0, 244, 104, 139, 79, 98, 207, 237, 60, 79, 23, 215, 147, 140, 27, 190, 122, 0, 0],
                mic_challenge=[0xAA595854],
                gps=Gps(lat=51.178889, lng=-1.826111, alt=None),
            ),
        )
    ],
    indirect=True,
)
async def test_upstream_stream_basic_receive(core: Core, client_session_ws):
    async with core.upstream() as upstream_conn:
        # We will receive one message, so we just unblock listener after receiving first message from stream.
        # Listener will receive "WS_CLOSED_MESSAGE" after setting this event, and "stream" must exit gracefully.
        client_session_ws.shutdown.set()

        async for msg in upstream_conn.stream():
            assert msg == client_session_ws.recvd_messages[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_session_ws",
    [
        (
            UpstreamMessage(
                protocol_version=1,
                transaction_id=1,
                outdated=None,
                dev_euis=[0x7ABE1B8C93D7174F],
                radio=UpstreamRadio(
                    frequency=868100000,
                    lora=LoRaModulation(spreading=12, bandwidth=125000),
                    fsk=None,
                    fhss=None,
                    rssi=-50.0,
                    snr=2.0,
                ),
                phy_payload_no_mic=[0, 244, 104, 139, 79, 98, 207, 237, 60, 79, 23, 215, 147, 140, 27, 190, 122, 0, 0],
                mic_challenge=[0xAA595854],
                gps=Gps(lat=51.178889, lng=-1.826111, alt=None),
            ),
        )
    ],
    indirect=True,
)
async def test_upstream_stream_recv_send_ack(core: Core, client_session_ws):
    async with core.upstream() as upstream_conn:
        # We will receive one message, so we just unblock listener after receiving first message from stream.
        # Listener will receive "WS_CLOSED_MESSAGE" after setting this event, and "stream" must exit gracefully.
        client_session_ws.shutdown.set()

        async for msg in upstream_conn.stream():
            assert msg == client_session_ws.recvd_messages[0]
            await upstream_conn.send_upstream_ack(
                transaction_id=msg.transaction_id, dev_eui=msg.dev_euis[0], mic=msg.mic_challenge[0]
            )
            assert client_session_ws.sent_messages[0] == json.dumps(
                {
                    "ProtocolVersion": 1,
                    "TransactionID": msg.transaction_id,
                    "DevEUI": msg.dev_euis[0],
                    "MIC": msg.mic_challenge[0],
                }
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_session_ws",
    [
        (
            UpstreamMessage(
                protocol_version=1,
                transaction_id=1,
                outdated=None,
                dev_euis=[0x7ABE1B8C93D7174F],
                radio=UpstreamRadio(
                    frequency=868100000,
                    lora=LoRaModulation(spreading=12, bandwidth=125000),
                    fsk=None,
                    fhss=None,
                    rssi=-50.0,
                    snr=2.0,
                ),
                phy_payload_no_mic=[0, 244, 104, 139, 79, 98, 207, 237, 60, 79, 23, 215, 147, 140, 27, 190, 122, 0, 0],
                mic_challenge=[0xAA595854],
                gps=Gps(lat=51.178889, lng=-1.826111, alt=None),
            ),
        )
    ],
    indirect=True,
)
async def test_upstream_stream_recv_send_reject(core: Core, client_session_ws):
    async with core.upstream() as upstream_conn:
        # We will receive one message, so we just unblock listener after receiving first message from stream.
        # Listener will receive "WS_CLOSED_MESSAGE" after setting this event, and "stream" must exit gracefully.
        client_session_ws.shutdown.set()

        async for msg in upstream_conn.stream():
            assert msg == client_session_ws.recvd_messages[0]
            await upstream_conn.send_upstream_reject(
                transaction_id=msg.transaction_id,
                result_code=UpstreamRejectResultCode.MICFailed,
            )
            assert client_session_ws.sent_messages[0] == json.dumps(
                {"ProtocolVersion": 1, "TransactionID": 1, "ResultCode": "MICFailed"}
            )


@pytest.mark.asyncio
async def test_upstream_send_ack_no_stream(core: Core, client_session_ws):
    upstream_conn = await core.upstream.create_connection()
    await upstream_conn.send_upstream_ack(transaction_id=1, dev_eui=1, mic=1)
    assert client_session_ws.sent_messages[0] == json.dumps(
        {
            "ProtocolVersion": 1,
            "TransactionID": 1,
            "DevEUI": 1,
            "MIC": 1,
        }
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    upstream_conn.close()
    await upstream_conn.wait_closed()


@pytest.mark.asyncio
async def test_upstream_send_ack_no_stream_ctx(core: Core, client_session_ws):
    async with core.upstream() as upstream_conn:
        await upstream_conn.send_upstream_ack(transaction_id=1, dev_eui=1, mic=1)
        assert client_session_ws.sent_messages[0] == json.dumps(
            {
                "ProtocolVersion": 1,
                "TransactionID": 1,
                "DevEUI": 1,
                "MIC": 1,
            }
        )
        upstream_conn.close()
        # After this, listener task will exit, so we don't want to call "upstream_conn.wait_closed()"
        client_session_ws.shutdown.set()


@pytest.mark.asyncio
async def test_upstream_send_reject_no_stream(core: Core, client_session_ws):
    upstream_conn = await core.upstream.create_connection()
    await upstream_conn.send_upstream_reject(transaction_id=1, result_code=UpstreamRejectResultCode.MICFailed)
    assert client_session_ws.sent_messages[0] == json.dumps(
        {"ProtocolVersion": 1, "TransactionID": 1, "ResultCode": "MICFailed"}
    )
    # Unblocking listener
    client_session_ws.shutdown.set()

    upstream_conn.close()
    await upstream_conn.wait_closed()


@pytest.mark.asyncio
async def test_upstream_send_reject_no_stream_ctx(core: Core, client_session_ws):
    async with core.upstream() as upstream_conn:
        await upstream_conn.send_upstream_reject(transaction_id=1, result_code=UpstreamRejectResultCode.MICFailed)
        assert client_session_ws.sent_messages[0] == json.dumps(
            {"ProtocolVersion": 1, "TransactionID": 1, "ResultCode": "MICFailed"}
        )
        upstream_conn.close()
        # After this, listener task will exit, so we don't want to call "upstream_conn.wait_closed()"
        client_session_ws.shutdown.set()
