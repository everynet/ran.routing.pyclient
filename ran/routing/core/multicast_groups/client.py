import logging
import typing as t
from datetime import datetime
from http import HTTPStatus

import aiohttp
from aiohttp.client_exceptions import ContentTypeError
from yarl import URL

from ..domains import MulticastGroup
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

            except (KeyError, TypeError, ValueError):
                logging.warning("Error extracting error details")
                raise exceptions.ApiUnknownError(str(json_error))

        raise exceptions.ApiUnknownError(await response.text())

    @staticmethod
    def _parse_multicast_group_dict(mg_dict: t.Dict[str, t.Any]) -> MulticastGroup:
        return MulticastGroup(
            id=mg_dict["id"],
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

    async def create_multicast_group(self, name: str, addr: int):
        if not self._is_uint32(addr):
            raise exceptions.ParameterError("'addr' must be of type uint32")
        if not isinstance(name, str) or len(name) > 255:
            raise exceptions.ParameterError("'name' must can be sting, less then 255 characters")

        json_body = {
            "name": name,
            "addr": f"{int(addr):08x}",
        }

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "create", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_group_dict = await response.json()
            return self._parse_multicast_group_dict(multicast_group_dict)

    async def update_multicast_group(
        self, multicast_group_id: int, name: t.Optional[str] = None, addr: t.Optional[int] = None
    ) -> MulticastGroup:
        if name is None and addr is None:
            raise exceptions.ParameterError("At least one of parameters 'name', 'addr' must be provided for update")
        json_body: t.Dict[str, t.Any] = {"id": multicast_group_id}

        if name is not None:
            if not isinstance(name, str) or len(name) > 255:
                raise exceptions.ParameterError("'name' must can be sting, less then 255 characters")
            json_body["name"] = name

        if addr is not None:
            if not self._is_uint32(addr):
                raise exceptions.ParameterError("'addr' must be of type uint32")
            json_body["addr"] = f"{int(addr):08x}"

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "update", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_group_dict = await response.json()
            return self._parse_multicast_group_dict(multicast_group_dict)

    async def get_multicast_groups(self, *multicast_group_id: int) -> t.List[MulticastGroup]:
        for idx, group_id in enumerate(multicast_group_id):
            if not isinstance(group_id, int):
                raise exceptions.ParameterError(f"multicast_group_id #{idx} must be of type int")

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "get", json={"ids": list(multicast_group_id)}
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            multicast_groups = await response.json()
            return [self._parse_multicast_group_dict(mg) for mg in multicast_groups]

    async def delete_multicast_group(self, multicast_group_id: int) -> bool:
        if not isinstance(multicast_group_id, int):
            raise exceptions.ParameterError("multicast_group_id must be of type int")

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "delete", json={"id": multicast_group_id}
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return bool((await response.json())["deleted"])

    async def add_device_to_multicast_group(self, multicast_group_id: int, dev_eui: int) -> bool:
        if not isinstance(multicast_group_id, int):
            raise exceptions.ParameterError("multicast_group_id must be of type int")

        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("'dev_eui' must be of type uint64")
        json_body = {"multicast_group_id": multicast_group_id, "dev_eui": f"{dev_eui:016x}"}

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "add-device", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return bool((await response.json())["is_created"])

    async def remove_device_from_multicast_group(self, multicast_group_id: int, dev_eui: int) -> bool:
        if not isinstance(multicast_group_id, int):
            raise exceptions.ParameterError("multicast_group_id must be of type int")

        if not self._is_uint64(dev_eui):
            raise exceptions.ParameterError("'dev_eui' must be of type uint64")
        json_body = {"multicast_group_id": multicast_group_id, "dev_eui": f"{dev_eui:016x}"}

        async with self._client_session.post(
            self.__api_path / "multicast-groups" / "remove-device", json=json_body
        ) as response:
            if not response.ok:
                await self._handle_http_error(response)

            return bool((await response.json())["is_deleted"])
