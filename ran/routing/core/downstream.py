import asyncio
import logging
import os
import typing as t
from contextlib import suppress

import aiohttp
import async_timeout
from yarl import URL

from . import consts, domains, serializers


class DownstreamConnection:
    """
    Main class, used for communication with downstream API.

    This class must not be created directly, but through :class:`ran.routing.core.Core` class, like so:

    .. code-block:: python

        async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
            async with ran.downstream() as downstream_connection:
                pass

    :param access_token: access token for downstream API
    :type access_token: str
    :param session: ClientSession object, used for communication with downstream API
    :type session: aiohttp.ClientSession
    :param api_path: downstream API path
    :type api_path: URL
    :param buffer_size: Size of internal Queue, used to store messages from ws, defaults to 1
    :type buffer_size: int
    """

    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL, buffer_size: int = 1):
        self._identifier = os.urandom(8).hex()
        self._session = session
        self.__access_token = access_token
        self.__api_path = api_path

        self._downstream_buffer: asyncio.Queue = asyncio.Queue(buffer_size)

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
            # TODO: custom exceptions
            raise Exception(f"ws[{self._identifier}] DownstreamConnection has not yet been established")

        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        elif isinstance(data, str):
            await self._ws.send_str(data)
        else:
            raise Exception(f"ws[{self._identifier}] Try to send wrong data type, expected str or bytes")

        return True

    async def send_downstream(
        self,
        transaction_id: int,
        dev_eui: int,
        tx_window: t.Union[dict, domains.TransmissionWindow],
        phy_payload: t.Union[bytes, bytearray],
        target_dev_addr: t.Optional[int] = None,
    ):
        """
        Send downstream message to downstream API. This method assembles downstream object from params and send it to
        downstream API.

        :param transaction_id: Unique transaction ID
        :type transaction_id: int
        :param dev_eui: device EUI
        :type dev_eui: int
        :param tx_window: TX window data, see domains.TxWindow
        :type tx_window: t.Union[dict, domains.TransmissionWindow]
        :param phy_payload: raw bytes of lora phy_payload
        :type phy_payload: t.Union[bytes, bytearray]
        :param target_dev_addr: Mandatory for join accept messages, defaults to None. Used to update routing table on
            ran-routing server.
        :type target_dev_addr: t.Optional[int]
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """
        downstream_obj = self._prepare_downstream_message(
            transaction_id=transaction_id,
            dev_eui=dev_eui,
            tx_window=tx_window,
            phy_payload=phy_payload,
            target_dev_addr=target_dev_addr,
        )
        return await self.send_downstream_object(downstream_obj)

    async def send_downstream_object(self, downstream_message: domains.DownstreamMessage) -> bool:
        """
        Serialize downstream message and send it to websocket.

        :param downstream_message: downstream message to send
        :type downstream_message: domains.DownstreamMessage
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """
        data = serializers.json.DownstreamMessageSerializer.serialize(downstream_message)
        return await self._send_to_ws(data)

    @staticmethod
    def _prepare_downstream_message(
        transaction_id: int,
        dev_eui: int,
        tx_window: t.Union[dict, domains.TransmissionWindow],
        phy_payload: t.Union[bytes, bytearray],
        target_dev_addr: t.Optional[int] = None,
    ) -> domains.DownstreamMessage:
        """
        Helper method to assemble downstream message object from args.

        :param transaction_id: Unique transaction ID
        :type transaction_id: int
        :param dev_eui: device EUI
        :type dev_eui: int
        :param tx_window: TX window data, see domains.TxWindow
        :type tx_window: t.Union[dict, domains.TransmissionWindow]
        :param phy_payload: raw bytes of lora phy_payload
        :type phy_payload: t.Union[bytes, bytearray]
        :param target_dev_addr: Mandatory for join accept messages, defaults to None. Used to update routing table on
            ran-routing server.
        :type target_dev_addr: t.Optional[int]
        :return: assembled downstream object
        :rtype: domains.DownstreamMessage
        """
        return domains.DownstreamMessage(
            protocol_version=consts.PROTOCOL_VERSION,
            transaction_id=transaction_id,
            dev_eui=dev_eui,
            tx_window=tx_window,
            phy_payload=phy_payload,
            target_dev_addr=target_dev_addr,
        )

    async def stream(
        self, timeout: int = 1
    ) -> t.AsyncIterator[t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]]:
        """
        Stream of downstream messages from websocket.
        This method ensures you not lose messages in case if some messages already received and stored in messages
        buffer and app must be terminated now.
        Example of graceful shutdown with "stream()"

        .. code-block:: python

            import asyncio, signal

            # Create downstream_connection way you like
            downstream_connection = create_downstream_connection()

            # Used for termination
            def stop() -> None:
                downstream_connection.stop() # Stop downstream connection

            loop = asyncio.new_event_loop()
            loop.add_signal_handler(signal.SIGTERM, stop)

            async for message in downstream_connection.stream():
                assert isinstance(message, domains.DownstreamMessage)  # not necessary, just for example
                await handle_message(message)

        :param timeout: timeout between reading attempts, defaults to 1
        :type timeout: int, optional
        :yield: domains.DownstreamMessage
        :rtype: t.AsyncIterator[domains.DownstreamMessage]
        """
        while not self._closed.is_set():
            with suppress(asyncio.TimeoutError):
                async with async_timeout.timeout(timeout):
                    yield await self._downstream_buffer.get()

        for _ in range(self._downstream_buffer.qsize()):
            yield await self._downstream_buffer.get()

    async def recv(
        self, timeout: t.Optional[int] = None
    ) -> t.Optional[t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]]:
        """
        Receives one message from downstream. Grants low-level control for message receiving flow.

        .. code-block:: python
            stopped = asyncio.Event()
            while not stopped.is_set():
                message = await downstream_connection.recv(timeout=1)

        :param timeout: timeout, defaults to None. If not set, this method will block until first received message.
        :type timeout: t.Optional[int]
        :return: Returns ACK or Result from downstream. If timeout provided, and no message received, will return None
        :rtype: t.Optional[t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]]
        """
        if timeout is None:
            return await self._downstream_buffer.get()
        with suppress(asyncio.TimeoutError):
            return await asyncio.wait_for(self._downstream_buffer.get(), timeout=timeout)
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
                f"Starting listener for downstream websocket connection {self._identifier} for {str(self.__api_path)!r}"
            )
            query_params = {"access_token": self.__access_token}
            async with self._session.ws_connect(self.__api_path, params=query_params) as ws:
                self._ws = ws
                self._opened.set()
                logging.debug(f"Downstream websocket connection {self._identifier} established")

                while not self._stop_event.is_set():
                    with suppress(asyncio.TimeoutError):  # TODO: add parse error
                        ws_msg = await ws.receive(timeout=1)

                        logging.debug(f"Received from downstream ws[{self._identifier}] message: {ws_msg}")

                        if ws_msg.type in {aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT}:
                            try:
                                downstream_ack_or_result = serializers.json.DownstreamAckOrResultSerializer.parse(
                                    ws_msg.data
                                )
                            except serializers.ValidationError as e:
                                logging.error(
                                    f"Received downstream from ws[{self._identifier}] broken message:"
                                    f" {ws_msg.data}\r\nErrors: {e.errors()}"
                                )
                                continue

                            # NOTE: this method will block thread forever if upstream_buffer is full.
                            await self._downstream_buffer.put(downstream_ack_or_result)

                        elif ws_msg.type == aiohttp.WSMsgType.CLOSED:
                            logging.warning(f"ws[{self._identifier}] Connection closed")
                            return

            logging.debug(f"Stopped listener for downstream websocket connection {self._identifier}")
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
            logging.debug(f"Closed event set for downstream websocket connection {self._identifier}")

    def close(self) -> None:
        """
        Close downstream connection.
        """
        self._stop_event.set()
        logging.debug(f"Closing downstream connection {self._identifier}")

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

            downstream_connection.close()  # Close downstream connection
            await downstream_connection.wait_closed()  # Wait until connection is closed

        :raises Exception: Raises exception if connection in not established before closing
        """
        if self._closed.is_set():
            return

        # TODO: custom exceptions
        if not self._ws:
            raise Exception(f"DownstreamConnection has not yet been established {self._identifier}")

        await self._closed.wait()

        logging.debug(f"Downstream connection closed {self._identifier}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()
        await self.wait_closed()


class DownstreamConnectionManager:
    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL):
        self.__access_token = access_token
        self.__session = session
        self.__api_path = api_path

    async def create_connection(self) -> DownstreamConnection:
        downstream_connection = DownstreamConnection(self.__access_token, self.__session, self.__api_path)
        await downstream_connection.connect()

        return downstream_connection

    def __call__(self) -> DownstreamConnection:
        return DownstreamConnection(self.__access_token, self.__session, self.__api_path)
