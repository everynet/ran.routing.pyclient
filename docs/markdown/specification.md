# RAN Connection API

> Note: This document is a draft specification of the RAN Connection API

## Table of contents

- [Introduction](#Introduction)
- [Subscription Management](#Subscription-Management)
- [Message Streaming](#message-streaming)
- [Upstream Traffic](#upstream-traffic)
- [Downstream Traffic](#downstream-traffic)
- [Message Types](#message-types)
    - [Upstream](#upstream-message)
    - [UpstreamAck](#upstreamack-message)
    - [Downstream](#downstream-message)
    - [DownstreamAck](#downstreamack-message)
    - [DownstreamResult](#downstreamack-message)
- [Models](#Models)

## Foreword

Everynet operates a Neutral-Host Cloud RAN, which can support customers with two different integration options:

- LNS may subscribe to specific devices (by DevEUI) on the Everynet RAN using proprietary RAN API (recommended)
- Devices may roam to Everynet RAN using the LoRa Alliance Backend Interfaces specification

There are several benefits to this first implementation. The most obvious is that it allows a host to subscribe and unsubscribe to individual devices, as the use case and business model support. It also eliminates message traffic from devices that are no longer subscribed to the LNS (or never were).

## Introduction

This API is intended to connect Everynet Cloud RAN (RAN) with customer LoRaWAN Network Server (LNS). The API is LNS-agnostic. 

Everynet RAN core funtionality is LoRaWAN traffic routing.  It receives messages from gateways and then matches each message with the _customer_ using either _DevAddr_ or pair _(DevEUI, JoinEUI)_. **The relations between device details and customer details are stored in a routing table.** 

Everynet RAN API is designed to let customer control the routing table. It also provides both upstream and downstream messaging capabilities.

**Cloud RAN does not store any device-related cryptographic keys and is not capable of decrypting customer traffic.** Maintaining data ownership gurantees without an access to the device keys the RAN enabled with a purpose-built [MIC challenge procedure](#mic-challenge-procedure).

All streaming interactions between RAN and LNS are organized via messaging API. It is based on asynchronous secure websockets (wss://).


## Subscription Management

To start receiving uplinks or join requests we require LNS to **explicitly** subscribe (and unsubscribe) for every device using the API methods below.

Note that subscriptions are simply rows in the RAN traffic routing table, hence the naming convention.

The methods are HTTP-based and are not available via WebSocket interface.

You can check subscription api OpenAPI Specification (Swagger) - http://3.68.195.68:8080/docs 
(TODO: in the future http://ranapi.everynet.com/api/v1.0/subscription/docs)
Subscription API path may look like `/api/v1.0/subscription/<coverage-id>/`, where `<coverage-id>` is numeric identifier of coverage.


| Method | Description |
| ------ | ----------- |
| [devices.select(CoverageID, ClientID,  Optional[DevEUIs])](#Devices.Select) | Select device subscriptions from the routing table. List of devices is specified via `DevEUIs` parameter. If `DevEUIs` parameter is not set, then all device subscriptions are returned. |
| [devices.insert(CoverageID, ClientID, DevEUI, OneOf[JoinEUI, DevAddr], Optional[Details])](#Devices.Insert) | Insert device subscription into the routing table to start receiving messages from the specified device. Both `DevEUI` and `DevAddr` are mandatory parameters for ABP devices. while `DevEUI` and `JoinEUI` are mandatory parameters for OTAA devices. Provided `DevEUI` must be unique, while single `DevAddr` may be assigned to several `DevEUIs` simultaneously. Optional `Details` field provides additional device information, such as geographical coordinates or device model. |
| [devices.update(CoverageID, ClientID, DevEUI, JoinEUI, Optional[ActiveDevAddr], Optional[TargetDevAddr])](#Devices.Update) | Update device subscription in a routing table by `DevEUI`. This API function is intended to be used by the LNS to set new device address after the join request has been processed. Optional parameters that are ommited won't be updated, `null` values are not allowed. |
| [devices.drop(CoverageID, ClientID, DevEUIs)](#Devices.Drop) | Deletes device subscription from the routing table by `DevEUI`. |
| [devices.drop_all(CoverageID, ClientID)](#Devices.DropAll) | Deletes all device subscriptions from the routing table. |


---


### Devices.Select

Select device subscriptions from the routing table. 

List of devices is specified via `DevEUIs` parameter. If `DevEUIs` parameter is not set, then all device subscriptions are returned.

**Params info:** 
| Param | Required | Type | Description |
| --- | --- | --- | --- |
| `CoverageID` | yes | int | This ID refers to one of the available Everynet network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ... |
| `ClientID` | yes | int | This ID refers to the client. |
| `DevEUIs` | no | str[] | List of `DevEUI` hex strings. |


#### Example



```bash

$ curl -s --request GET 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/select' \
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' | jq
[
  {
    "DevEUI": "dddddddddddddddd",
    "JoinEUI": "dddddddddddddddd",
    "ActiveDevAddr": "dddddddd",
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-30T10:06:44.726471"
  },
  {
    "DevEUI": "ffffffffffffffff",
    "JoinEUI": null,
    "ActiveDevAddr": "ffffffff",
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-31T07:20:00.360463"
  },
  {
    "DevEUI": "eeeeeeeeeeeeeeee",
    "JoinEUI": "eeeeeeeeeeeeeeee",
    "ActiveDevAddr": null,
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-31T07:32:16.545797"
  }
]
```

##### With DevEUIs specified:

```bash
$ curl -s --request GET 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/select?DevEUIs=ffffffffffffffff&DevEUIs=dddddddddddddddd' \                                                                   
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' | jq
[
  {
    "DevEUI": "dddddddddddddddd",
    "JoinEUI": "dddddddddddddddd",
    "ActiveDevAddr": "dddddddd",
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-30T10:06:44.726471"
  },
  {
    "DevEUI": "ffffffffffffffff",
    "JoinEUI": null,
    "ActiveDevAddr": "ffffffff",
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-31T07:20:00.360463"
  }
]
```


### Devices.Insert

Subscribe to the device messages. Insert device into the routing table to start receiving messages from the specified device. 

Both `DevEUI` and `DevAddr` are mandatory parameters for ABP devices. while `DevEUI` and `JoinEUI` are mandatory parameters for OTAA devices. 

Provided `DevEUI` must be unique, while single `DevAddr` may be assigned to several `DevEUIs` simultaneously. 

For some NetID types, the DevAddr space is much smaller than the number of possible DevEUIs and it is possible that multiple devices (DevEUIs) share the same DevAddr. RAN supports mupliple DevEUIs pointing to one DevAddr and provides an array of DevEUIs in the `Upstream` message. It is expected that LNS provides a correct `DevEUI` in the `UpstreamAck` message.

Optional `Details` field provides additional device information, such as geographical coordinates or device model.

**Params info:** 
| Param | Required | Type | Description |
| --- | --- | --- | --- |
| `CoverageID` | yes | int | This ID refers to one of the available Everynet network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ... |
| `ClientID` | yes | int | This ID refers to client. This identifier may be obtained automatically from credentials, provided by user. |
| `DevEUI` | yes | str | Hex string, represents 64 bit integer of end-device identifier. This field should be unique for each device. |
| `DevAddr` | conditional* | str | Hex string, represent 32 bit int device address. Single `DevAddr` may be assigned to several `DevEUIs` simultaneously. This param must be passed only for ABP devices. |
| `JoinEUI` | conditional* | str | Hex string, represents 64 bit int unique `JoinEUI`. This param must be passed only for OTAA devices. |
| `Details` | no | str | Some JSON in string form. This field provides additional device information, such as geographical coordinates or device model. Size of data, passed as this param, may be limited by server. |

`*` Only one of `DevAddr` or `JoinEUI` shall be provided, providing both values will result in an error.


#### Example

##### Create device with JoinEUI:

```json
{
    "DevEUI": "ffffffffffffffff", 
    "JoinEUI": "ffffffffffffffff"
}
```

```bash
$ curl -s --request POST 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/insert' \ 
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' \
--data-raw '{
"DevEUI":  "ffffffffffffffff", 
"JoinEUI": "ffffffffffffffff"
}' | jq

{
  "DevEUI": "ffffffffffffffff",
  "JoinEUI": "ffffffffffffffff",
  "ActiveDevAddr": null,
  "TargetDevAddr": null,
  "Details": null,
  "CreatedAt": "2022-05-31T07:12:02.875460"
}
```

##### Create device with DevAddr:
```json
{
    "DevEUI": "ffffffffffffffff",
    "DevAddr": "ffffffff"
}
```

```bash
$ curl -s --request POST 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/insert' \
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' \
--data-raw '{
"DevEUI": "ffffffffffffffff",
"DevAddr": "ffffffff"
}' | jq
{
  "DevEUI": "ffffffffffffffff",
  "JoinEUI": null,
  "ActiveDevAddr": "ffffffff",
  "TargetDevAddr": null,
  "Details": null,
  "CreatedAt": "2022-05-31T07:14:04.473749"
}
```


### Devices.Update

Update device subscription in a routing table by `DevEUI`. This API function is intended to be used by the LNS to set new device address after the join request has been processed. Optional parameters that are ommited won't be updated, `null` values are not allowed. 

Parameters `ActiveDevAddr` and `TargetDevAddr` are used to handle two security contexts during the join procedure. The security-context is only switched after the device sends its first uplink with `TargetDevAddr`. It is valid for both LoRaWAN 1.0.x and 1.1.

At least one of `ActiveDevAddr` or `TargetDevAddr` values must be provided.


**Params info:** 
| Param | Required | Type | Description |
| --- | --- | --- | --- |
| `CoverageID` | yes | int | This ID refers to one of the available Everynet network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ... |
| `ClientID` | yes | int | This ID refers to client. |
| `DevEUI` | yes | str | Hex string representing `DevEUI` of the updated device. Returns an error if device is missing from the routing table. |
| `JoinEUI` | yes | str | Hex string representing `JoinEUI` of the updated device. |
| `ActiveDevAddr` | conditional | str | Hex string, represent 32 bit int device address. Used to update current device address. |
| `TargetDevAddr` | conditional | str | Hex string, represent 32 bit int device address. This DevAddr was generated and sent to device by Join Server (via Join Accept), but NS is not informed about this change right now (by Uplink) |

#### Example

```json
{
    "DevEUI": "ffffffffffffffff", 
    "JoinEUI": "ffffffffffffffff",
    "TargetDevAddr": "ffffffff"
}
```


```bash
$ # This call is not required, here is just for example to see the difference after update
$ curl -s --request GET 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/select?DevEUIs=ffffffffffffffff' \                                                                   
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' | jq
[
  {
    "DevEUI": "ffffffffffffffff",
    "JoinEUI": "ffffffffffffffff",
    "ActiveDevAddr": null,
    "TargetDevAddr": null,
    "Details": null,
    "CreatedAt": "2022-05-31T07:20:00.360463"
  }
]

$ curl -s --request POST 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/update' \
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' \
--data-raw '{
"DevEUI": "ffffffffffffffff",
"JoinEUI": "ffffffffffffffff",
"TargetDevAddr": "ffffffff"  
}' | jq

{
  "DevEUI": "ffffffffffffffff",
  "JoinEUI": "ffffffffffffffff",
  "ActiveDevAddr": null,
  "TargetDevAddr": "ffffffff",
  "Details": null,
  "CreatedAt": "2022-05-31T07:20:00.360463"
}
```


### Devices.Drop

Deletes device subscription from the routing table by `DevEUI`.

**Params info:** 
| Param | Required | Type | Description |
| --- | --- | --- | --- |
| `CoverageID` | yes | int | This ID refers to one of the available Everynet network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ... |
| `ClientID` | yes | int | This ID refers to the client. This identifier may be obtained automatically from credentials, provided by user. |
| `DevEUIs` | no | str[] | List of `DevEUI` represented as hex strings. Subscription info about devices from the list will be deleted from routing table. |

#### Example

```json
{
    "DevEUIs": [
        "ffffffffffffffff"
    ]
}
```

```bash
$ curl -s --request POST 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/drop' \  
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' \
--data-raw '{"DevEUIs": ["ffffffffffffffff"]}' | jq

{
  "deleted": 1
}
```


### Devices.DropAll

Deletes all device subscriptions from the routing table.

**Params info:** 
| Param | Required | Type | Description |
| --- | --- | --- | --- |
| `CoverageID` | yes | int | This ID refers to one of the available Everynet network deployments: Brazil, Indonesia, USA, Italy, Spain, UK, ... |
| `ClientID` | yes | int | This ID refers to client. This identifier may be obtained automatically from credentials, provided by user. |


#### Example

```bash
$ curl -s --request POST 'http://ranapi.everynet.com/api/v1.0/subscription/1/devices/drop-all' \  
--header 'Authorization: Bearer secrettoken' \
--header 'Content-Type: application/json' \

{
  "deleted": 10
}
```


---


## Message Streaming

Message streams are available through the secure websockets at these URLs:
- [`wss://.../CoverageId/upstream`]() for `Upstream` and `UpstreamAck` messages
- [`wss://.../CoverageId/downstream`]() for `Downstream`, `DownstreamAck` and `DownstreamResult` messages.

Several websocket clients connected to the same URL will be served on a round robin basis receiving messages one after another. Please use it for load balancing.

LNS must handle Websocket ping-pong functionality properly.

## Upstream Traffic = Uplinks + Join Requests

Everynet RAN considers both join requests and uplinks as part of the upstream traffic and do not separate them.

For the billing purposes we require LNS to acknowledge every upstream message according to the [MIC challenge procedure](#mic-challenge-procedure).

Here is a list of messages related to the upstream traffic available to the customer.

### Upstream Traffic Messages

| Message | Direction | Description |
| ------- | --------- | ----------- |
| [Upstream](#upstream-message) | RAN -> LNS | Upstream (join request or uplink) message received by the network |
| [UpstreamAck](#upstreamack-message) | LNS -> RAN | Confirmation of Upstream message reception by the LNS |

### MIC Challenge Procedure

To keep upstream traffic clean and for the billing purposes we require LNS to acknowledge each upstream message.

**Acknowledgment procedure is designed this way to let RAN check whether LNS has correct device keys in possession without revealing these keys.**

The procedure executed by LNS is the following:

1. On `Upstream` message reception compute MIC using `Payload.PHYPayloadNoMIC` and `AppSKey` stored at LNS.
1. Check whether the `Payload.MICChallenge` field contains the correct MIC calculated on the previous step.
1. Send back `UpstreamAck` message to RAN (with LNS-calculated MIC in the `Payload.MIC` field).

The size of the `MICChallenge` field varies from 2 to 4096 and is reduced with every successful `UpstreamAck`.

Failure to accomplish this procedure may result in unsubscription of the LNS from the selected device traffic.

## Downstream traffic = Downlinks + Join Accepts

Everynet RAN considers both join accepts and downlink as part of the downstream and do not separate them.

Here is list of messages related to the downstream traffic between RAN and LNS.

| Message | Direction | Description |
| ------- | --------- | ----------- |
| [Downstream](#downstream-message) |  LNS -> RAN | Downstream (join accept or downlink) message that LNS is willing to send to the device. |
| [DownstreamAck](#downstreamack-message) |  RAN -> LNS | Confirmation of Downstream message reception by the RAN. |
| [DownstreamResult](#downstreamresult-message) |  RAN -> LNS | Result of Downstream message transmission. Can be transmitted or discarded due to different reasons (regulatory restrictions, lack of gateway capacity, etc.) |

Downstream messages could only be sent to the devices with active subscription. Any other downstream messages will be discarded.

## Message Types

### Upstream Message

| Field | Type | Mandatory | Description |
| ----- | ---- | --------- | ----------- |
| `ProtocolVersion`| UInt32 | True | RAN protocol version |
| `TransactionID`| UInt64 | True | This field is used by the `UpstreamAck` message to identify corresponding `Upstream` messages to acknowledge. |
| `Outdated` | Boolean | False | Set to true if an uplink is more than 2.5 seconds old. |
| `DevEUIs` | UInt64[] | True | List of LoRaWAN DevEUIs potentially associated with the upstream message |
| `Radio` | [Radio](#radio-model) | True | Radio data |
| `PHYPayloadNoMIC` | UInt8[] | True | PHYPayload with detached MIC |
| `MICChallenge` | UInt32[] | True| List of MICs for upstream traffic for the [MIC challenge procedure]() |

#### Example:
```json
{
	"ProtocolVersion": 1,
	"TransactionID": 4,
	"DevEUIs": [8844537008791951183],
	"Radio": {
		"Frequency": 868100000,
		"LoRa": {
			"Spreading": 12,
			"Bandwidth": 125000
		},
		"RSSI": -52.0,
		"SNR": -3.0
	},
	"PHYPayloadNoMIC": [64, 184, 174, 199, 114, 128, 1, 0, 1, 69, 180, 115, 127],
	"MICChallenge": [1308830714,114830713, 170883]
}
```

### UpstreamAck Message

| Field | Type | Mandatory | Description |
| ----- | ---- | ----------- | ---|
| `ProtocolVersion` | UInt32 | True | RAN protocol version |
| `TransactionID` | UInt64 | True | ID of the corresponding Upstream message |
| `MIC` | UInt32 | True | LNS-calculated MIC according to the [MIC challenge procedure](#mic-challenge-procedure) |
| `DevEUI` | UInt64 | True | DevEUI of the device associated with the upstream message |

#### Example

```json
{
	"ProtocolVersion": 1,
	"TransactionID": 4,
	"DevEUI": 8844537008791951183,
	"MIC": 1308830714
}
```


### UpstreamReject Message

| Field | Type | Mandatory | Description |
| ----- | ---- | ----------- | ---|
| `ProtocolVersion` | UInt32 | True | RAN protocol version |
| `TransactionID` | UInt64 | True | ID of the corresponding Upstream message |
| `ResultCode` | Enum[`MICFailed`, `Other`] | True | Code of reason why upstream was rejected |
| `ResultMessage` | String | Optional | An optional message with a human explanation why uplink could not be rejected  |

#### Example

```json
{
	"ProtocolVersion": 1,
	"TransactionID": 4,
	"DevEUI": 8844537008791951183,
	"ResultCode": "MICFailed"
}
```

### Downstream Message

| Field | Type | Mandatory | Description |
| ----- | ---- | ----------- | ---- |
| `ProtocolVersion` | UInt32 | True | RAN protocol version |
| `TransactionID` | UInt64 | True | Unique Downstream identifier provided by the LNS. It is requred to associate `DownstreamAck` and `DownstreamResult` with this downstream message later. |
| `DevEUI` | UInt64 | True | LoRaWAN DevEUI |
| `TargetDevAddr` | UInt32 | True for JoinAccept |  Mandatory for join accept messages. In the due course of the Join procedure device may end up having two device addresses: device address that was active before join procedure has started and target device address provided in JoinAccept message. |
| `TxWindow` | [TransmissionWindow](#Transmission-Window) | True | Transmission window object |
| `PHYPayload` | UInt8[] | True | Full PHYPayload |


#### Example
```json
{
	"ProtocolVersion": 1,
	"TransactionID": 1,
	"DevEUI": 8844537008791951183,
	"TxWindow": {
		"Radio": {
			"Frequency": 868300000,
			"LoRa": {
				"Spreading": 12,
				"Bandwidth": 125000
			}
		},
		"Delay": 5
	},
	"PHYPayload": [97, 98, 97, 98]
}
```
### DownstreamAck

Reception of this message means that RAN received a `Downstream` message from LNS and about to process it.

| Field | Type | Mandatory | Description |
| ----- | ---- | --------- | ----------- |
| `ProtocolVersion` | UInt32 | True | RAN protocol version |
| `TransactionID` | UInt64 | True| RAN request ID |
| `MailboxID` | UInt64 | True | MailboxID to obtain downstream transmission history later |

#### Example

```json
{
	"ProtocolVersion": 1,
	"TransactionID": 1,
	"MailboxID": 1
}
```

### DownstreamResult

Reception of this message means that RAN received `Downstream` message from LNS and processed it. Processing result is reported in `Mailbox` section of the message.

| Field | Type | Mandatory | Description |
| ----- | ---- | --------- | ----------- |
| `ProtocolVersion` | UInt32 | True | RAN protocol version |
| `TransactionID` | UInt64 | True | RAN request ID |
| `ResultCode` | Enum[`Success`, `WindowNotFound`] | True | Downstream transmission status code: transmitted, not transmitted, error.  |
| `ResultMessage` | UInt32 | True | Downstream transmission status message |
| `MailboxID` | UInt64 | True | MailboxID to obtain downstream transmission history later |

#### Example

```json
{
	"ProtocolVersion": 1,
	"TransactionID": 1,
	"ResultCode": "Success",
	"ResultMessage": "Success",
	"MailboxID": 1
}
```

## Models

### Radio Model

| Field | Type | Mandatory | Description |
| ----- | ---- | --------- | ----------- |
| `RSSI` | Float | True for Uplink | Received signal strength indicator |
| `SNR` | Float | True for Uplink | Signal to noise ratio |
| `Frequency` | Uint32 | True | Central frequency of the radio signal, in Hz |
| `LoRa.Spreading` | Uint4 | True | LoRa modulation spreading factor, max value is 12 |
| `LoRa.Bandwidth` | UInt16 | True| LoRa modulation signal bandwidth in Hz |
| `FSK.FrequencyDeviation` | UInt32 | True | FSK modulation frequency deviation in Hz |
| `FSK.BitRate` | UInt32 | True | FSK modulation bitrate in bits per second |
| `FHSS.OCW` | UInt32 | True | FHSS modulation operating channel width in Hz |
| `FHSS.CodingRate` | String | True | FHSS modulation coding rate |

### Transmission Window

| Field | Type | Mandatory | Description |
| ----- | ---- | --------- | ----------- |
| `Delay` | UInt4 | True for Class A | Used for Class A downlinks. Delays are measured using the last acknowledged `Upstream` message for the same DevEUI (no need to provide UpstreamID). Such a message is automatically identified by the RAN. |
| `TMMS`  | Uint64[] | True for Class B | GPS-time transmission slots for Class B messages. Not more than 8 slots. |
| `Deadline` | Timestamp | True for Class C | Transmission deadline for Class C downlink. RAN will schedule downlink till the deadline (if possible). Default and maximum deadline value is now + 512 seconds. |
| `Radio` | [Radio](#radio-model) | True | [Radio](#radio-model) transmission parameters |

