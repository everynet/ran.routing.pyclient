
# Tutorial

## Routing core

"Core" is main object of ran-routing SDK. It allows to manage routing table, work with upstream and downstream API.

To use sdk, you need to create `ran.routing.core.Core` object first.
It takes two required parameters:

- `access_token` - your access token for Ran Routing API, you can obtain one at [LANDING PAGE](http://example.com/).
- `coverage` - this is value of enum class {class}`ran.routing.core.domains.Coverage`. Coverage refers to one of the available network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ...

With one Core instance you can access only one coverage, provided on Core creation. If you want to gain access to different coverages, create multiple Core objects.

`Core` object manages underlying network connections with Ran Routing API, so it requires connection management.
Core provides context manager api, so you can use it in "async with" statement. It will automatically open and close connections to Ran Routing API.

```python
from ran.routing.core import domains, Core

async def main():
    async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
        # do something with core
        pass
```

Also, if you want to manage core state manually, you can use methods `connect` and `close`:

- {meth}`ran.routing.core.Core.connect`
- {meth}`ran.routing.core.Core.close`

It is required to close connection after use.

```python
from ran.routing.core import domains, Core

async def main():
    ran = Core(access_token="...", coverage=domains.Coverage.DEV)
    await ran.connect()
    # do something with core
    await ran.close()
```

After connecting to API, you will have an access to several Core attributes:

* {attr}`ran.routing.core.Core.routing_table` - Routing table management object {class}`ran.routing.core.RoutingTable`
* {attr}`ran.routing.core.Core.upstream` - Upstream streaming api connection manager {class}`ran.routing.core.UpstreamConnectionManager`
* {attr}`ran.routing.core.Core.downstream` - Downstream streaming api connection manager {class}`ran.routing.core.DownstreamConnectionManager`

## Routing table

You can access routing table by using {attr}`ran.routing.core.Core.routing_table`.

You don't need to create additional connections for routing table, it is created automatically after Core object is created.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    devices = await ran.routing_table.select()
```

{class}`ran.routing.core.RoutingTable` provides several methods for managing routing table:

- {meth}`ran.routing.core.RoutingTable.insert` - insert new device into routing table
- {meth}`ran.routing.core.RoutingTable.update` - update device in routing table
- {meth}`ran.routing.core.RoutingTable.delete` - delete device from routing table
- {meth}`ran.routing.core.RoutingTable.delete_all` - delete all devices from routing table
- {meth}`ran.routing.core.RoutingTable.select` - get device from routing table


## Select devices

Method {meth}`ran.routing.core.RoutingTable.select` provides logic to fetch info about existed devices. It returns list of {class}`ran.routing.core.domains.Device` DTO-objects, with data of stored devices.


```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    # You can select devices by any of the following ways:

    # Select all devices (will return list of all devices)
    devices = await ran.routing_table.select()

    # Select devices with pagination
    devices = await ran.routing_table.select(offset=10, limit=5)

    # Select devices by dev_euis (will return list of devices with given dev_euis)
    devices = await ran.routing_table.select(
        dev_euis=[0x7abe1b8c93d7174f, 0x7bbe1b8c93d7174a],
    )

    # Pagination also works with passed dev_euis
    devices = await ran.routing_table.select(
        dev_euis=[0x7abe1b8c93d7174f, 0x7bbe1b8c93d7174a],
        offset=1, 
        limit=1
    )

```

## Insert new devices

Method {meth}`ran.routing.core.RoutingTable.insert` allows to insert new device into routing table. It returns {class}`ran.routing.core.domains.Device` DTO-object, with data of newly created device.

Both `dev_eui` and `dev_addr` are mandatory parameters for ABP devices. while `dev_eui` and `join_eui` are mandatory parameters for OTAA devices.
Provided `dev_eui` must be unique, while single `dev_addr` may be assigned to several `dev_eui`'s simultaneously.


```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    # Creating OTAA-device
    device = await ran.routing_table.insert(
        dev_eui=0x7abe1b8c93d7174f,
        join_eui=0x3cedcf624f8b68f4
    )
    # Creating ABP-device
    device = await ran.routing_table.insert(
        dev_eui=0x7abe1b8c93d7174f,
        dev_addr=0x627bb8bb
    )
```

## Update devices

You can update device in routing table by using {meth}`ran.routing.core.RoutingTable.update` method.

Update procedure allows to change `dev_addr` for existed device in a routing table by `dev_eui`. This method is intended to be used by the client to set new device address after the join request has been processed.

Updating `dev_addr` is not allowed for ABP devices.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.update(
        dev_eui=0x7abe1b8c93d7174f,
        join_eui=0x3cedcf624f8b68f4,
        active_dev_addr=0x627bb8bc
    )
```

## Delete devices

To delete device from routing table, use {meth}`ran.routing.core.RoutingTable.delete` method.
Provide `dev_eui` for devices to delete.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.delete(
        dev_euis=[0x7abe1b8c93d7174f, 0x7bbe1b8c93d7174a],
    )
```


You can delete all devices in chosen coverage by calling {meth}`ran.routing.core.RoutingTable.delete_all` method.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.delete_all()
```

---

## Upstream API

To use upstream api, you need to create connection {class}`ran.routing.core.UpstreamConnection` object, which is managed by {class}`ran.routing.core.UpstreamConnectionManager`.

You have access to `UpstreamConnectionManager` object by using `Core` attribute {attr}`ran.routing.core.Core.upstream`.

You can create multiple `UpstreamConnection` objects, to distribute messages consumption. If more than one connection created, each connection will receive unique messages from API in random order.

Each `UpstreamConnection` object uses same TCP connection pool, managed by `Core` object.
When `Core` object is closed, all `UpstreamConnection` objects will be closed as well.

Preferred way to use `UpstreamConnection` is context-manager. This context manager will automatically close websocket connection and stop all underlying tasks, when context exited.


```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.upstream() as upstream_connection:
        # do something with upstream connection
        pass
    
```

If you want to manage upstream connection state manually, you can create `UpstreamConnection` object by using {meth}`ran.routing.core.UpstreamConnectionManager.create_connection` method.

In this case you need to close connection manually.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    upstream_connection = await ran.upstream.create_connection()
    # do something with upstream connection
    pass
    # Closing upstream connection, this operation is instant and will not block
    upstream_connection.close()
    # Waiting for closing upstream connection, this operation is blocking and will return when upstream connection is closed
    await upstream_connection.wait_closed()
```

Main method, used for receiving messages from upstream, is {meth}`ran.routing.core.UpstreamConnection.stream` method.
This method returns async iterator, which will yield received upstream messages.

Simple example of using `UpstreamConnection` to receive upstream messages:

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.upstream() as upstream_connection:
        async for upstream_message in upstream_connection.stream():
            await handle_message(upstream_message)
```

Each upstream message is {class}`ran.routing.core.domains.UpstreamMessage` DTO-object. It contains all data, defined by ran-routing protocol.

Also, you will want to use `UpstreamConnection` to send UpstreamAck and UpstreamReject messages, because it required in ran-routing specification. For this purpose, `UpstreamConnection` has following methods:

- {meth}`ran.routing.core.UpstreamConnection.send_upstream_ack` sends UpstreamAck message.
- {meth}`ran.routing.core.UpstreamConnection.send_upstream_reject` sends UpstreamReject message.

Following example has both UpstreamAck and UpstreamReject cases:

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.upstream() as upstream_connection:
        async for message in upstream_connection.stream():
            try:
                # Assuming This function handles MIC challenge and returns device EUI and correct MIC
                # If MIC is incorrect, exception "MicChallengeError" will be raised
                dev_eui, mic = await handle_message(message) 
            except MicChallengeError:  
                # We have could not solve MIC challenge, and now we need to send UpstreamReject message
                await upstream_connection.send_upstream_reject(
                    transaction_id=message.transaction_id, 
                    result_code=domains.UpstreamRejectResultCode.MICFailed
                )
            else:
                # Everything is OK, so we can send correct ACK message
                await upstream_connection.send_upstream_ack(
                    transaction_id=message.transaction_id, 
                    dev_eui=dev_eui, 
                    mic=mic,
                )
```


## Downstream API

Downstream API is pretty similar with [Upstream API](#upstream-api).
To use downstream api, you need to create connection {class}`ran.routing.core.DownstreamConnection` object, 
which is managed by {class}`ran.routing.core.DownstreamConnectionManager`.

You have access to `DownstreamConnectionManager` object by using `Сore` attribute {attr}`ran.routing.core.Core.downstream`.

To create connection, you need to provide `coverage` parameter, which is value of enum class {class}`ran.routing.core.domains.Coverage`.


```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.downstream() as downstream_connection:
        # do something with downstream connection
        pass
    
# or

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    downstream_connection = await ran.downstream.create_connection()
    # do something with downstream connection here
    pass
    # Closing downstream connection, this operation is instant and will not block
    downstream_connection.close()
    # Waiting for closing downstream connection, this operation is blocking and will return when downstream connection is closed
    await downstream_connection.wait_closed()

```

Main usage of `DownstreamConnection` is to send messages to downstream API. It can be done, using method {meth}`ran.routing.core.DownstreamConnection.send_downstream`. This method allows to send any type of message to device.

This method requires parameters, which are described in ran-routing specification.


```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.downstream() as downstream_connection:
        # do something with downstream connection
        await downstream_connection.send_downstream(
            # Client code must provide unique transaction_id, which will be sent in DownstreamAck and DownstreamResult messages.
            transaction_id=next(counter),
            # Device identifier.
            dev_eui=dev_eui,
            # Transmission window object, check example below.
            tx_window=make_tx_window(),
            # bytes of phy_payload, produced by network server.
            phy_payload=phy_payload,
            # Optional field. Must be provided, if this is join-response message.
            # Used to automatically update device address in ran-routing table after join accept will be handled by device.
            target_dev_addr=dev_addr_after_join,
        )
    
```

To tell the downstream API server when and how to send downstream message, you need to provide `tx_window` parameter.
It may be instance of {class}`ran.routing.core.domains.TransmissionWindow` or dict object with same structure.

***TODO: BETTER EXAMPLE!***

```python
def make_tx_window():
    # It contains two parts: radio parameters and transmission window parameters.

    # First, we need to create radio object
    radio_params = {
        "frequency": 868300000,
        # Specify the modulation type and its parameters.
        "lora": {
            "spreading": 1,
            "bandwidth": 1,
        }
    }

    # Second part is transmission window parameters.
    # You can provide one of following values:
    # "delay" (for class A downstream)
    # "tmms" (for class B downstream)
    # "deadline" (for class C downstream)
    window = {
        "radio": radio_params,
        "delay": 1,
    }
    return window


```

To obtain info messages from DownstreamConnection, you can use similar interface with UpstreamConnection. 

You can gain access to downstream messages by using {meth}`ran.routing.core.DownstreamConnection.stream` method.

```python
from ran.routing.core import domains, Core

async with Core(access_token="...", coverage=domains.Coverage.DEV) as ran:
    async with ran.downstream() as downstream_connection:
        async for downstream_message in downstream_connection.stream():
            await handle_downstream_message(downstream_message)
```

Downstream messages, obtained this way, can be different types:

- {class}`ran.routing.core.domains.DownstreamAckMessage` - downstream API server has received message, and take it to processing.
- {class}`ran.routing.core.domains.DownstreamResultMessage` - downstream API server has finished processing message.

Both of these messages have `transaction_id` field, which is used to identify message. It is similar to `transaction_id`, you send in Downstream messages.
