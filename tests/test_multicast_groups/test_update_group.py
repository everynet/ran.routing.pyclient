import pytest

from ran.routing.core import Core
from ran.routing.core.multicast_groups import exceptions
from ran.routing.core.multicast_groups.consts import ApiErrorCode

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Positive scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "multicast_group",
    [
        {"addr": 0xFFFFFFFF, "name": "test1"},
        {"addr": 0x1, "name": "test2"},
    ],
    indirect=True,
)
async def test_multicast_groups_update_group(core: Core, client_session, multicast_group):
    multicast_group_dict, multicast_group_model = multicast_group

    client_session.post.return_value.__aenter__.return_value.ok = True
    client_session.post.return_value.__aenter__.return_value.status = 201
    client_session.post.return_value.__aenter__.return_value.json.return_value = multicast_group_dict

    multicast_group = await core.multicast_groups.update_multicast_group(
        addr=0xFFFFFFFF,
        new_name=multicast_group_model.name,
        new_addr=multicast_group_model.addr,
    )

    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "update",
        json={
            "addr": "ffffffff",
            "update": {"name": multicast_group_model.name, "addr": f"{multicast_group_model.addr:08x}"},
        },
    )
    assert multicast_group == multicast_group_model


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "multicast_group",
    [
        {"addr": None, "name": None},
        {"addr": 0xFFFFFFFF + 1, "name": "test1"},
        {"addr": 0x0 - 1, "name": "test2"},
        {"addr": 0xFFFFFFFF, "name": "x" * 256},
    ],
    indirect=True,
)
async def test_multicast_groups_update_group_parameter_error(core: Core, client_session, multicast_group):
    multicast_group_dict, multicast_group_model = multicast_group
    with pytest.raises(exceptions.ParameterError):
        multicast_group = await core.multicast_groups.update_multicast_group(
            addr=0xFFFFFFFF,
            new_name=multicast_group_model.name,
            new_addr=multicast_group_model.addr,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("multicast_group", [{"addr": 0xFFFFFFFF, "name": "test1"}], indirect=True)
@pytest.mark.parametrize(
    "api_error, exception",
    [
        (ApiErrorCode.UNKNOWN, exceptions.ApiUnknownError),
        (ApiErrorCode.UNAUTHORIZED, exceptions.ApiUnauthorizedError),
        (ApiErrorCode.VALIDATION_FAILED, exceptions.ApiValidationFailedError),
        (ApiErrorCode.MC_NOT_FOUND, exceptions.ApiMulticastGroupNotFoundError),
    ],
)
async def test_multicast_groups_update_group_api_error(
    core: Core, client_session, multicast_group, api_error, exception
):
    multicast_group_dict, multicast_group_model = multicast_group

    client_session.post.return_value.__aenter__.return_value.ok = False
    client_session.post.return_value.__aenter__.return_value.status = 400
    client_session.post.return_value.__aenter__.return_value.json.return_value = {"detail": {"error_code": api_error}}

    with pytest.raises(exception):
        multicast_group = await core.multicast_groups.update_multicast_group(
            addr=0xFFFFFFFF,
            new_name=multicast_group_model.name,
            new_addr=multicast_group_model.addr,
        )
    client_session.post.assert_called_with(
        core._Core__api_endpoint_schema.multicast / "multicast-groups" / "update",
        json={
            "addr": "ffffffff",
            "update": {"name": multicast_group_model.name, "addr": f"{multicast_group_model.addr:08x}"},
        },
    )
