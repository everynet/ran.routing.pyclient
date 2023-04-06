
# Guide

## MIC challenge 

To keep upstream traffic clean and for the billing purposes we require LNS to acknowledge each upstream message.

**Acknowledgment procedure is designed this way to let RAN check whether LNS has correct device keys in possession without revealing these keys.**

The procedure executed by LNS is the following:

1. On `Upstream` message reception compute MIC using `Payload.PHYPayloadNoMIC` and `AppSKey` stored at LNS.
1. Check whether the `Payload.MICChallenge` field contains the correct MIC calculated on the previous step.
1. Send back `UpstreamAck` message to RAN (with LNS-calculated MIC in the `Payload.MIC` field).

The size of the `MICChallenge` field varies from 2 to 4096 and is reduced with every successful `UpstreamAck`.

Failure to accomplish this procedure may result in unsubscription of the LNS from the selected device traffic.


## How to handle MIC challenge

Simple way to integrate MIC challenge with existing LoRa network server is to use existing Network Server implementation as blackbox and create some kind of mic-challenge wrapper for it.

We assuming that LNS has some kind of MIC verification implementation, which raises an exception if the MIC is not correct.

We can use this behavior to implement our MIC challenge wrapper.

This wrapper will try to pass the lora message with random mic from MICChallenge field to the underlying network server.
If the underlying network server raises an exception, wrapper will pass other message with random mic.

This procedure will be repeated until the underlying network server accepts the message.
When message is accepted, wrapper will send `UpstreamAck` message with correct MIC. If all attempts are failed, wrapper will send `UpstreamReject` message.

Simplified example of the MIC challenge wrapper:

```python
from ran.routing.core import domains, Core, UpstreamConnection

# This is error, raised when LNS could not verify MIC 
class MicError(Exception):
    pass


class MyNetworkServer:
    async def handle_upstream_lora_message(self, phy_payload: bytearray):
        # Here is example of abstract LNS server logic.       
        # We are assuming LNS validates MIC using nwk_key and phy_payload. If it is wrong, MicError is raised.
        nwk_key = await self.get_nwk_key()
        if not self.validate_mic(phy_payload, nwk_key):
            raise MicError()
        ...


class MyMicChallengeWrapper:
    def __init__(self, network_server: MyNetworkServer, upstream_api: UpstreamConnection):
        self.network_server = network_server
        self.upstream_api = upstream_api

    @staticmethod
    def populate_lora_messages(upstream_message: domains.UpstreamMessage) -> List[Tuple[int, bytearray]]:
        """
        This method populates list of lora messages to be passed to the network server.
        """
        messages = []
        message_no_mic = bytearray(upstream_message.phy_payload_no_mic)
        for mic_int in upstream_message.mic_challenge:
            mic = mic_int.to_bytes(4, byteorder="big")
            messages.append((mic_int, message_no_mic + mic))
        return messages

    async def handle_upstream_message_with_mic_challenge(self, upstream_message: domains.UpstreamMessage):
        # This variable is used to track correct MIC value.
        accepted_mic = None

        # This function creates multiple phy payloads with different MICs, obtained from MIC Challenge and pass each to NS.
        # NS must raise a MicError exception if it can't verify message with this MIC.
        # In this case, this function will send next message to LNS, until it finally accepts one of them.
        for mic, lora_message_bytes in self.populate_lora_messages(upstream_message):
            try:
                await self.network_server.handle_upstream_lora_message(lora_message_bytes)
            except MicError:
                # If MIC challenge failed, we should try next MIC.
                logger.debug(f"Mic challenge attempt failed, wrong mic - {mic}")
                continue
            else:
                accepted_mic = mic
                break

        # If we have no accepted MIC, we reject the message.
        if accepted_mic is None:
            logger.warning("Mic challenge failed, sending UpstreamReject")
            self.upstream_api.send_upstream_reject(
                transaction_id=upstream_message.transaction_id,
                result_code=UpstreamRejectResultCode.MICFailed,
            )
        # If mic is accepted, we send an ACK for this message.
        else:
            logger.debug("Mic challenge successful, sending UpstreamAck")
            await self.upstream_api.send_upstream_ack(
                transaction_id=upstream_message.transaction_id,
                dev_eui=upstream_message.dev_euis[0],
                mic=accepted_mic,
            )


async def main():
    async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
        async with sdk.upstream() as upstream_api:
            # Some kind of network server
            network_server = MyNetworkServer()
            mic_challenge_wrapper = MyMicChallengeWrapper(network_server, upstream_api)

            async for upstream_message in upstream_api.stream():
                await mic_challenge_wrapper.handle_upstream_message_with_mic_challenge(upstream_message)
```

