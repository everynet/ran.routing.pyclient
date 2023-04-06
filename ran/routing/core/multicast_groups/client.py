import logging
import typing as t
from datetime import datetime
from http import HTTPStatus

import aiohttp
from aiohttp.client_exceptions import ContentTypeError
from yarl import URL

from ran.routing.core.domains import MulticastGroup

from . import exceptions
from .consts import ApiErrorCode


def map_error_class(error_code: ApiErrorCode) -> t.Type[exceptions.ApiError]:
    errors_map: t.Dict[str, t.Type[exceptions.ApiError]] = {
        ApiErrorCode.UNKNOWN: exceptions.ApiUnknownError,
        ApiErrorCode.UNAUTHORIZED: exceptions.ApiUnauthorizedError,
        ApiErrorCode.VALIDATION_FAILED: exceptions.ApiValidationFailedError,
        ApiErrorCode.MC_ALREADY_EXISTS: exceptions.ApiMulticastGroupAlreadyExistsError,
        ApiErrorCode.MC_NOT_FOUND: exceptions.ApiMulticastGroupNotFoundError,
        ApiErrorCode.MC_ALREADY_CONTAINS_DEVICE: exceptions.ApiMulticastGroupAlreadyContainsDeviceError,
        ApiErrorCode.DEVICE_NOT_FOUND: exceptions.ApiDeviceNotFoundError,
    }
    # In case when we could not map exception, return most general "ApiError"
    return errors_map.get(error_code, exceptions.ApiUnknownError)


def map_int(maybe_hexdecimal: t.Optional[str]) -> t.Optional[int]:
    if maybe_hexdecimal is None:
        return None

    return int(maybe_hexdecimal, 16)


class MulticastGroupsManagement:
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
    def _parse_multicast_group_dict(mg_dict: t.Dict[str, t.Any]) -> MulticastGroup:
        return MulticastGroup(
            created_at=datetime.fromisoformat(mg_dict["created_at"]),
            name=mg_dict["name"],
            addr=map_int(mg_dict["addr"]),
            devices=[map_int(d) for d in mg_dict["devices"]],
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

    async def create_multicast_group(self, name: str, addr: int) -> MulticastGroup:
        """
        Create new multicast group.

        :param name: Name of the multicast group, must be less, then 256 symbols.
        :type name: str
        :param addr: address of multicast group, which will be used to send downlinks.
        :type addr: int
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiMulticastGroupAlreadyExistsError: Raised when multicast group with same addr already exists.
        :raises ApiUnauthorizedError: When auth token is incorrect.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: Created multicast group info.
        :rtype: MulticastGroup
        """
        if not self._is_uint32(addr):
            raise exceptions.ParameterError("'addr' must be of type uint32")
        if not isinstance(name, str) or len(name) > 255:
            raise exceptions.ParameterError("'name' must can be sting, less then 255 characters")

        json_body = {"name": name, "addr": f"{addr:08x}"}
        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "create", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_group_dict = await response.json()
            return self._parse_multicast_group_dict(multicast_group_dict)

    async def update_multicast_group(
        self, addr: int, new_name: t.Optional[str] = None, new_addr: t.Optional[int] = None
    ) -> MulticastGroup:
        """
        Update multicast group. At least one of parameters 'new_name' or 'new_addr' must be provided for update.

        :param addr: Address of multicast group, which you need to update
        :type addr: int
        :param new_name: new multicast group name, defaults to None - means no update required.
        :type new_name: t.Optional[str], optional
        :param new_addr: New address of multicast group, defaults to None - means no update required.
        :type new_addr: t.Optional[int], optional
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiMulticastGroupNotFoundError: When multicast group with this addr is not found.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: Updated multicast group info.
        :rtype: MulticastGroup
        """
        if not self._is_uint32(addr):
            raise exceptions.ParameterError("'addr' must be of type uint32")

        if new_name is None and new_addr is None:
            raise exceptions.ParameterError("At least one of parameters 'name', 'addr' must be provided for update")
        json_body: t.Dict[str, t.Any] = {"addr": f"{addr:08x}", "update": {}}

        if new_name is not None:
            if not isinstance(new_name, str) or len(new_name) > 255:
                raise exceptions.ParameterError("'name' must be sting, less then 255 characters")
            json_body["update"]["name"] = new_name

        if new_addr is not None:
            if not self._is_uint32(new_addr):
                raise exceptions.ParameterError("'new_addr' must be of type uint32")
            json_body["update"]["addr"] = f"{new_addr:08x}"

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "update", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_group_dict = await response.json()
            return self._parse_multicast_group_dict(multicast_group_dict)

    async def get_multicast_groups(self, *addrs: int) -> t.List[MulticastGroup]:
        """
        Get info about multicast groups. If no "addrs" provided, will return info about all multicast groups you own.

        :param addrs: Address of multicast group, which you want to get info for.
        :type addrs: int
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: List of multicast groups info.
        :rtype: t.List[MulticastGroup]
        """
        json_body: t.Dict[str, t.List[str]] = {
            "addrs": [],
        }
        for idx, addr in enumerate(addrs):
            if not self._is_uint32(addr):
                raise exceptions.ParameterError(f"addr #{idx} must be of type uint32")
            json_body["addrs"].append(f"{addr:08x}")

        async with self._client_session.post(self.__api_path / "multicast-groups" / "get", json=json_body) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_groups = await response.json()
            return [self._parse_multicast_group_dict(mg) for mg in multicast_groups]

    async def delete_multicast_groups(self, addrs: t.List[int]) -> int:
        """
        Delete multicast group. Returns True, if multicast group deleted.
        If you provide unknown "addr" will return False.

        :param addr: Address of multicast group you want to delete.
        :type addr: int
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: Returns amount of devices deleted.
        :rtype: int
        """
        json_body: t.Dict[str, t.List[str]] = {
            "addrs": [],
        }

        for idx, addr in enumerate(addrs):
            if not self._is_uint32(addr):
                raise exceptions.ParameterError(f"addr #{idx} must be of type uint32")
            json_body["addrs"].append(f"{addr:08x}")

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "delete", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return (await response.json())["deleted"]

    async def add_device_to_multicast_group(self, addr: int, dev_eui: int) -> bool:
        """
        Add device to multicast group.

        :param addr: Address of multicast group you want to use to add device in it.
        :type addr: int
        :param dev_eui: dev_eui of device you want to add to multicast group.
        :type dev_eui: int
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiMulticastGroupNotFoundError: When no multicast group with this addr exists.
        :raises ApiDeviceNotFoundError: When you doesen't have device with this dev_eui in routing table.
        :raises ApiMulticastGroupAlreadyContainsDeviceError: when multicast group already contains device.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: Is device added to multicast group
        :rtype: bool
        """
        if not self._is_uint32(addr):
            raise exceptions.ParameterError("'addr' must be of type uint32")
        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("'dev_eui' must be of type uint64")

        json_body = {"addr": f"{addr:08x}", "dev_eui": f"{dev_eui:016x}"}
        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "add-device", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return bool((await response.json())["is_added"])

    async def remove_device_from_multicast_group(self, addr: int, dev_eui: int) -> bool:
        """
        Remove device from multicast group. If device was removed from group, will return True.
        If you provide not existing addr or dev_eui, will return False.

        :param addr: Address of multicast group you want to use to remove device from.
        :type addr: int
        :param dev_eui: dev_eui of device you want to remove from multicast group.
        :type dev_eui: int
        :raises ParameterError: Raised when passed parameter is invalid.
        :raises ApiValidationFailedError: When input data is incorrect.
        :raises ApiUnknownError: When some unknown error happened (by ex, internal server error).
        :return: Is device removed from multicast group.
        :rtype: bool
        """
        if not self._is_uint32(addr):
            raise exceptions.ParameterError("'addr' must be of type uint32")
        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("'dev_eui' must be of type uint64")

        json_body = {"addr": f"{addr:08x}", "dev_eui": f"{dev_eui:016x}"}
        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "remove-device", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return bool((await response.json())["is_removed"])
