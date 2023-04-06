import pytest

from ran.routing.core import Core
from ran.routing.core.multicast_groups import exceptions
from ran.routing.core.multicast_groups.consts import ApiErrorCode

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize("dev_eui", [0xFFFFFFFFFFFFFFFF])
async def test_multicast_groups_add_device(core: Core, client_session, dev_eui):
    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 201
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"is_added": 1}

    is_created = await core.multicast_groups.add_device_to_multicast_group(addr=0xFFFFFFFF, dev_eui=dev_eui)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "add-device",
        json={"addr": "ffffffff", "dev_eui": f"{dev_eui:016x}"},
    )
    assert is_created == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("dev_eui", [0xFFFFFFFFFFFFFFFF + 1, "FFFF", None])
async def test_multicast_groups_add_device_parameter_error(core: Core, dev_eui):
    with pytest.raises(exceptions.ParameterError):
        await core.multicast_groups.add_device_to_multicast_group(addr=0xFFFFFFFF, dev_eui=dev_eui)


@pytest.mark.asyncio
async def test_multicast_groups_add_device_parameter_error_id(core: Core):
    with pytest.raises(exceptions.ParameterError):
        await core.multicast_groups.add_device_to_multicast_group(addr="TEST", dev_eui=0xFFFFFFFFFFFFFFFF)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
        (ApiErrorCode.MC_NOT_FOUND, exceptions.ApiMulticastGroupNotFoundError),
        (ApiErrorCode.MC_ALREADY_CONTAINS_DEVICE, exceptions.ApiMulticastGroupAlreadyContainsDeviceError),
    ],
)
@pytest.mark.parametrize("dev_eui", [0xFFFFFFFFFFFFFFFF])
async def test_multicast_groups_add_device_api_error(core: Core, client_session, dev_eui, api_error, exception):
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 400
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        await core.multicast_groups.add_device_to_multicast_group(addr=0xFFFFFFFF, dev_eui=dev_eui)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "add-device",
        json={"addr": "ffffffff", "dev_eui": f"{dev_eui:016x}"},
    )
