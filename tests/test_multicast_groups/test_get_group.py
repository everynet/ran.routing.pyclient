import pytest

from ran.routing.core import Core
from ran.routing.core.multicast_groups import exceptions
from ran.routing.core.multicast_groups.consts import ApiErrorCode


@pytest.mark.asyncio
async def test_multicast_groups_select(core: Core, client_session, make_multicast_group):
    multicast_group_dict, multicast_group_model = make_multicast_group(addr=0xFFFFFFFF, name="test")
    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.json.return_value = [multicast_group_dict]
    client_session.post.return_value.__aenter__.return_value.status = 200

    multicast_groups = await core.multicast_groups.get_multicast_groups(0xFFFFFFFF)
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "get", json={"addrs": ["ffffffff"]}
    )
    assert multicast_groups[0] == multicast_group_model


@pytest.mark.asyncio
@pytest.mark.parametrize("select_id", ["some_string", None])
async def test_multicast_groups_select_parameter_error(core: Core, select_id):
    with pytest.raises(exceptions.ParameterError):
        await core.multicast_groups.get_multicast_groups(select_id)


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
async def test_multicast_groups_select_api_error(core: Core, client_session, api_error, exception):
    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 400
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        await core.multicast_groups.get_multicast_groups()
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "get", json={"addrs": []}
    )
