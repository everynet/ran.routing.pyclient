import asyncio
import logging
import typing as t
from contextlib import suppress

import async_timeout

from ran.routing.core import Core, domains


async def prepare_downstream(abstract_downstream_dict: dict) -> domains.DownstreamMessage:
    # Please enter the correct data from your abstract_downstream_dict here.

    lora_modulation = domains.LoRaModulation(spreading=12, bandwidth=125000)
    radio = domains.DownstreamRadio(frequency=868300000, lora=lora_modulation)
    tx_window = domains.TransmissionWindow(radio=radio, delay=5)

    return domains.DownstreamMessage(
        transaction_id=1,
        dev_eui=18446744073709551615,
        tx_window=tx_window,
        phy_payload=b"my payload",
    )


async def handle_upstream_message(upstream_message: domains.UpstreamMessage) -> t.Tuple[int, int]:
    # Please put here your code to handling upstream_message and passing it to your NS

    return upstream_message.dev_euis[0], upstream_message.mic_challenge[0]


async def upstream_loop_forever(ran: Core):
    async with ran.upstream() as upstream_conn:
        async for upstream_message in upstream_conn.stream(timeout=1):
            dev_eui, mic = await handle_upstream_message(upstream_message)
            await upstream_conn.send_upstream_ack(
                transaction_id=upstream_message.transaction_id, dev_eui=dev_eui, mic=mic
            )


async def downstream_loop_forever(ran: Core, downstream_queue: asyncio.Queue):
    downstream_sync = DownstreamSync()

    async with ran.downstream() as downstream_conn:
        task_ack_result_listener = asyncio.create_task(downstream_sync.ack_result_listener(downstream_conn))

        with suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(delay=1):
                abstract_downstream_dict: t.Dict[str, t.Any] = await downstream_queue.get()
                downstream_message: domains.DownstreamMessage = await prepare_downstream(abstract_downstream_dict)

                await downstream_conn.send_downstream_object(downstream_message)

                downstream_ack = await downstream_sync.create_downstream_ack_future(
                    downstream_message.transaction_id
                )
                downstream_result = await downstream_sync.create_downstream_result_future(
                    downstream_message.transaction_id
                )

        await task_ack_result_listener


class DownstreamSync:
    def __init__(
        self,
    ):
        self.acks = {}
        self.results = {}

    def create_downstream_ack_future(self, transaction_id: int) -> asyncio.Future[domains.DownstreamAckMessage]:
        future: asyncio.Future[domains.DownstreamAckMessage] = asyncio.Future()
        self.acks[transaction_id] = future

        return future

    def create_downstream_result_future(self, transaction_id: int) -> asyncio.Future[domains.DownstreamResultMessage]:
        future: asyncio.Future[domains.DownstreamResultMessage] = asyncio.Future()
        self.results[transaction_id] = future

        return future

    async def ack_result_listener(self, connection):
        async for ack_or_result in connection.stream():
            if isinstance(ack_or_result, domains.DownstreamAckMessage):
                if ack_or_result.transaction_id in self.acks:
                    self.acks.pop(ack_or_result.transaction_id).set_result(ack_or_result)
            elif isinstance(ack_or_result, domains.DownstreamResultMessage):
                if ack_or_result.transaction_id in self.results:
                    self.results.pop(ack_or_result.transaction_id).set_result(ack_or_result)


async def run_forever():
    downstream_queue = asyncio.Queue()  # pass this queue to your NS to send downstream messages to this queue

    async with Core(access_token="...", url="...") as ran:
        device = await ran.routing_table.insert(dev_eui=123130, dev_addr=123)

        await asyncio.gather(upstream_loop_forever(ran), downstream_loop_forever(ran, downstream_queue))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(run_forever())
