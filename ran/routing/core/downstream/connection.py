import asyncio
import logging
import os
import typing as t
from contextlib import suppress

import aiohttp
import async_timeout
from yarl import URL

from ran.routing.core import domains, serializers

from . import consts, exceptions


class DownstreamConnectionError(Exception):
    pass


class DownstreamConnection:
    """
    Main class, used for communication with downstream API.

    This class must not be created directly, but through :class:`ran.routing.core.Core` class, like so:

    .. code-block:: python

        async with Core(access_token="...", url="...") as ran:
            async with ran.downstream() as downstream_connection:
                pass

    :param access_token: access token for downstream API
    :type access_token: str
    :param session: ClientSession object, used for communication with downstream API
    :type session: aiohttp.ClientSession
    :param api_path: downstream API path
    :type api_path: URL
    :param buffer_size: Size of internal Queue, used to store messages from ws
        recommended value is at least the number of workers reading data from the stream
    :type buffer_size: int
    """

    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL, buffer_size: int):
        self._identifier = os.urandom(8).hex()
        self._session = session
        self.__access_token = access_token
        self.__api_path = api_path

        self._downstream_buffer: asyncio.Queue = asyncio.Queue(buffer_size)

        self._listener_task: t.Optional[asyncio.Future] = None

        self._stop_event = asyncio.Event()
        self._closed: asyncio.Future[t.Optional[str]] = asyncio.Future()
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
        if self.is_closed() or self._ws is None:
            raise exceptions.DownstreamConnectionClosed(
                f"ws[{self._identifier}] DownstreamConnection has not yet been established"
            )

        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        elif isinstance(data, str):
            await self._ws.send_str(data)
        else:
            raise exceptions.DownstreamError(
                f"ws[{self._identifier}] Try to send wrong data type, expected str or bytes"
            )

        return True

    def _raise_on_closed(self, force_raise_if_closed: bool = False) -> t.Optional[t.NoReturn]:
        if self.is_closed():
            close_result = self._closed.result()
            if close_result is None:
                if force_raise_if_closed:
                    raise exceptions.DownstreamConnectionClosedOk("Connection closed")
                return None
            else:
                raise exceptions.DownstreamConnectionClosedAbnormally(close_result)
        return None

    async def send_multicast_downstream(
        self,
        transaction_id: int,
        addr: int,
        tx_window: t.Union[dict, domains.TransmissionWindow],
        phy_payload: t.Union[bytes, bytearray],
    ):
        """
        Send multicast downstream message to downstream API. This method assembles downstream object from params and
        send it to downstream API.

        :param transaction_id: Unique transaction ID
        :type transaction_id: int
        :param addr: Address of multicast group uint32
        :type addr: int
        :param tx_window: TX window data, see domains.TxWindow
        :type tx_window: t.Union[dict, domains.TransmissionWindow]
        :param phy_payload: raw bytes of lora phy_payload
        :type phy_payload: t.Union[bytes, bytearray]
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """

        multicast_downstream_obj = domains.MulticastDownstreamMessage(
            protocol_version=consts.PROTOCOL_VERSION,
            transaction_id=transaction_id,
            addr=addr,
            tx_window=tx_window,
            phy_payload=phy_payload,
        )

        return await self.send_multicast_downstream_object(multicast_downstream_obj)

    async def send_multicast_downstream_object(
        self, multicast_downstream_message: domains.MulticastDownstreamMessage
    ) -> bool:
        """
        Serialize multicast downstream message and send it to websocket.

        :param multicast_downstream_message: downstream message to send
        :type multicast_downstream_message: domains.DownstreamMessage
        :return: Return True on successful sending, otherwise raise exception
        :rtype: bool
        """
        data = serializers.json.MulticastDownstreamMessageSerializer.serialize(multicast_downstream_message)
        return await self._send_to_ws(data)

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
        while not self.is_closed():
            with suppress(asyncio.TimeoutError):
                data_message = None
                async with async_timeout.timeout(timeout):
                    data_message = await self._downstream_buffer.get()
                if data_message is not None:
                    yield data_message

        # Read all items from buffer, when stream already closed.
        for _ in range(self._downstream_buffer.qsize()):
            yield await self._downstream_buffer.get()

    async def recv(
        self, timeout: t.Optional[int] = None
    ) -> t.Optional[t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]]:
        """
        Receives one message from downstream. Grants low-level control for message receiving flow.
        If "recv()" method is called without established connection, an exception will be raised.
        If the connection is closed during the "recv()" call (without timeout), an exception will be raised.
        If some connection error happened during "recv()" call (without timeout), an exception will be raised.

        .. code-block:: python
            stopped = asyncio.Event()
            while not stopped.is_set():
                message = await downstream_connection.recv(timeout=1)

        :param timeout: timeout, defaults to None. If not set, this method will block until first received message.
        :type timeout: t.Optional[int]
        :return: Returns ACK or Result from downstream. If timeout provided, and no message received, will return None
        :rtype: t.Optional[t.Union[domains.DownstreamAckMessage, domains.DownstreamResultMessage]]
        """

        # If messages are already in buffer - return them. In other case - check closed state and raise an exception.
        if not self._downstream_buffer.empty():
            return await self._downstream_buffer.get()

        if timeout is None:
            recv_data_task = asyncio.create_task(self._downstream_buffer.get())

            _, pending = await asyncio.wait(
                {asyncio.create_task(self.wait_closed()), recv_data_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            pending_task = pending.pop()
            pending_task.cancel()

            try:
                await pending_task
            except asyncio.CancelledError:
                pass

            if pending_task != recv_data_task:
                return recv_data_task.result()

        else:
            with suppress(asyncio.TimeoutError):
                return await asyncio.wait_for(self._downstream_buffer.get(), timeout=timeout)

        return self._raise_on_closed(force_raise_if_closed=True)

    async def connect(self) -> None:
        """
        Creates task, which opens websocket connections and start to listen for new messages.
        Without this task, "stream()" method will not produce messages.
        This method will not block code execution, because it only manages background task.
        """

        if self.is_opened() or self.is_closed():
            raise exceptions.DownstreamError("Connection already established or closed")

        listener_task = asyncio.create_task(self._listener())

        _, pending = await asyncio.wait(
            {listener_task, asyncio.create_task(self._opened.wait())},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If listener stopped then cancel waiter and raise exception
        pending_task = pending.pop()
        if pending_task != listener_task:
            pending_task.cancel()

            # Waiting until task cancelled
            try:
                await pending_task
            except asyncio.CancelledError:
                pass

            # If listener task raised exception then reraise it, otherwise raise DownstreamConnecetionCloseError
            exception = listener_task.exception()
            if exception:
                raise exception

            return self._raise_on_closed()

    async def _listener(self) -> None:
        close_result: t.Optional[str] = None

        try:
            logging.debug(
                f"Starting listener for downstream websocket connection ws[{self._identifier}] to"
                f" {str(self.__api_path)!r}"
            )
            query_params = {"access_token": self.__access_token}
            async with self._session.ws_connect(self.__api_path, params=query_params) as ws:
                self._ws = ws
                self._opened.set()
                logging.debug(f"Downstream websocket connection ws[{self._identifier}] established")

                while not self._stop_event.is_set():
                    with suppress(asyncio.TimeoutError):
                        ws_msg = await ws.receive(timeout=1)

                        logging.debug(f"Received from downstream ws[{self._identifier}] message: {ws_msg}")
                        if ws_msg.type in {aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT}:
                            try:
                                downstream = serializers.json.DownstreamAckOrResultSerializer.parse(ws_msg.data)
                            except serializers.ValidationError as e:
                                logging.error(
                                    f"Received downstream from ws[{self._identifier}] broken message:"
                                    f" {ws_msg.data}\r\nErrors: {e.errors()}"
                                )
                                continue

                            # NOTE: this method will block thread forever if downstream_buffer is full.
                            await self._downstream_buffer.put(downstream)
                        elif ws_msg.type == aiohttp.WSMsgType.CLOSE:
                            close_result = (
                                f"Connection closed with ws closed_code: {ws_msg.data}; reason: {ws_msg.extra}"
                            )
                        elif ws_msg.type == aiohttp.WSMsgType.CLOSED:
                            if close_result is None:
                                close_result = "Connection closed due to unknown network reason"
                            logging.warning(f"ws[{self._identifier}] Connection closed")
                            return

            logging.debug(f"Stopped listener for downstream websocket connection ws[{self._identifier}]")
        except aiohttp.client_exceptions.WSServerHandshakeError as e:
            if e.status == 401:
                close_result = "Unauthorized. Incorrect access_token sent."

                logging.error(f"Unauthorized. Incorrect access_token sent. ws[{self._identifier}]")
            else:
                close_result = f"Connection closed due to unhandled handshake error: {e}"

                logging.exception(
                    f"Catch unhandled handshake error in listener of websocket connection ws[{self._identifier}]:"
                )
        except aiohttp.ClientConnectionError as e:
            logging.exception(f"Catch unhandled error in listener of websocket connection ws[{self._identifier}]:")
            close_result = f"Connection closed due to {e}"
            logging.error(f"aiohttp.ClientSession closed: {e}")
        except Exception:
            close_result = "Connection closed due to internal error"
            raise
        finally:
            self._opened.clear()
            self._ws = None
            self._closed.set_result(close_result)

            logging.debug(f"Closed event set for downstream websocket connection ws[{self._identifier}]")

    def close(self) -> None:
        """
        Close downstream connection.
        """
        self._stop_event.set()
        logging.debug(f"Closing downstream connection ws[{self._identifier}]")

    def is_opened(self) -> bool:
        """
        Method returns True if connection is opened.

        :return: Is connection closed
        :rtype: bool
        """
        return self._opened.is_set()

    def is_closed(self) -> bool:
        """
        Method returns True if connection is closed.

        :return: Is connection closed
        :rtype: bool
        """
        return self._closed.done()

    async def wait_closed(self) -> None:
        """
        Method waits until connection is closed.

        .. code-block:: python

            downstream_connection.close()  # Close downstream connection
            await downstream_connection.wait_closed()  # Wait until connection is closed

        :raises Exception: Raises exception if connection in not established before closing
        """
        if self.is_closed():
            return

        # TODO: custom exceptions
        if not self._ws:
            raise Exception(f"DownstreamConnection has not yet been established ws[{self._identifier}]")

        await self._closed
        logging.debug(f"Downstream connection closed ws[{self._identifier}]")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()
        await self.wait_closed()
