import logging
import typing as t
from datetime import datetime
from http import HTTPStatus

import aiohttp
from aiohttp.client_exceptions import ContentTypeError
from yarl import URL

from ran.routing.core.domains import Device

from . import exceptions
from .consts import ApiErrorCode


def map_error_class(error_code: ApiErrorCode) -> t.Type[exceptions.ApiError]:
    errors_map: t.Dict[str, t.Type[exceptions.ApiError]] = {
        ApiErrorCode.UNKNOWN: exceptions.ApiUnknownError,
        ApiErrorCode.UNAUTHORIZED: exceptions.ApiUnauthorizedError,
        ApiErrorCode.VALIDATION_FAILED: exceptions.ApiValidationFailedError,
        ApiErrorCode.DEVICE_ALREADY_EXISTS: exceptions.ApiDeviceAlreadyExistsError,
        ApiErrorCode.DEVICES_LIMIT_EXHAUSTED: exceptions.ApiDevicesLimitExhaustedError,
        ApiErrorCode.DEVICE_NOT_FOUND: exceptions.ApiDeviceNotFoundError,
    }
    # In case when we could not map exception, return most general "ApiError"
    return errors_map.get(error_code, exceptions.ApiUnknownError)


def map_int(maybe_hexdecimal: t.Optional[str]) -> t.Optional[int]:
    if maybe_hexdecimal is None:
        return None

    return int(maybe_hexdecimal, 16)


class RoutingTable:
    def __init__(self, client_session: aiohttp.ClientSession, api_path: URL):
        self._client_session = client_session
        self.__api_path = api_path

    @staticmethod
    async def _handle_http_error(response: aiohttp.ClientResponse) -> None:
        # Equal to 400 <= response.status < 500
        if HTTPStatus.BAD_REQUEST <= response.status < HTTPStatus.INTERNAL_SERVER_ERROR:
            try:
                json_error = await response.json()
            except (ContentTypeError, TypeError, ValueError):
                logging.warning("Error decoding error message, received from server")
                raise exceptions.ApiUnknownError(await response.text())

            try:
                error_info = json_error["detail"]
                error_code = ApiErrorCode(error_info.get("error_code", ApiErrorCode.UNKNOWN.value))
                error_class = map_error_class(error_code=error_code)
                error_description = error_info.get("error_description", "<no description>")

                # If this is validation error, we must have extra field with error details
                if error_class is exceptions.ApiValidationFailedError:
                    raise error_class(  # type: ignore
                        error_description=error_description,
                        error_detail=error_info.get("error_detail", None),
                    )

                # In other case just raise exception
                raise error_class(error_description=error_description)  # type: ignore

            except (KeyError, TypeError, ValueError, AttributeError):
                logging.warning("Error extracting error details")
                raise exceptions.ApiUnknownError(str(json_error))

        raise exceptions.ApiUnknownError(await response.text())

    @staticmethod
    def _parse_device_dict(device_dict: t.Dict[str, t.Any]) -> Device:
        return Device(
            created_at=datetime.fromisoformat(device_dict["CreatedAt"]),
            dev_eui=int(device_dict["DevEUI"], 16),
            join_eui=map_int(device_dict["JoinEUI"]),
            active_dev_addr=map_int(device_dict["ActiveDevAddr"]),
            target_dev_addr=map_int(device_dict["TargetDevAddr"]),
            details=device_dict["Details"],
        )

    @staticmethod
    def _is_uint32(n: int) -> bool:
        if not isinstance(n, int):
            return False
        return 0 <= n <= 0xFFFFFFFF

    @staticmethod
    def _is_uint64(n: int) -> bool:
        if not isinstance(n, int):
            return False
        return 0 <= n <= 0xFFFFFFFFFFFFFFFF

    async def insert(self, dev_eui: int, join_eui: t.Optional[int] = None, dev_addr: t.Optional[int] = None) -> Device:
        """
        Insert device into the routing table to start receiving messages from the
        specified device.

        Both DevEUI and DevAddr are mandatory parameters for ABP devices. while DevEUI and JoinEUI are mandatory
        parameters for OTAA devices.
        Provided DevEUI must be unique, while single DevAddr may be assigned to several DevEUIs simultaneously.

        Returns device domain If successfully completed, otherwise raise exception

        :param dev_eui: Represents uint64 end-device identifier
        :type dev_eui: int
        :param join_eui: Represents uint64 unique JoinEUI.
        :type join_eui: Optional[int]
        :param dev_addr: Represents uint32 device address.
        :type dev_addr: Optional[int]
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiDeviceAlreadyExistsError: When you tries to create device with already existing "dev_eui"
        :raises ApiDevicesLimitExhaustedError:  When your account reach device creation limit
        :raises ApiUnauthorizedError: When auth token is incorrect
        :raises ApiValidationFailedError: When input data is incorrect
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error)
        :return: Created device record from the routing table.
        :rtype: Device
        """

        # Validation
        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("dev_eui must be of type uint64")

        if join_eui is None and dev_addr is None:
            raise exceptions.ParameterError(
                "One of the following values must be specified: join_eui (for OTAA device) or dev_addr (for ABP device)"
            )

        json_body = {
            "DevEUI": f"{dev_eui:016x}",
        }

        if join_eui is not None:
            if not self._is_uint64(join_eui):
                raise exceptions.ParameterError("join_eui must be of type uint64")

            json_body["JoinEUI"] = f"{join_eui:016x}"

        if dev_addr is not None:
            if not self._is_uint32(dev_addr):
                raise exceptions.ParameterError("dev_addr must be of type uint32")

            json_body["DevAddr"] = f"{dev_addr:08x}"

        async with self._client_session.post(self.__api_path / "devices" / "insert", json=json_body) as response:
            if not response.ok:
                await self._handle_http_error(response)

            device_as_dict = await response.json()
            return self._parse_device_dict(device_as_dict)

    async def select(
        self,
        dev_euis: t.Optional[t.List[int]] = None,
        offset: t.Optional[int] = None,
        limit: t.Optional[int] = None,
    ) -> t.List[Device]:
        """
        Returns list of devices is specified via DevEUIs parameter. If DevEUIs parameter is not set, then all device
        subscriptions will be returned.

        :param dev_euis: List of DevEUI uint64
        :type dev_euis: Optional[List[innt]]
        :param offset: Offset, used for pagination, defaults to None
        :type offset: Optional[int]
        :param limit: Limit, used for pagination, defaults to None
        :type limit: Optional[int]
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiUnauthorizedError: When auth token is incorrect
        :raises ApiValidationFailedError: When input data is incorrect
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error)
        :return: List of devices subscriptions from the routing table.
        :rtype: List[Device]
        """

        query_params: t.Dict[str, t.Any] = {}

        if dev_euis is not None:
            query_params["DevEUIs"] = []
            # validation
            for idx, dev_eui in enumerate(dev_euis):
                if not self._is_uint64(dev_eui):
                    raise exceptions.ParameterError(f"dev_eui #{idx} must be of type uint64")
                query_params["DevEUIs"].append(f"{dev_eui:016x}")

        if offset is not None:
            if offset < 0:
                raise exceptions.ParameterError("Offset field can't be negative")
            query_params["offset"] = offset

        if limit is not None:
            if limit < 0:
                raise exceptions.ParameterError("Limit field can't be negative")
            query_params["limit"] = limit

        async with self._client_session.get(
            self.__api_path / "devices" / "select",
            params=query_params,
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return [self._parse_device_dict(d) for d in await response.json()]

    async def update(
        self,
        dev_eui: int,
        join_eui: int,
        active_dev_addr: t.Optional[int] = None,
        target_dev_addr: t.Optional[int] = None,
    ) -> Device:
        """
        Update dev_addr for present device in a routing table by DevEUI.
        This API function is intended to update the routing table for upstream traffic for a given device.
        Optional parameters that are omitted won't be updated, null values are not allowed.

        Parameters active_dev_addr and target_dev_addr are used to handle two security contexts during the join
        procedure. The security-context is only switched after the device sends its first uplink with target_dev_addr.
        It is valid for both LoRaWAN 1.0.x and 1.1.

        At least one of ActiveDevAddr or TargetDevAddr values must be provided.

        Returns device domain If successfully completed, otherwise raise exception.

        :param dev_eui: Represents uint64 of end-device DevEUI of the updated device.
            note: Call will throws an error if device is missing from the routing table.
        :type dev_eui: int
        :param join_eui: Represents uint64 JoinEUI of the updated device.
        :type join_eui: int
        :param active_dev_addr: Represents uint32 device address. Used to update current device address.
        :type active_dev_addr: Optional[int]
        :param target_dev_addr:  Represents uint32 device address. This DevAddr was generated and sent
            to device by Join Server (via Join Accept), but NS is not informed about this change right now (by Uplink).
        :type target_dev_addr: Optional[int]
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiDeviceNotFoundError: When target device (chosen by pair "dev_eui" and "join_eui") is not found
        :raises ApiUnauthorizedError: When auth token is incorrect
        :raises ApiValidationFailedError: When input data is incorrect
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error)
        :return: List of devices subscriptions from the routing table.
        :return: Updated device subscription from the routing table.
        :rtype: Device
        """

        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("dev_eui must be of type uint64")

        if not self._is_uint64(join_eui):
            raise exceptions.ParameterError("join_eui must be of type uint64")

        json_body = {
            "DevEUI": f"{dev_eui:016x}",
            "JoinEUI": f"{join_eui:016x}",
        }

        if active_dev_addr is None and target_dev_addr is None:
            raise exceptions.ParameterError("target_dev_addr and active_dev_addr cannot be both null")

        if active_dev_addr is not None:
            if not self._is_uint32(active_dev_addr):
                raise exceptions.ParameterError("dev_addr must be of type uint32")

            json_body["ActiveDevAddr"] = f"{active_dev_addr:08x}"

        if target_dev_addr is not None:
            if not self._is_uint32(target_dev_addr):
                raise exceptions.ParameterError("target_dev_addr must be of type uint32")

            json_body["TargetDevAddr"] = f"{target_dev_addr:08x}"

        async with self._client_session.post(self.__api_path / "devices" / "update", json=json_body) as response:
            if not response.ok:
                await self._handle_http_error(response)

            device_as_dict = await response.json()
            return self._parse_device_dict(device_as_dict)

    async def delete(self, dev_euis: t.List[int]) -> int:
        """
        Delete devices by DevEUI from routing table.
        This method will not check if devices present and will return no errors, if you pass non-existing DevEUIs.
        Returns amount of deleted devices.

        :param dev_euis: List of devices EUI, which must be deleted. Each must be hex string, represents 64 bit integer
            of end-device identifier
        :type dev_euis: List[str]
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiUnauthorizedError: When auth token is incorrect
        :raises ApiValidationFailedError: When input data is incorrect
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error)
        :return: Amount of deleted devices
        :rtype: int
        """
        json_body: t.Dict[str, t.List[str]] = {
            "DevEUIs": [],
        }

        for idx, dev_eui in enumerate(dev_euis):
            if not self._is_uint64(dev_eui):
                raise exceptions.ParameterError(f"dev_eui #{idx} must be of type uint64")
            json_body["DevEUIs"].append(f"{dev_eui:016x}")

        async with self._client_session.post(self.__api_path / "devices" / "drop", json=json_body) as response:
            if not response.ok:
                await self._handle_http_error(response)

            result = await response.json()
            return result["deleted"]

    async def delete_all(self) -> int:
        """
        Delete all devices.
        Returns amount of deleted devices.

        :raises ApiUnauthorizedError: When auth token is incorrect
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error)
        :return: Amount of deleted devices
        :rtype: int
        """

        async with self._client_session.post(self.__api_path / "devices" / "drop-all") as response:
            if not response.ok:
                await self._handle_http_error(response)

            result = await response.json()
            return result["deleted"]
