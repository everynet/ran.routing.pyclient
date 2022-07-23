import asyncio
import typing as t
from dataclasses import dataclass

import aiohttp
from yarl import URL

from . import consts, domains
from .downstream import DownstreamConnection, DownstreamConnectionManager
from .routing_table import RoutingTable
from .upstream import UpstreamConnection, UpstreamConnectionManager


# HACK: Temporary solution to allow custom endpoints for RANAPI
@dataclass
class RanApiEndpointSchema:
    """
    Class, that represents endpoint schema for RANAPI.
    """

    routing: URL  #: Routing endpoint, defaults to :data:`.consts.ROUTING_TABLE_API_URL`.
    upstream: URL  #: Upstream endpoint, defaults to :data:`.consts.UPSTREAM_API_URL`
    downstream: URL  #: Downstream endpoint, defaults to :data:`.consts.DOWNSTREAM_API_URL`


def _default_endpoint_schema(coverage: domains.Coverage) -> RanApiEndpointSchema:
    """
    Will generate endpoint schema based on api urls from consts

    """
    return RanApiEndpointSchema(
        routing=URL(consts.ROUTING_TABLE_API_URL.format(coverage=coverage)),
        upstream=URL(consts.UPSTREAM_API_URL.format(coverage=coverage)),
        downstream=URL(consts.DOWNSTREAM_API_URL.format(coverage=coverage)),
    )


class Core:
    """
    "Core" is main object of ran-routing SDK. It allows to manage routing table, upstream and downstream.

    Core provides context manager api, so you can use it in "async with" statement.

    .. code-block:: python

        from ran.routing.core import Core

        async def main():
            async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
                # do something with core
                pass

    Also, you can use Core object by calling :meth:`.Core.connect` and :meth:`.Core.close` methods.
    It is required to close connection after use.

    .. code-block:: python

        from ran.routing.core import Core

        async def main():
            ran = Core(access_token="...")
            await ran.connect()
            # do something with core
            await ran.close()

    After connecting to API, you has an access to sdk attributes:

        * :attr:`.Core.routing_table` - :class:`.RoutingTable`
        * :attr:`.Core.upstream` - :class:`.UpstreamConnectionManager`
        * :attr:`.Core.downstream` - :class:`.DownstreamConnectionManager`


    You can access routing table by using :attr:`.Core.routing_table`.

    .. code-block:: python

        async with Core(access_token="...") as ran:
            device = await ran.routing_table.insert(dev_eui=123129, dev_addr=123)

    To use upstream api, you need to create :class:`.UpstreamConnection` object, which is returned by
    :meth:`.UpstreamConnectionManager.create_connection` method.

    .. code-block:: python

        async with Core(access_token="...") as ran:
            upstream_connection = await ran.upstream.create_connection()

    Same for downstream api. You need to create :class:`.DownstreamConnection` object, which is returned by
    :meth:`.DownstreamConnectionManager.create_connection` method.

    .. code-block:: python

        async with Core(access_token="...") as ran:
            downstream_connection = await ran.downstream.create_connection()

    """

    def __init__(
        self,
        access_token: str,
        coverage: domains.Coverage,
        endpoint_schema: t.Optional[RanApiEndpointSchema] = None,
    ):
        #: Routing table API, created by :meth:`.Core.connect`. Instance of :class:`.RoutingTable`.
        self.routing_table: RoutingTable = None  # type: ignore
        #: Upstream connection manager, created by :meth:`.Core.connect`. Instance of :class:`.UpstreamConnectionManager`.
        self.upstream: UpstreamConnectionManager = None  # type: ignore
        #: Downstream connection manager factory, created by :meth:`.Core.connect`. Instance of :class:`.DownstreamConnectionManager`.
        self.downstream: DownstreamConnectionManager = None  # type: ignore

        self.__access_token = access_token
        self.__api_endpoint_schema = (
            endpoint_schema if endpoint_schema is not None else _default_endpoint_schema(coverage)
        )
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
        self.upstream: UpstreamConnectionManager = None  # type: ignore
        self.downstream: DownstreamConnectionManager = None  # type: ignore

        self._opened.clear()
        self._closed.set()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


# FIXME: why?
core = Core


__all__ = [
    "core",
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
