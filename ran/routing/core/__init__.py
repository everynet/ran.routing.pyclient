import asyncio
import typing as t
from dataclasses import dataclass

import aiohttp
from yarl import URL

from . import consts, domains
from .downstream import DownstreamConnection, DownstreamConnectionManager
from .multicast_groups import MulticastGroupsManagement
from .routing_table import RoutingTable
from .upstream import UpstreamConnection, UpstreamConnectionManager


@dataclass
class RanApiEndpointSchema:
    """
    Class, that represents endpoint schema for RANAPI.
    """

    routing: URL  #: Routing endpoint
    multicast: URL  #: Multicast group management endpoint
    upstream: URL  #: Upstream endpoint
    downstream: URL  #: Downstream endpoint

    def __post_init__(self):
        for field in ("routing", "multicast", "upstream", "downstream"):
            field_value = getattr(self, field)
            if field_value is None:
                raise ValueError(f"'{field}' field not set")
            else:
                if isinstance(field_value, str):
                    setattr(self, field, URL(self.routing))
                elif isinstance(field_value, URL):
                    continue
                else:
                    raise ValueError(f"Field '{field}' supports only str or URL instance, not {type(field_value)!r}")


def _get_service_api_url(url: t.Union[str, URL], service: consts.RanRoutingApiService) -> URL:
    try:
        return URL(url).with_scheme(consts.API_SCHEMA_MAP[service]) / consts.API_PATH_MAP[service].lstrip("/")
    except LookupError:
        raise ValueError(f"Unknown service type: {service!r}")


def _derive_url_to_endpoints_schema(url: t.Union[str, URL]) -> RanApiEndpointSchema:
    url = URL(url)
    return RanApiEndpointSchema(
        routing=_get_service_api_url(url, consts.RanRoutingApiService.ROUTING),
        multicast=_get_service_api_url(url, consts.RanRoutingApiService.MULTICAST),
        upstream=_get_service_api_url(url, consts.RanRoutingApiService.UPSTREAM),
        downstream=_get_service_api_url(url, consts.RanRoutingApiService.DOWNSTREAM),
    )


class Core:
    """
    "Core" is main object of ran-routing SDK. It allows to manage routing table, upstream and downstream.

    Core provides context manager api, so you can use it in "async with" statement.

    .. code-block:: python

        from ran.routing.core import Core

        async def main():
            async with Core(access_token="...", url="...") as ran:
                # do something with core
                pass

    Also, you can use Core object by calling :meth:`.Core.connect` and :meth:`.Core.close` methods.
    It is required to close connection after use.

    .. code-block:: python

        from ran.routing.core import Core

        async def main():
            ran = Core(access_token="...", url="...")
            await ran.connect()
            # do something with core
            await ran.close()

    After connecting to API, you has an access to sdk attributes:

        * :attr:`.Core.routing_table` - :class:`.RoutingTable`
        * :attr:`.Core.upstream` - :class:`.UpstreamConnectionManager`
        * :attr:`.Core.downstream` - :class:`.DownstreamConnectionManager`


    You can access routing table by using :attr:`.Core.routing_table`.

    .. code-block:: python

        async with Core(access_token="...", url="...") as ran:
            device = await ran.routing_table.insert(dev_eui=123129, dev_addr=123)

    To use upstream api, you need to create :class:`.UpstreamConnection` object, which is returned by
    :meth:`.UpstreamConnectionManager.create_connection` method.

    .. code-block:: python

        async with Core(access_token="...", url="...") as ran:
            upstream_connection = await ran.upstream.create_connection()

    Same for downstream api. You need to create :class:`.DownstreamConnection` object, which is returned by
    :meth:`.DownstreamConnectionManager.create_connection` method.

    .. code-block:: python

        async with Core(access_token="...", url="...") as ran:
            downstream_connection = await ran.downstream.create_connection()

    """

    def __init__(
        self,
        access_token: str,
        url: t.Optional[t.Union[str, URL]] = None,
        endpoint_schema: t.Optional[RanApiEndpointSchema] = None,
    ):
        #: Routing table API, created by :meth:`.Core.connect`. Instance of :class:`.RoutingTable`.
        self.routing_table: RoutingTable = None  # type: ignore
        #: Multicast groups management API, created by :meth:`.Core.connect`. Instance of :class:`.MulticastGroupsManagement`.
        self.multicast_groups: MulticastGroupsManagement = None  # type: ignore
        #: Upstream connection manager, created by :meth:`.Core.connect`. Instance of :class:`.UpstreamConnectionManager`.
        self.upstream: UpstreamConnectionManager = None  # type: ignore
        #: Downstream connection manager factory, created by :meth:`.Core.connect`. Instance of :class:`.DownstreamConnectionManager`.
        self.downstream: DownstreamConnectionManager = None  # type: ignore

        self.__access_token = access_token
        if url is None and endpoint_schema is None:
            raise ValueError("One of parameters 'url', 'endpoint_schema' must be provided")
        if sum([url is not None, endpoint_schema is not None]) > 1:
            raise ValueError("At most one of parameters 'url', 'endpoint_schema' can be provided")

        if url:
            self.__api_endpoint_schema = _derive_url_to_endpoints_schema(url)
        elif endpoint_schema:
            self.__api_endpoint_schema = endpoint_schema
        else:
            # Unreachable: see checks before.
            raise ValueError("Api endpoints not provided")

        self.__session: aiohttp.ClientSession = None  # type: ignore
        self._closed = asyncio.Event()
        self._opened = asyncio.Event()

    async def connect(self, raise_exception: bool = False) -> None:
        """
        Creates connection pool for API calls and creates :class:`.RoutingTable`, :class:`.UpstreamConnectionManager`
        and :class:`.DownstreamConnectionManager` objects, and assign them to attributes:

        * :attr:`.Core.routing_table` - :class:`.RoutingTable`
        * :attr:`.Core.upstream` - :class:`.UpstreamConnectionManager`
        * :attr:`.Core.downstream` - :class:`.DownstreamConnectionManager`

        After connecting, this objects is ready to use.

        :param raise_exception: Raise exception if already opened, defaults to False
        :type raise_exception: bool, optional
        :raises Exception: Raises exception if already opened and `raise_exception` is True
        """
        if self._opened.is_set():
            if raise_exception:
                raise Exception("Already opened")

            return

        self.__session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.__access_token}"})
        self.routing_table = RoutingTable(self.__session, api_path=self.__api_endpoint_schema.routing)
        self.multicast_groups = MulticastGroupsManagement(self.__session, api_path=self.__api_endpoint_schema.multicast)
        self.upstream = UpstreamConnectionManager(
            access_token=self.__access_token, session=self.__session, api_path=self.__api_endpoint_schema.upstream
        )
        self.downstream = DownstreamConnectionManager(
            access_token=self.__access_token, session=self.__session, api_path=self.__api_endpoint_schema.downstream
        )

        self._opened.set()

    async def close(self, raise_exception: bool = False) -> None:
        """
        Closes connection pool for API calls and closes all bound upstream/downstream connections.

        :param raise_exception: Raise exception if already closed, defaults to False
        :type raise_exception: bool
        :raises Exception: Raises exception if already closed and `raise_exception` is True
        """
        if raise_exception and self._closed.is_set():
            raise Exception("Already closed")

        await self.__session.close()

        self.routing_table: RoutingTable = None  # type: ignore
        self.multicast_groups: MulticastGroupsManagement = None  # type: ignore
        self.upstream: UpstreamConnectionManager = None  # type: ignore
        self.downstream: DownstreamConnectionManager = None  # type: ignore

        self._opened.clear()
        self._closed.set()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


__all__ = [
    "Core",
    "RanApiEndpointSchema",
    "RoutingTable",
    "DownstreamConnectionManager",
    "DownstreamConnection",
    "UpstreamConnectionManager",
    "UpstreamConnection",
    "consts",
    "domains",
]
