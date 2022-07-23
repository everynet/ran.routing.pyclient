import json
import re
import typing as t
from functools import partial

from pydantic import BaseModel

from .. import domains
from .interface import ISerializer

T = t.TypeVar("T", bound=BaseModel)


# Helpers
def to_bytearray(field_name, domain_dict: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    domain_dict[field_name] = bytes(domain_dict[field_name])
    return domain_dict


def from_bytearray(field_name, domain_dict: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    domain_dict[field_name] = list(domain_dict[field_name])
    return domain_dict


def cast_keys_to_snake_case(model_dict: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    rules = {
        "DevEUI": "dev_eui",
        "DevEUIs": "dev_euis",
        "JoinEUI": "join_eui",
        "TransactionID": "transaction_id",
        "MailboxID": "mailbox_id",
        "PHYPayload": "phy_payload",
        "PHYPayloadNoMIC": "phy_payload_no_mic",
        "MIC": "mic",
        "MICChallenge": "mic_challenge",
        "LoRa": "lora",
        "FSK": "fsk",
        "FHSS": "fhss",
        "RSSI": "rssi",
        "SNR": "snr",
    }

    for key in list(model_dict.keys()):
        if key in rules:
            snake_key = rules[key]
        else:
            snake_key = re.sub("(?!^)([A-Z]+)", r"_\1", key).lower()

        val = model_dict.pop(key)
        if isinstance(val, dict):
            val = cast_keys_to_snake_case(val)

        model_dict[snake_key] = val

    return model_dict


def cast_keys_to_camel_case(model_dict: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    rules = {
        "dev_eui": "DevEUI",
        "dev_euis": "DevEUIs",
        "join_eui": "JoinEUI",
        "transaction_id": "TransactionID",
        "mailbox_id": "MailboxID",
        "phy_payload": "PHYPayload",
        "phy_payload_no_mic": "PHYPayloadNoMIC",
        "mic": "MIC",
        "mic_challenge": "MICChallenge",
        "lora": "LoRa",
        "fsk": "FSK",
        "fhss": "FHSS",
        "rssi": "RSSI",
        "snr": "SNR",
    }

    for key in list(model_dict.keys()):
        if key in rules:
            camel_key = rules[key]
        else:
            camel_key = key.title().replace("_", "")

        val = model_dict.pop(key)
        if isinstance(val, dict):
            val = cast_keys_to_camel_case(val)

        model_dict[camel_key] = val

    return model_dict


# Models
class GenericJSONSerializer(ISerializer[T]):
    def __init__(
        self,
        model: t.Type[T],
        extra_parse: t.Optional[t.Callable] = None,
        extra_serialize: t.Optional[t.Callable] = None,
    ) -> None:
        self.model = model
        self.extra_parse = extra_parse
        self.extra_serialize = extra_serialize

    def parse(self, data: t.Union[str, bytes]) -> T:
        domain_dict = cast_keys_to_snake_case(json.loads(data))

        if self.extra_parse is not None:
            domain_dict = self.extra_parse(domain_dict)

        return self.model(**domain_dict)

    def serialize(self, message: T) -> t.Union[str, bytes]:
        domain_dict = message.dict(exclude_none=True)

        if self.extra_serialize is not None:
            domain_dict = self.extra_serialize(domain_dict)

        return json.dumps(cast_keys_to_camel_case(domain_dict))


UpstreamAckMessageSerializer: GenericJSONSerializer[domains.UpstreamAckMessage] = GenericJSONSerializer(
    domains.UpstreamAckMessage
)
UpstreamRejectMessageSerializer: GenericJSONSerializer[domains.UpstreamRejectMessage] = GenericJSONSerializer(
    domains.UpstreamRejectMessage
)
UpstreamMessageSerializer: GenericJSONSerializer[domains.UpstreamMessage] = GenericJSONSerializer(
    domains.UpstreamMessage,
    extra_parse=partial(to_bytearray, "phy_payload_no_mic"),
    extra_serialize=partial(from_bytearray, "phy_payload_no_mic"),
)


DownstreamMessageSerializer: GenericJSONSerializer[domains.DownstreamMessage] = GenericJSONSerializer(
    domains.DownstreamMessage,
    extra_parse=partial(to_bytearray, "phy_payload"),
    extra_serialize=partial(from_bytearray, "phy_payload"),
)


class DownstreamAckOrResultSerializer(ISerializer):
    @staticmethod
    def parse(data: t.Union[str, bytes]) -> t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]:
        domain_dict = cast_keys_to_snake_case(json.loads(data))

        if "result_code" in domain_dict:
            model = domains.DownstreamResultMessage
        else:
            model = domains.DownstreamAckMessage  # type: ignore

        return model(**domain_dict)

    @staticmethod
    def serialize(
        message: t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]
    ) -> t.Union[str, bytes]:
        return json.dumps(cast_keys_to_camel_case(message.dict(exclude_none=True)))
