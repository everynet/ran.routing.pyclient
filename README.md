# Python Client for Everynet RAN Routing API


## Introduction

Everynet operates a Neutral-Host Cloud RAN, which is agnostic to the LoRaWAN Network Server. Everynet's main product is carrier-grade coverage that can be connected to any LNS available on the market.

Everynet coverage is available via Everynet RAN Routing API that let customer to control message routing table (subscribe to devices). It also allows to send and receive LoRaWAN messages.

This API client is designed to simplify the use of Everynet RAN Routing API and serve as an example for other client implementations. 

Before we start it is important to mention that Everynet RAN main functionality is LoRaWAN traffic routing. 

The RAN receives messages from gateways and then matches each message with the _customer_ using either _DevAddr_ or pair _(DevEUI, JoinEUI)_. **The relations between device details and customer details are stored in a routing table.** 

| DevEUI | JoinEUI | DevAddr | Customer |
| ------ | ------- | ------- | -------- |
| 0x0..1 | 0x0..3  | 0x0..5  | ACME Inc.|
| 0x0..2 | 0x0..4  | 0x0..8  | ACME Inc.|

Everynet RAN Routing API is designed to let customer control such a rounting table to subscribe to the end device traffic. 

It also provides both upstream and downstream messaging capabilities.

**Cloud RAN does not store any device-related cryptographic keys and is not capable of decrypting customer traffic.** 

Maintaining data ownership gurantees without an access to the device keys the RAN enabled with a purpose-built MIC challenge procedure described in details in the RAN Routing API specification.


## Installation

You can install the client with [`pip`](https://pip.pypa.io/en/stable/installing/), using following command:

```bash
$ pip install everynet
```


## Usage example

Here is a very quick walkthrough the client usage example to illustrate how easy it is to subscribe and get messages:

```python
import asyncio

from ran.routing.core import Core


async def main():
    async with Core(access_token="...", url="...") as ran:
        # Create routing table record
        device = await ran.routing_table.insert(dev_eui=0x7ABE1B8C93D7174F, join_eui=0x3CEDCF624F8B68F4)

        # Will print "Device(dev_eui=8844537008791951183, join_eui=4390393232904382708, created_at=...)"
        print(device)

        # You can gather data about existed devices from routing_table any time.
        devices = await ran.routing_table.select()
        assert devices[0].dev_eui == device.dev_eui

        # Create upstream connection and downstream connection
        async with ran.upstream() as upstream, ran.downstream() as downstream:
            async for upstream_message in upstream.stream():
                # will print "UpstreamMessage(protocol_version=1, transaction_id=1, dev_euis=[8844537008791951183], ...)"
                await print(upstream_message)

                # Prepare downlink radio and tx_window
                lora_modulation = domains.LoRaModulation(spreading=12, bandwidth=125000)
                radio = domains.DownstreamRadio(frequency=868300000, lora=lora_modulation)
                tx_window = domains.TransmissionWindow(radio=radio, delay=1)

                # Send downlink to the device
                await downstream.send_downstream(
                    transaction_id=1,
                    dev_eui=0x7ABE1B8C93D7174F,
                    tx_window=tx_window,
                    phy_payload=b"some-phy-payload-from-lns",
                )

                downstream_ack = await downstream.recv(timeout=1)
                downstream_result = await downstream.recv(timeout=1)

        # Deleting device from routing table
        await ran.routing_table.delete(dev_euis=[device.dev_eui])


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

## Managing of the routing table

It is possible to get access to the RAN routing table by using the `ran.routing.core.Core.routing_table` attribute, but before that it is needed to connect client to the RAN Routing API.


### Connecting to the RAN Routing API

It is needed to create `ran.routing.core.Core` object to create connect client to the RAN Routing API.

`Core` is main object of ran-routing client that allows to manage routing table, work with upstream and downstream messages.

Object constructor takes two mandatory parameters:

- `access_token` - RAN Routing API access token that can be obtained from Everynet support
- `url` - RAN Routing API url. That URL refers to one of the available API instances, which provides traffic from different territories such as Brazil, Indonesia, USA, Italy, Spain, UK, ...

Note, that it is necessary to create multiple `Core` objects if you want to gain access to the coverage in several territories simultaneously.

RAN Routing API connections need to be opened and closed manually. In order to simplify that `Core` provides context manager, so it is possible to use "async with" statement with it. It will automatically open and close connections to the RAN Routing API.

```python
from ran.routing.core import Core

async def main():
    async with Core(access_token="...", url="...") as ran:
        # do something with core
        pass
```

Also, it is possible to manage connections via the `connect()` and `close()` methods:

- `ran.routing.core.Core.connect()`
- `ran.routing.core.Core.close()`

It is required to close connection after use.

```python
from ran.routing.core import Core

async def main():
    ran = Core(access_token="...", url="...")
    await ran.connect()
    # do something with core
    await ran.close()
```

After establishing a connection with the RAN Routing API, you will gain access to the following attributes:

* `ran.routing.core.Core.routing_table` - routing table management interface `ran.routing.core.RoutingTable`
* `ran.routing.core.Core.multicast_groups` - multicast groups management interface `ran.routing.core.MulticastGroupsManagement`
* `ran.routing.core.Core.upstream` - upstream message streaming interface `ran.routing.core.UpstreamConnectionManager`
* `ran.routing.core.Core.downstream` - downstream message streaming interface `ran.routing.core.DownstreamConnectionManager`

These interfaces are discussed in the next chapters.


## Managing RAN routing table

You can access routing table by using the `ran.routing.core.Core.routing_table` attribute.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    devices = await ran.routing_table.select()
```

It provides several methods for managing the RAN routing table:

- `ran.routing.core.RoutingTable.insert` - insert new device into the routing table
- `ran.routing.core.RoutingTable.update` - update specitfic device in the routing table
- `ran.routing.core.RoutingTable.delete` - delete device from the routing table
- `ran.routing.core.RoutingTable.delete_all` - delete all devices from the routing table
- `ran.routing.core.RoutingTable.select` - fetch device information from the routing table

The methods are explained in details below...

### Select devices

Method `ran.routing.core.RoutingTable.select` fetches existing devices from the routing table. It returns list of `ran.routing.core.domains.Device` DTO-objects.


```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
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

### Insert new devices

Method `ran.routing.core.RoutingTable.insert` inserts new device into the routing table. It returns `ran.routing.core.domains.Device` DTO-object that contais information about newly created device.

Both `dev_eui` and `dev_addr` are mandatory parameters for ABP devices, while `dev_eui` and `join_eui` are mandatory parameters for OTAA devices.

Provided `dev_eui` must be unique, while single `dev_addr` may be assigned to several `dev_eui`'s simultaneously.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
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

### Update devices

Updating device in the routing table is performed via the `ran.routing.core.RoutingTable.update` method.

Update procedure changes `dev_addr` for an existed device in the routing table, where device is referred by the device's `dev_eui`.

This method is intended to be used by the client to set the new device address after the join request has been processed.

Updating of the `dev_addr` is not allowed for ABP devices.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.update(
        dev_eui=0x7abe1b8c93d7174f,
        join_eui=0x3cedcf624f8b68f4,
        active_dev_addr=0x627bb8bc
    )
```

### Delete devices

Deleting devices from the routing table is performed via `ran.routing.core.RoutingTable.delete` method. It is needed to provide the list of `dev_eui` selected for deletion.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.delete(
        dev_euis=[0x7abe1b8c93d7174f, 0x7bbe1b8c93d7174a],
    )
```

It is also possible to delete all devices in the routing table by calling `ran.routing.core.RoutingTable.delete_all` method.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # Updating device's dev_addr
    device = await ran.routing_table.delete_all()
```

## Managing multicast groups

It is possible to get access to the RAN multicast groups by using the `ran.routing.core.Core.multicast_groups` attribute, but before that it is needed to connect client to the RAN Routing API.

It provides several methods for managing the RAN routing table:

- `ran.routing.core.MulticastGroupsManagement.create_multicast_group` - create new multicast group
- `ran.routing.core.MulticastGroupsManagement.update_multicast_group` - update specific device multicast group
- `ran.routing.core.MulticastGroupsManagement.get_multicast_groups` - fetch multicast groups
- `ran.routing.core.MulticastGroupsManagement.delete_multicast_groups` - delete multicast group
- `ran.routing.core.MulticastGroupsManagement.add_device_to_multicast_group` - add device to multicast group
- `ran.routing.core.MulticastGroupsManagement.remove_device_from_multicast_group` - remove device from multicast group

The methods are explained in details below...


### Create multicast group

New multicast group can be created with `ran.routing.core.MulticastGroupsManagement.create_multicast_group` method. This method requires group name and group address. It returns `ran.routing.core.domains.MulticastGroup` DTO-object that contains information about newly created multicast group.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    multicast_group = await ran.multicast_groups.create_multicast_group(
        name="test-multicast-group", 
        addr=0xef046a1e
    )
```

### Select multicast group

Method `ran.routing.core.MulticastGroupsManagement.get_multicast_groups` fetches existing multicast groups from the routing table. It returns list of `ran.routing.core.domains.MulticastGroup` DTO-objects. You can select all groups (if no args provided), or specific groups, by passing groups addresses into this method.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # Fetching all groups
    all_multicast_groups = await ran.multicast_groups.get_multicast_groups()

    # Fetching one group (also returns list, but with one element)
    multicast_groups = await ran.multicast_groups.get_multicast_groups(0xef046a1e)

    # Fetching specific groups
    multicast_groups = await ran.multicast_groups.get_multicast_groups(0xef046a1e, 0xffed8719)
```

### Update multicast group

Method `ran.routing.core.MulticastGroupsManagement.update_multicast_group` can perform multicast group update procedure.

You can update `addr` (address) or `name` of the multicast group (or both).

Update procedure changes fields for an existed multicast group, where multicast group is referred by the it's `addr` (address). You need to provide at least one of new fields to make update.


```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # Updating name
    multicast_group = await ran.multicast_groups.update_multicast_group(
        addr=0xef046a1e, 
        new_name="new-multicast-group-name"
    )
    # Updating addr
    multicast_group = await ran.multicast_groups.update_multicast_group(
        addr=0xef046a1e, 
        new_addr=0xffffffff, 
    )
    # Updating all fields
    multicast_group = await ran.multicast_groups.update_multicast_group(
        addr=0xef046a1e, 
        new_addr=0xffffffff, 
        new_name="new-multicast-group-name"
    )
```

### Manage multicast group devices

Devices can be added or removed from multicast group by using:

- `ran.routing.core.MulticastGroupsManagement.add_device_to_multicast_group` - for adding new device into multicast group.
- `ran.routing.core.MulticastGroupsManagement.remove_device_from_multicast_group` - for removing existed device from multicast group.

Only devices, already added into routing table can be added into multicast group.

Only devices, already added into multicast group, can be removed from it.


```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    # We need to create device first, before adding it into multicast group.
    device = await ran.routing_table.insert(
        dev_eui=0x7abe1b8c93d7174f,
        dev_addr=0x627bb8bb
    )
    # Creating multicast group
    multicast_group = await ran.multicast_groups.create_multicast_group(
        name="test-multicast-group", 
        addr=0xef046a1e
    )

    # Adding device into multicast group
    multicast_group = await ran.multicast_groups.add_device_to_multicast_group(
        addr=multicast_group.addr, 
        dev_eui=device.dev_eui, 
    )
    # Removing device from multicast group
    multicast_group = await ran.multicast_groups.remove_device_from_multicast_group(
        addr=multicast_group.addr,
        dev_eui=device.dev_eui,
    )
```

### Delete multicast group

Deleting multicast group is performed via `ran.routing.core.RoutingTable.delete_multicast_groups` method. It is needed to provide the list of `addr` of multicast groups, selected for deletion.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    multicast_group = await ran.multicast_groups.delete_multicast_groups(
        addrs=[0xef046a1e],
    )
```


## Sending and receiving messages

### Connecting to the Upstream API

It is needed to connect to the RAN Upstream API to start getting upstream messages. 

Connection is established by creating of the `ran.routing.core.UpstreamConnection` object, which is managed by `ran.routing.core.UpstreamConnectionManager` class.

It is possible to access to `UpstreamConnectionManager` object by using `Core` attribute `ran.routing.core.Core.upstream`.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    async with ran.upstream() as upstream_connection:
        # do something with upstream connection
        pass
    
```

Preferred way to use `UpstreamConnection` is via context-manager. This context manager will automatically close websocket connection and stop all underlying tasks, when context exited.

In case of the high number of messages it is possible to create multiple `UpstreamConnection` objects, for the load balancing purposes. In this case each connection will receive unique messages from the RAN in random order.

Each `UpstreamConnection` object uses the same TCP connection pool, that is managed by the `Core` object. Once the `Core` object is closed, all underlying `UpstreamConnection` objects will be closed as well.

It is also possible to manage upstream connection state manually by instanciating of the `UpstreamConnection` object manually via `ran.routing.core.UpstreamConnectionManager.create_connection` method.

In this case you need to close connection manually as well. Unclosed connection may cause memory leak and data loss.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    upstream_connection = await ran.upstream.create_connection()
    # do something with upstream connection
    pass
    # Closing upstream connection, this operation is instant and will not block
    upstream_connection.close()
    # Waiting for closing upstream connection, this operation is blocking and will return when upstream connection is closed
    await upstream_connection.wait_closed()
```

### Receiving upstream messages

The main method, to receive upstream message is via the `ran.routing.core.UpstreamConnection.stream()` method. 

This method returns async iterator, which will yield received upstream messages.

Here is how to receive upstream messages:

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    async with ran.upstream() as upstream_connection:
        async for upstream_message in upstream_connection.stream():
            await handle_message(upstream_message)
```

Each upstream message is `ran.routing.core.domains.UpstreamMessage` DTO-object. It contains all data, defined by RAN Routing API specification.

It is required by the RAN Routing API to acknowledge all upstream messages.

Please use `UpstreamConnection` to send either `UpstreamAck` or `UpstreamReject` messages back to RAN:

- `ran.routing.core.UpstreamConnection.send_upstream_ack` sends UpstreamAck message.
- `ran.routing.core.UpstreamConnection.send_upstream_reject` sends UpstreamReject message.

Following example has both UpstreamAck and UpstreamReject cases:

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
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


### Connecting to Downstream API

Downstream API is pretty similar to the Upstream API.

Connection to the downstream API is established via creation of the  `ran.routing.core.DownstreamConnection` object, which is managed by the `ran.routing.core.DownstreamConnectionManager` class.

It is possible to get access to the `DownstreamConnectionManager` object by using `Сore` attribute `ran.routing.core.Core.downstream`.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    async with ran.downstream() as downstream_connection:
        # do something with downstream connection
        pass
    
# or

async with Core(access_token="...", url="...") as ran:
    downstream_connection = await ran.downstream.create_connection()
    # do something with downstream connection here
    pass
    # Closing downstream connection, this operation is instant and will not block
    downstream_connection.close()
    # Waiting for closing downstream connection, this operation is blocking and will return when downstream connection is closed
    await downstream_connection.wait_closed()

```

The main purpose of the `DownstreamConnection` is to send messages back to devices via Downstream API. It can be done, using the `ran.routing.core.DownstreamConnection.send_downstream` method. This method allows to send any type of message to device: downlinks, join-accepts, etc.

This method requires parameters, which are described in the RAN Routing API specification.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
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

To tell the downstream API when and how to send downstream message, you need to provide `tx_window` parameter.

It may be instance of `ran.routing.core.domains.TransmissionWindow` or dict object with same structure.

```python
# TODO: We can come up with a better example in future...
def make_tx_window():
    # It contains two parts: radio parameters and transmission window parameters.

    # First, we need to create radio object
    lora_modulation = domains.LoRaModulation(spreading=12, bandwidth=125000)
    radio = domains.DownstreamRadio(frequency=868300000, lora=lora_modulation)

    # Second part is transmission window parameters.
    # You can provide one of following values:
    # "delay" (for class A downstream)
    # "tmms" (for class B downstream)
    # "deadline" (for class C downstream)
    tx_window = domains.TransmissionWindow(radio=radio, delay=1)
    return tx_window


```

To obtain info messages from `DownstreamConnection`, you can use interface similar to the `UpstreamConnection`.

It is possible gain access to downstream messages by using `ran.routing.core.DownstreamConnection.stream` method.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    async with ran.downstream() as downstream_connection:
        async for downstream_message in downstream_connection.stream():
            await handle_downstream_message(downstream_message)
```

Downstream messages, obtained this way, can be of different types:

- `ran.routing.core.domains.DownstreamAckMessage` - downstream API server has received message, and scheduled it for processing
- `ran.routing.core.domains.DownstreamResultMessage` - downstream API server has finished processing of the message

Both of these messages have `transaction_id` field, which is used to identify message. It is similar to the `transaction_id`, you send in Downstream messages.


### Sending multicast downstream messages

Multicast messages can be sent with same `DownstreamConnection`, which used for regular downlink messages.

You can send multicast downlinks, by using the `ran.routing.core.DownstreamConnection.send_multicast_downstream` method.

This method requires parameters, which are described in the RAN Routing API specification.

This parameters are pretty same, as in regular `send_downstream` downlinks, but instead of `dev_eui` of device using `addr` of multicast group as target, and don't support `target_dev_addr` field.

```python
from ran.routing.core import Core

async with Core(access_token="...", url="...") as ran:
    async with ran.downstream() as downstream_connection:
        # do something with downstream connection
        await downstream_connection.send_multicast_downstream(
            # Client code must provide unique transaction_id, which will be sent in DownstreamAck and DownstreamResult messages.
            transaction_id=next(counter),
            # Multicast group address
            addr=multicast_group_addr,
            # Transmission window object, check example above.
            tx_window=make_tx_window(),
            # bytes of phy_payload, produced by network server.
            phy_payload=phy_payload,
        )
```

You need to use same `transaction_id` counter for multicast downlinks, you use for regular downlinks.

You will receive `DownstreamAckMessage` and `DownstreamResultMessage` for multicast downstream, as for regular downlink.

