import asyncio
import logging
import os
import typing as t
from contextlib import suppress

import aiohttp
import async_timeout
from yarl import URL

from . import consts, domains, serializers


class UpstreamConnection:
    """
    Main class, used for communication with upstream API.

    This class must not be created directly, but through :class:`ran.routing.core.Core` class, like so:

    .. code-block:: python

        async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
            async with ran.upstream() as upstream_connection:
                pass

    :param access_token: access token for upstream API
    :type access_token: str
    :param session: ClientSession object, used for communication with upstream API
    :type session: aiohttp.ClientSession
    :param api_path: upstream API path
    :type api_path: URL
    :param buffer_size: Size of internal Queue, used to store messages from ws, defaults to 1
    :type buffer_size: int
    """

    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL, buffer_size: int = 1):
        self._identifier = os.urandom(8).hex()
        self._session = session
        self.__access_token = access_token
        self.__api_path = api_path

        self._upstream_buffer: asyncio.Queue = asyncio.Queue(buffer_size)

        self._listener_task: t.Optional[asyncio.Future] = None

        self._stop_event = asyncio.Event()
        self._closed = asyncio.Event()
        self._opened = asyncio.Event()
        self._ws: t.Optional[aiohttp.client.ClientWebSocketResponse] = None

    async def _send_to_ws(self, data: t.Union[str, bytes]) -> bool:
        """
        Send raw data to websocket.

        :param data: raw data to send
        :type data: t.Union[str, bytes]
        :raises Exception: when websocket is not connected or data format is invalid
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """
        if self._ws is None:
            raise Exception(f"ws[{self._identifier}] UpstreamConnection has not yet been established")

        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        elif isinstance(data, str):
            await self._ws.send_str(data)
        else:
            raise Exception(f"ws[{self._identifier}] Try to send wrong data type, expected str or bytes")

        logging.debug(f"ws[{self._identifier}] send data {data}")  # type: ignore

        return True

    async def send_upstream_ack(self, transaction_id: int, dev_eui: int, mic: int) -> bool:
        """
        Send UpstreamAck message. Must be called after successful upstream message processing.

        .. code-block:: python

            async for message in upstream_connection.stream():
                try:
                    dev_eui, mic = await handle_message(message)  # This function handles MIC challenge and returns
                                                                  # device EUI and correct MIC
                except Exception:
                    handle_exception()
                else:
                    await upstream_connection.send_upstream_ack(message.transaction_id, dev_eui, mic)

        :param transaction_id: Unique Upstream message identifier. Must be same as in upstream message.
        :type transaction_id: int
        :param dev_eui: LoRaWAN DevEUI
        :type dev_eui: int
        :param mic: correct MIC, obtained after solving MIC-challenge
        :type mic: int
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """

        upstream_ack = domains.UpstreamAckMessage(
            protocol_version=consts.PROTOCOL_VERSION, transaction_id=transaction_id, dev_eui=dev_eui, mic=mic
        )
        data = serializers.json.UpstreamAckMessageSerializer.serialize(upstream_ack)

        return await self._send_to_ws(data)

    async def send_upstream_reject(self, transaction_id: int, result_code: domains.UpstreamRejectResultCode) -> bool:
        """
        Send UpstreamReject message. Must be called after failed upstream message processing.
        If UpstreamReject message is sent, then UpstreamAck message will not be sent.

        Main usage of this method, is notify upstream API about unsolved MIC challenge.

        .. code-block:: python

            async for message in upstream_connection.stream():
                try:
                    await handle_message(message)
                except MicChallengeError:  # This is custom exception for example
                    await upstream_connection.send_upstream_reject(
                        message.transaction_id, UpstreamRejectResultCode.MICFailed
                    )

        :param transaction_id: Unique Upstream message identifier. Must be same as in upstream message.
        :type transaction_id: int
        :param result_code: reason of rejecting upstream message.
        :type result_code: domains.UpstreamRejectResultCode
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """

        upstream_reject = domains.UpstreamRejectMessage(
            protocol_version=consts.PROTOCOL_VERSION, transaction_id=transaction_id, result_code=result_code
        )
        data = serializers.json.UpstreamRejectMessageSerializer.serialize(upstream_reject)

        return await self._send_to_ws(data)

    async def stream(self, timeout: int = 1) -> t.AsyncGenerator[domains.UpstreamMessage, None]:
        """
        Stream of upstream messages from websocket.
        This method ensures you not lose messages in case if some messages already received and stored in messages
        buffer and app must be terminated now.
        Example of graceful shutdown with "stream()"

        .. code-block:: python

            import asyncio, signal

            # Create upstream_connection way you like
            upstream_connection = create_upstream_connection()

            # Used for termination
            def stop() -> None:
                upstream_connection.stop() # Stop upstream connection

            loop = asyncio.new_event_loop()
            loop.add_signal_handler(signal.SIGTERM, stop)

            async for message in upstream_connection.stream():
                assert isinstance(message, domains.UpstreamMessage)  # not necessary, just for example
                await handle_message(message)

        :param timeout: timeout between reading attempts, defaults to 1
        :type timeout: int, optional
        :yield: domains.UpstreamMessage
        :rtype: t.AsyncIterator[domains.UpstreamMessage]
        """
        while not self._closed.is_set():
            with suppress(asyncio.TimeoutError):
                async with async_timeout.timeout(timeout):
                    yield await self._upstream_buffer.get()

        for _ in range(self._upstream_buffer.qsize()):
            yield await self._upstream_buffer.get()

    async def recv(self, timeout: t.Optional[int] = None) -> t.Optional[domains.UpstreamMessage]:
        """
        Receives one message from upstream. Grants low-level control for message receiving flow.

        .. code-block:: python
            stopped = asyncio.Event()
            while not stopped.is_set():
                message = await upstream_connection.recv(timeout=1)

        :param timeout: timeout, defaults to None. If not set, this method will block until first received message.
        :type timeout: t.Optional[int]
        :return: Returns upstream message. If timeout provided, and no message received, will return None
        :rtype: t.Optional[domains.UpstreamMessage]
        """
        if timeout is None:
            return await self._upstream_buffer.get()
        with suppress(asyncio.TimeoutError):
            return await asyncio.wait_for(self._upstream_buffer.get(), timeout=timeout)
        return None

    async def connect(self) -> None:
        """
        Creates task, which opens websocket connections and start to listen for new messages.
        Without this task, "stream()" method will not produce messages.
        This method will not block code execution, because it only manages background task.
        """
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listener())

        done, pending = await asyncio.wait(
            {asyncio.create_task(self._closed.wait()), asyncio.create_task(self._opened.wait())},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Extract pending task and cancel it
        task = pending.pop()
        task.cancel()

        # Waiting until task cancelled
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _listener(self) -> None:
        try:
            logging.debug(
                f"Starting listener for upstream websocket connection {self._identifier} for {str(self.__api_path)!r}"
            )
            query_params = {"access_token": self.__access_token}
            async with self._session.ws_connect(self.__api_path, params=query_params) as ws:
                self._ws = ws
                self._opened.set()
                logging.debug(f"Upstream websocket connection {self._identifier} established")

                while not self._stop_event.is_set():
                    with suppress(asyncio.TimeoutError):  # TODO: add parse error
                        ws_msg = await ws.receive(timeout=1)

                        logging.debug(f"Received from upstream ws[{self._identifier}] message: {ws_msg}")
                        if ws_msg.type in {aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT}:
                            try:
                                upstream = serializers.json.UpstreamMessageSerializer.parse(ws_msg.data)
                            except serializers.ValidationError as e:
                                logging.error(
                                    f"Received upstream from ws[{self._identifier}] broken message:"
                                    f" {ws_msg.data}\r\nErrors: {e.errors()}"
                                )
                                continue

                            # NOTE: this method will block thread forever if upstream_buffer is full.
                            await self._upstream_buffer.put(upstream)

                        elif ws_msg.type == aiohttp.WSMsgType.CLOSED:
                            logging.warning(f"ws[{self._identifier}] Connection closed")
                            return

            logging.debug(f"Stopped listener for upstream websocket connection {self._identifier}")
        except aiohttp.client_exceptions.WSServerHandshakeError as e:
            if e.status == 401:
                logging.error(f"Unauthorized. Incorrect access_token sent. {self._identifier}")
            else:
                logging.exception(
                    f"Catch unhandled handshake error in listener of websocket connection {self._identifier}:"
                )
        except (aiohttp.ClientConnectionError, RuntimeError) as e:
            logging.error(f"aiohttp.ClientSession closed: {e}")
        except Exception:
            logging.exception(f"Catch unhandled exception in listener of websocket connection {self._identifier}:")
        finally:
            self._ws = None
            self._closed.set()
            logging.debug(f"Closed event set for upstream websocket connection {self._identifier}")

    def close(self) -> None:
        """
        Close upstream connection.
        """
        self._stop_event.set()
        logging.debug(f"Closing upstream connection {self._identifier}")

    def is_closed(self) -> bool:
        """
        Method returns True if connection is closed.

        :return: Is connection closed
        :rtype: bool
        """
        return self._closed.is_set()

    async def wait_closed(self) -> None:
        """
        Method waits until connection is closed.

        .. code-block:: python

            upstream_connection.close()  # Close upstream connection
            await upstream_connection.wait_closed()  # Wait until connection is closed

        :raises Exception: Raises exception if connection in not established before closing
        """
        if self._closed.is_set():
            return

        # TODO: custom exceptions
        if not self._ws:
            raise Exception(f"UpstreamConnection has not yet been established {self._identifier}")

        await self._closed.wait()
        logging.debug(f"Upstream connection closed {self._identifier}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()
        await self.wait_closed()


class UpstreamConnectionManager:
    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL):
        self.__access_token = access_token
        self.__session = session
        self.__api_path = api_path

    async def create_connection(self) -> UpstreamConnection:
        upstream_connection = UpstreamConnection(self.__access_token, self.__session, self.__api_path)
        await upstream_connection.connect()

        return upstream_connection

    def __call__(self) -> UpstreamConnection:
        return UpstreamConnection(self.__access_token, self.__session, self.__api_path)
