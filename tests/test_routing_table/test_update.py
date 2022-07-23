import pytest

from ran.routing.core import Core
from ran.routing.core.domains import Device
from ran.routing.core.routing_table.consts import ApiErrorCode
from ran.routing.core.routing_table.exceptions import ApiUnknownError, ApiValidationFailedError, ParameterError


def device_as_update_params(device: Device):
    # Preparing insert method params
    return {
        "dev_eui": device.dev_eui,
        "join_eui": device.join_eui,
        "active_dev_addr": device.active_dev_addr,
        "target_dev_addr": device.target_dev_addr,
    }


def device_dict_as_update_dict(device_dict):
    data = {
        "DevEUI": device_dict["DevEUI"],
        "JoinEUI": device_dict["JoinEUI"],
    }
    if device_dict["ActiveDevAddr"]:
        data["ActiveDevAddr"] = device_dict["ActiveDevAddr"]
    if device_dict["TargetDevAddr"]:
        data["TargetDevAddr"] = device_dict["TargetDevAddr"]
    return data


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "target_dev_addr": 0xFFFFFFFF},
        {
            "dev_eui": 0xFFFFFFFFFFFFFFFF,
            "join_eui": 0xFFFFFFFFFFFFFFFF,
            "active_dev_addr": 0xFFFFFFFF,
            "target_dev_addr": 0xFFFFFFFF,
        },
    ],
    indirect=True,
)
async def test_routing_table_update(core: Core, client_session, device):
    device_dict, device_model = device

    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 200
    client_session.post.return_value.__aenter__.return_value.json.return_value = device_dict

    device = await core.routing_table.update(**device_as_update_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/update", json=device_dict_as_update_dict(device_dict)
    )
    assert device == device_model


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Negative scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        # Important fields is None
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
        {"join_eui": 0xFFFFFFFFFFFFFFFF, "target_dev_addr": 0xFFFFFFFF},
        # Not provided active or target dev addr
        {
            "dev_eui": 0xFFFFFFFFFFFFFFFF,
            "join_eui": 0xFFFFFFFFFFFFFFFF,
            "active_dev_addr": None,
            "target_dev_addr": None,
        },
        # Wrong values
        {"dev_eui": 0xFFFFFFFFFFFFFFFF + 1, "join_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF + 1, "active_dev_addr": 0xFFFFFFFF},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF + 1},
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "target_dev_addr": 0xFFFFFFFF + 1},
    ],
    indirect=True,
)
async def test_routing_table_update_parameter_error(core: Core, client_session, device):
    device_dict, device_model = device
    with pytest.raises(ParameterError):
        await core.routing_table.update(**device_as_update_params(device_model))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
    ],
    indirect=True,
)
async def test_routing_table_update_remote_validation_error(core: Core, client_session, device):
    device_dict, device_model = device

    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 422
    client_session.post.return_value.__aenter__.return_value.json.return_value = {
        "detail": {"error_code": ApiErrorCode.VALIDATION_FAILED}
    }

    with pytest.raises(ApiValidationFailedError):
        await core.routing_table.update(**device_as_update_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/update", json=device_dict_as_update_dict(device_dict)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device",
    [
        {"dev_eui": 0xFFFFFFFFFFFFFFFF, "join_eui": 0xFFFFFFFFFFFFFFFF, "active_dev_addr": 0xFFFFFFFF},
    ],
    indirect=True,
)
async def test_routing_table_update_remote_unknown_error(core: Core, client_session, device):
    device_dict, device_model = device
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 418

    with pytest.raises(ApiUnknownError):
        await core.routing_table.update(**device_as_update_params(device_model))
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/update", json=device_dict_as_update_dict(device_dict)
    )
