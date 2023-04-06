import pytest

from ran.routing.core import Core
from ran.routing.core.routing_table.consts import ApiErrorCode
from ran.routing.core.routing_table import exceptions

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
async def test_routing_table_select(core: Core, client_session, make_device):
    device_dict, device_model = make_device(dev_eui=0x7ABE1B8C93D7174F, active_dev_addr=0xFF92D2A8)
    client_session.get.return_value.__aenter__.return_value.ok = True
    client_session.get.return_value.__aenter__.return_value.json.return_value = [device_dict]
    client_session.get.return_value.__aenter__.return_value.status = 200

    devices = await core.routing_table.select()
    client_session.get.assert_called_with(core._Core__api_endpoint_schema.routing / "devices/select", params={})
    assert devices[0] == device_model


@pytest.mark.asyncio
async def test_routing_table_select_offset(core: Core, client_session, make_device):
    device_dict, device_model = make_device(dev_eui=0x7ABE1B8C93D7174F, active_dev_addr=0xFF92D2A8)
    client_session.get.return_value.__aenter__.return_value.ok = True
    client_session.get.return_value.__aenter__.return_value.json.return_value = [device_dict]
    client_session.get.return_value.__aenter__.return_value.status = 200

    devices = await core.routing_table.select(offset=1)
    client_session.get.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/select", params={"offset": 1}
    )
    assert devices[0] == device_model


@pytest.mark.asyncio
async def test_routing_table_select_limit(core: Core, client_session, make_device):
    device_dict, device_model = make_device(dev_eui=0x7ABE1B8C93D7174F, active_dev_addr=0xFF92D2A8)
    client_session.get.return_value.__aenter__.return_value.ok = True
    client_session.get.return_value.__aenter__.return_value.json.return_value = [device_dict]
    client_session.get.return_value.__aenter__.return_value.status = 200

    devices = await core.routing_table.select(limit=1)
    client_session.get.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/select", params={"limit": 1}
    )
    assert devices[0] == device_model


@pytest.mark.asyncio
async def test_routing_table_select_dev_euis(core: Core, client_session, make_device):
    device_dict, device_model = make_device(dev_eui=0x7ABE1B8C93D7174F, active_dev_addr=0xFF92D2A8)
    client_session.get.return_value.__aenter__.return_value.ok = True
    client_session.get.return_value.__aenter__.return_value.json.return_value = [device_dict]
    client_session.get.return_value.__aenter__.return_value.status = 200

    devices = await core.routing_table.select(dev_euis=[0x7ABE1B8C93D7174F])
    client_session.get.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/select", params={"DevEUIs": ["7abe1b8c93d7174f"]}
    )
    assert devices[0] == device_model


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Negative scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize("dev_eui", ["some_string", 0xFFFFFFFFFFFFFFFF + 1])
async def test_routing_table_select_dev_euis_parameter_error(core: Core, dev_eui):
    with pytest.raises(exceptions.ParameterError):
        await core.routing_table.select(dev_euis=[dev_eui])


@pytest.mark.asyncio
async def test_routing_table_select_limit_parameter_error(core: Core):
    with pytest.raises(exceptions.ParameterError):
        await core.routing_table.select(limit=-1)


@pytest.mark.asyncio
async def test_routing_table_select_offset_parameter_error(core: Core):
    with pytest.raises(exceptions.ParameterError):
        await core.routing_table.select(offset=-1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
    ],
)
async def test_routing_table_select_api_error(core: Core, client_session, api_error, exception):
    client_session.get.return_value.__aenter__.return_value.ok = False
    client_session.get.return_value.__aenter__.return_value.status = 422
    client_session.get.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        await core.routing_table.select()
    client_session.get.assert_called_with(core._Core__api_endpoint_schema.routing / "devices/select", params={})
