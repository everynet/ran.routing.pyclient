from ran.routing.core import Core, domains

# import logging
# logging.basicConfig(level=logging.DEBUG)


async def main():
    async with Core(access_token="...", url="...") as ran:
        async with ran.downstream() as downstream, ran.upstream() as upstream:
            # Receiving upstream
            msg = await upstream.recv(timeout=10)
            assert isinstance(msg, domains.UpstreamMessage)
            print(repr(msg))

            # Sending ack
            await upstream.send_upstream_ack(msg.transaction_id, dev_eui=msg.dev_euis[0], mic=msg.mic_challenge[0])

            # Sending downstream
            await downstream.send_downstream(
                transaction_id=1,
                dev_eui=8844537008791951183,
                tx_window={"delay": 1, "radio": {"frequency": 868300000, "lora": {"spreading": 1, "bandwidth": 1}}},
                phy_payload=b"hi",
            )
            # Receiving downstream info
            for msg_type in [domains.DownstreamAckMessage, domains.DownstreamResultMessage]:
                msg = await downstream.recv(timeout=3)
                print(repr(msg))
                assert isinstance(msg, msg_type)


if __name__ == "__main__":
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
