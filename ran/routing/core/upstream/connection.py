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


class UpstreamConnection:
    """
    Main class, used for communication with upstream API.

    This class must not be created directly, but through :class:`ran.routing.core.Core` class, like so:

    .. code-block:: python

        async with Core(access_token="...", url="...") as ran:
            async with ran.upstream() as upstream_connection:
                pass

    :param access_token: access token for upstream API
    :type access_token: str
    :param session: ClientSession object, used for communication with upstream API
    :type session: aiohttp.ClientSession
    :param api_path: upstream API path
    :type api_path: URL
    :param buffer_size: Size of internal Queue, used to store messages from ws,
        recommended value is at least the number of workers reading data from the stream
    :type buffer_size: int
    """

    def __init__(self, access_token: str, session: aiohttp.ClientSession, api_path: URL, buffer_size: int):
        self._identifier = os.urandom(8).hex()
        self._session = session
        self.__access_token = access_token
        self.__api_path = api_path

        self._upstream_buffer: asyncio.Queue = asyncio.Queue(buffer_size)

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
            raise exceptions.UpstreamConnectionClosed(
                f"ws[{self._identifier}] UpstreamConnection has not yet been established"
            )

        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        elif isinstance(data, str):
            await self._ws.send_str(data)
        else:
            raise exceptions.UpstreamError(f"ws[{self._identifier}] Try to send wrong data type, expected str or bytes")

        logging.debug(f"ws[{self._identifier}] send data {data}")  # type: ignore

        return True

    def _raise_on_closed(self, force_raise_if_closed: bool = False) -> t.Optional[t.NoReturn]:
        if self.is_closed():
            close_result = self._closed.result()
            if close_result is None:
                if force_raise_if_closed:
                    raise exceptions.UpstreamConnectionClosedOk("Connection closed")
                return None
            else:
                raise exceptions.UpstreamConnectionClosedAbnormally(close_result)
        return None

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
        while not self.is_closed():
            with suppress(asyncio.TimeoutError):
                data_message = None
                async with async_timeout.timeout(timeout):
                    data_message = await self._upstream_buffer.get()
                if data_message is not None:
                    yield data_message

        # Read all items from buffer, when stream already closed.
        for _ in range(self._upstream_buffer.qsize()):
            yield await self._upstream_buffer.get()

    async def recv(self, timeout: t.Optional[int] = None) -> t.Optional[domains.UpstreamMessage]:
        """
        Receives one message from upstream. Grants low-level control for message receiving flow.
        If "recv()" method is called without established connection, an exception will be raised.
        If the connection is closed during the "recv()" call (without timeout), an exception will be raised.
        If some connection error happened during "recv()" call (without timeout), an exception will be raised.

        .. code-block:: python
            stopped = asyncio.Event()
            while not stopped.is_set():
                message = await upstream_connection.recv(timeout=1)

        :param timeout: timeout, defaults to None. If not set, this method will block until first received message.
        :type timeout: t.Optional[int]
        :return: Returns upstream message. If timeout provided, and no message received, will return None
        :rtype: t.Optional[domains.UpstreamMessage]
        """

        # If messages are already in buffer - return them. In other case - check closed state and raise an exception.
        if not self._upstream_buffer.empty():
            return await self._upstream_buffer.get()

        if timeout is None:
            recv_data_task = asyncio.create_task(self._upstream_buffer.get())

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
                return await asyncio.wait_for(self._upstream_buffer.get(), timeout=timeout)

        return self._raise_on_closed(force_raise_if_closed=True)

    async def connect(self) -> None:
        """
        Creates task, which opens websocket connections and start to listen for new messages.
        Without this task, "stream()" method will not produce messages.
        This method will not block code execution, because it only manages background task.
        """

        if self.is_opened() or self.is_closed():
            raise exceptions.UpstreamError("Connection already established or closed")

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

            # If listener task raised exception then reraise it, otherwise raise UpstreamConnecetionCloseError
            exception = listener_task.exception()
            if exception:
                raise exception

            return self._raise_on_closed()

    async def _listener(self) -> None:
        close_result: t.Optional[str] = None

        try:
            logging.debug(
                f"Starting listener for upstream websocket connection ws[{self._identifier}] to"
                f" {str(self.__api_path)!r}"
            )
            query_params = {"access_token": self.__access_token}
            async with self._session.ws_connect(self.__api_path, params=query_params) as ws:
                self._ws = ws
                self._opened.set()
                logging.debug(f"Upstream websocket connection ws[{self._identifier}] established")

                while not self._stop_event.is_set():
                    with suppress(asyncio.TimeoutError):
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
                        elif ws_msg.type == aiohttp.WSMsgType.CLOSE:
                            close_result = (
                                f"Connection closed with ws closed_code: {ws_msg.data}; reason: {ws_msg.extra}"
                            )
                        elif ws_msg.type == aiohttp.WSMsgType.CLOSED:
                            if close_result is None:
                                close_result = "Connection closed due to unknown network reason"
                            logging.warning(f"ws[{self._identifier}] Connection closed")
                            return

            logging.debug(f"Stopped listener for upstream websocket connection ws[{self._identifier}]")
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

            logging.debug(f"Closed event set for upstream websocket connection ws[{self._identifier}]")

    def close(self) -> None:
        """
        Close upstream connection.
        """
        self._stop_event.set()
        logging.debug(f"Closing upstream connection ws[{self._identifier}]")

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

            upstream_connection.close()  # Close upstream connection
            await upstream_connection.wait_closed()  # Wait until connection is closed

        :raises Exception: Raises exception if connection in not established before closing
        """
        if self.is_closed():
            return

        # TODO: custom exceptions
        if not self._ws:
            raise Exception(f"UpstreamConnection has not yet been established ws[{self._identifier}]")

        await self._closed
        logging.debug(f"Upstream connection closed ws[{self._identifier}]")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()
        await self.wait_closed()
