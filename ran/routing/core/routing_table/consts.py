from enum import Enum


# All possible error codes enumeration
class ApiErrorCode(str, Enum):
    UNKNOWN = "Unknown"
    UNAUTHORIZED = "Unauthorized"
    VALIDATION_FAILED = "ValidationFailed"
    DEVICE_ALREADY_EXISTS = "Device.AlreadyExists"
    DEVICES_LIMIT_EXHAUSTED = "Device.LimitExhausted"
    DEVICE_NOT_FOUND = "Device.NotFound"
