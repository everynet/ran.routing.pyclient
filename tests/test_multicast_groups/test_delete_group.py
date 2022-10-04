import pytest

from ran.routing.core import Core
from ran.routing.core.multicast_groups import exceptions
from ran.routing.core.multicast_groups.consts import ApiErrorCode

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
async def test_multicast_groups_delete(core: Core, client_session):
    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 200
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"deleted": 1}

    deleted = await core.multicast_groups.delete_multicast_group(multicast_group_id=1)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "delete", json={"id": 1}
    )
    assert deleted == 1


@pytest.mark.asyncio
async def test_multicast_groups_delete_parameter_error(core: Core):
    with pytest.raises(exceptions.ParameterError):
        await core.multicast_groups.delete_multicast_group(multicast_group_id="TEST")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
        (ApiErrorCode.MC_NOT_FOUND, exceptions.ApiMulticastGroupNotFoundError),
    ],
)
async def test_multicast_groups_delete_api_error(core: Core, client_session, api_error, exception):
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 400
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        await core.multicast_groups.delete_multicast_group(multicast_group_id=1)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "delete", json={"id": 1}
    )
