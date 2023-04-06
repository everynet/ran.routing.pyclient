import typing as t
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, conint, conlist, constr, root_validator, validator


class UpstreamRejectResultCode(str, Enum):
    MICFailed = "MICFailed"
    Other = "Other"


class Device(BaseModel):
    created_at: datetime
    dev_eui: conint(ge=0, le=0xFFFFFFFFFFFFFFFF)
    join_eui: t.Optional[conint(ge=0, le=0xFFFFFFFFFFFFFFFF)]
    active_dev_addr: t.Optional[conint(ge=0, le=0xFFFFFFFF)]
    target_dev_addr: t.Optional[conint(ge=0, le=0xFFFFFFFF)]
    details: t.Optional[str]

    @root_validator
    def extra_constrains(cls, values):
        if values.get("join_eui") is None and values.get("active_dev_addr") is None:
            raise ValueError(
                "One of the following values must be specified: JoinEUI (for OTAA device) or DevAddr (for ABP device)"
            )
        return values


class MulticastGroup(BaseModel):
    addr: int
    created_at: datetime
    name: constr(max_length=255)
    devices: t.List[int]


#################
# RADIO DOMAINS #
#################
class LoRaModulation(BaseModel):
    spreading: conint(ge=0, le=12)
    bandwidth: conint(ge=0)


class FSKModulation(BaseModel):
    frequency_deviation: conint(ge=0)
    bit_rate: conint(ge=0)


class FHSSModulation(BaseModel):
    ocw: conint(ge=0)
    coding_rate: str


class BaseRadio(BaseModel):
    frequency: conint(ge=0)
    lora: t.Optional[LoRaModulation]
    fsk: t.Optional[FSKModulation]
    fhss: t.Optional[FHSSModulation]

    @root_validator
    def extra_constrains(cls, values):
        modulations = [values["lora"], values["fsk"], values["fhss"]]

        if len([m for m in modulations if m is not None]) != 1:
            raise ValueError("One and only one type of modulation must be present")

        return values


####################
# UPSTREAM DOMAINS #
####################
class UpstreamRadio(BaseRadio):
    rssi: float
    snr: float


class Gps(BaseModel):
    lat: float
    lng: float
    alt: t.Optional[float]


class UpstreamMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    outdated: t.Optional[bool]
    dev_euis: t.List[conint(ge=0, le=0xFFFFFFFFFFFFFFFF)]
    radio: UpstreamRadio
    phy_payload_no_mic: t.Union[bytes, t.List[conint(ge=0, le=0xFF)]]
    mic_challenge: t.List[conint(ge=0, le=0xFFFFFFFF)]
    gps: t.Optional[Gps]

    @validator("phy_payload_no_mic")
    def payload_to_bytes(cls, v):
        if isinstance(v, list):
            return bytes(v)

        return v


class UpstreamAckMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    dev_eui: conint(ge=0, le=0xFFFFFFFFFFFFFFFF)
    mic: conint(ge=0, le=0xFFFFFFFF)


class UpstreamRejectMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    result_code: UpstreamRejectResultCode
    result_message: t.Optional[str]


######################
# DOWNSTREAM DOMAINS #
######################
class DownstreamResultCode(str, Enum):
    Success = "Success"
    WindowNotFound = "WindowNotFound"
    GatewayNotFound = "GatewayNotFound"
    TooLate = "TooLate"
    NoAck = "NoAck"
    GatewayError = "GatewayError"


class DownstreamRadio(BaseRadio):
    pass


class TransmissionWindow(BaseModel):
    radio: DownstreamRadio
    delay: t.Optional[conint(gt=0, lt=16)]
    tmms: t.Optional[conlist(int, min_items=1)]
    deadline: t.Optional[conint(gt=0)]

    @root_validator
    def extra_constrains(cls, values):
        one_of = [values["delay"], values["tmms"], values["deadline"]]

        if len([m for m in one_of if m is not None]) != 1:
            raise ValueError("One and only one type of modulation must be present")

        return values


class DownstreamMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    dev_eui: conint(ge=0, le=0xFFFFFFFFFFFFFFFF)
    target_dev_addr: t.Optional[conint(ge=0, le=0xFFFFFFFF)]
    tx_window: TransmissionWindow
    phy_payload: bytes


class MulticastDownstreamMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    addr: conint(ge=0, le=0xFFFFFFFF)
    tx_window: TransmissionWindow
    phy_payload: bytes


class DownstreamAckMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    mailbox_id: conint(gt=0)  # RFU


class DownstreamResultMessage(BaseModel):
    protocol_version: conint(gt=0)
    transaction_id: conint(gt=0)
    result_code: DownstreamResultCode
    result_message: str
    mailbox_id: conint(gt=0)
