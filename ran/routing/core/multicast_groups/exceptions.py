from typing import Any, Dict, List, Optional

from .consts import ApiErrorCode


class MulticastGroupTableError(Exception):
    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Client errors


class ClientError(MulticastGroupTableError):
    """
    Exception, raised when local client error happened
    """

    pass


class ParameterError(ClientError):
    """
    Raised, when parameter validation error happened
    """

    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Api errors


class ApiError(MulticastGroupTableError):
    """
    Exception, raised when API respond with some error.
    All inheritors will have "error_description: str" and "error_code: str" attributes.

    .. code-block:: python
        from ran.routing.core.routing_table import ApiErrorCode
        from ran.routing.core.routing_table.exceptions import ApiDeviceNotFoundError, ApiError

        try:
            dev_eui = ...
            await routing_table.update(dev_eui=dev_eui, join_eui=..., target_dev_addr=...)

        # Catching some important exception:
        except ApiDeviceNotFoundError as e:
            logging.error(f"Could not update device {dev_eui} - Not found: {e.error_description}")

        # Catching general exception:
        except ApiError as e:
            if e.error_code == ApiErrorCode.UNKNOWN:
                logger.error("Some unknown error: {e.error_description}")

    """

    def __init__(self, error_description: str, error_code: ApiErrorCode) -> None:
        super().__init__(f"Api error {error_code.name!r} has occurred. Description: {error_description!r}")
        self.error_description = error_description
        self.error_code = error_code


class ApiUnknownError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.UNKNOWN)


class ApiUnauthorizedError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.UNAUTHORIZED)


class ApiValidationFailedError(ApiError):
    """
    Validation error has extra field "error_detail" with error description.
    This is validation error, returned by fastapi, it has structure like:
    [{'loc': ['body', 'DevEUI'], 'msg': '...', 'type': '...', }]
    """

    def __init__(self, error_description: str, error_detail: Optional[List[Dict[str, Any]]]) -> None:
        self.error_detail = error_detail

        super().__init__(error_description=error_description, error_code=ApiErrorCode.VALIDATION_FAILED)


class ApiMulticastGroupAlreadyExistsError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.MC_ALREADY_EXISTS)


class ApiMulticastGroupAlreadyContainsDeviceError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.MC_ALREADY_CONTAINS_DEVICE)


class ApiMulticastGroupNotFoundError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.MC_NOT_FOUND)


class ApiDeviceNotFoundError(ApiError):
    def __init__(self, error_description: str) -> None:
        super().__init__(error_description=error_description, error_code=ApiErrorCode.DEVICE_NOT_FOUND)
