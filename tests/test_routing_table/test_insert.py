import pytest

from ran.routing.core import Core
from ran.routing.core.domains import Device
from ran.routing.core.routing_table.consts import ApiErrorCode
from ran.routing.core.routing_table.exceptions import ApiUnknownError, ApiValidationFailedError, ParameterError


def device_as_insert_params(device: Device):
    # Preparing insert method params
    params = device.dict()
    for key in ("created_at", "target_dev_addr", "details"):
        if key in params:
            params.pop(key)

    if "active_dev_addr" in params:
        params["dev_addr"] = params.pop("active_dev_addr")
    return params


def device_dict_as_insert_dict(device_dict):
    data = {k: v for k, v in device_dict.items() if k not in ("CreatedAt", "TargetDevAddr") and v is not None}
    if "ActiveDevAddr" in data:
        data["DevAddr"] = data.pop("ActiveDevAddr")
    return data


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF},
    ],
    indirect=True,
)
async def test_routing_table_insert(core: Core, client_session, device):
    device_dict, device_model = device

    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 201
    client_session.post.return_value.__aenter__.return_value.json.return_value = device_dict

    device = await core.routing_table.insert(**device_as_insert_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/insert", json=device_dict_as_insert_dict(device_dict)
    )
    assert device == device_model


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Negative scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF + 1, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF + 1},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF + 1, "join_eui": 0xFFFFFFFFFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF + 1},
        {"dev_eui": -1, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": -1},
        {"dev_eui": -1, "join_eui": 0xFFFFFFFFFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": -1},
        # {"dev_eui": "random_string", "active_dev_addr": 0xFFFFFFFF},
        # {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": "random_string"},
        # {"dev_eui": "random_string", "join_eui": 0xFFFFFFFFFFFFFFFF},
        # {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": "random_string"},
    ],
    indirect=True,
)
async def test_routing_table_insert_param_error(core: Core, client_session, device):
    device_dict, device_model = device
    with pytest.raises(ParameterError):
        await core.routing_table.insert(**device_as_insert_params(device_model))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
    ],
    indirect=True,
)
async def test_routing_table_insert_remote_validation_error(core: Core, client_session, device):
    device_dict, device_model = device

    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 422
    client_session.post.return_value.__aenter__.return_value.json.return_value = {
        "detail": {"error_code": ApiErrorCode.VALIDATION_FAILED}
    }

    with pytest.raises(ApiValidationFailedError):
        await core.routing_table.insert(**device_as_insert_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/insert", json=device_dict_as_insert_dict(device_dict)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
    ],
    indirect=True,
)
async def test_routing_table_insert_remote_unknown_error(core: Core, client_session, device):
    device_dict, device_model = device

    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 418

    with pytest.raises(ApiUnknownError):
        await core.routing_table.insert(**device_as_insert_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/insert", json=device_dict_as_insert_dict(device_dict)
    )
