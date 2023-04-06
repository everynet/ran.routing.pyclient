import aiohttp
from yarl import URL

from .connection import UpstreamConnection


class UpstreamConnectionManager:
    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL):
        self.__access_token = access_token
        self.__session = session
        self.__api_path = api_path

    async def create_connection(self, buffer_size: int = 1) -> UpstreamConnection:
        upstream_connection = UpstreamConnection(
            self.__access_token, self.__session, self.__api_path, buffer_size=buffer_size
        )
        await upstream_connection.connect()

        return upstream_connection

    def __call__(self, buffer_size: int = 1) -> UpstreamConnection:
        return UpstreamConnection(self.__access_token, self.__session, self.__api_path, buffer_size=buffer_size)
