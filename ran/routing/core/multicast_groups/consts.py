from enum import Enum


class ApiErrorCode(str, Enum):
    UNKNOWN = "Unknown"
    UNAUTHORIZED = "Unauthorized"
    VALIDATION_FAILED = "ValidationFailed"
    MC_ALREADY_EXISTS = "MulticastGroup.AlreadyExists"
    MC_NOT_FOUND = "MulticastGroup.NotFound"
    MC_ALREADY_CONTAINS_DEVICE = "MulticastGroup.AlreadyContainsTheDevice"
    DEVICE_NOT_FOUND = "Device.NotFound"
