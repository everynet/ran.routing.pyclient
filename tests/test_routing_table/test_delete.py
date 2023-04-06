import pytest

from ran.routing.core import Core
from ran.routing.core.routing_table.consts import ApiErrorCode
from ran.routing.core.routing_table import exceptions

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
async def test_routing_table_delete(core: Core, client_session):
    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 200
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"deleted": 1}

    dev_euis = [0xFFFFFFFFFFFFFFFF]
    deleted = await core.routing_table.delete(dev_euis=dev_euis)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/drop", json={"DevEUIs": [f"{d:016x}" for d in dev_euis]}
    )
    assert deleted == 1


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Negative scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize("dev_eui", [0xFFFFFFFFFFFFFFFF + 1])
async def test_routing_table_delete_parameter_error(core: Core, client_session, dev_eui):
    dev_euis = [dev_eui]
    with pytest.raises(exceptions.ParameterError):
        await core.routing_table.delete(dev_euis=dev_euis)
    assert not client_session.post.called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
    ],
)
async def test_routing_table_delete_api_error(core: Core, client_session, api_error, exception):
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 422
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    dev_euis = [0xFFFFFFFFFFFFFFFF]
    with pytest.raises(exception):
        await core.routing_table.delete(dev_euis=dev_euis)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.routing / "devices/drop", json={"DevEUIs": [f"{d:016x}" for d in dev_euis]}
    )


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
async def test_routing_table_delete_all(core: Core, client_session):
    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 200
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"deleted": 100}

    deleted = await core.routing_table.delete_all()
    client_session.post.assert_called_with(core._Core__api_endpoint_schema.routing / "devices/drop-all")
    assert deleted == 100


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Negative scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
    ],
)
async def test_routing_table_delete_all_remote_api_error(core: Core, client_session, api_error, exception):
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 422
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        await core.routing_table.delete_all()
    client_session.post.assert_called_with(core._Core__api_endpoint_schema.routing / "devices/drop-all")
