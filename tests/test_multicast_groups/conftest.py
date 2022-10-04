from datetime import datetime
from itertools import count
from typing import List, Optional

import pytest
from pydantic import BaseModel

_GROUP_ID = count()
next(_GROUP_ID)


class TestMulticastGroup(BaseModel):
    # Device model without constraints
    id: Optional[int]
    created_at: Optional[datetime]
    name: Optional[str]
    addr: Optional[int]
    devices: Optional[List[int]]


def _multicast_group_factory(*, id=None, created_at=None, name=None, addr=None, devices=None):
    created_at = datetime.utcnow() if created_at is None else created_at
    id = next(_GROUP_ID) if id is None else id
    devices = [] if devices is None else devices
    multicast_group_dict = {
        "created_at": created_at.isoformat(),
        "id": id,
        "name": name,
        "addr": f"{addr:08x}" if addr is not None else None,
        "devices": devices,
    }
    multicast_group_model = TestMulticastGroup(
        id=id,
        created_at=created_at,
        name=name,
        addr=addr,
        devices=devices,
    )
    return multicast_group_dict, multicast_group_model


@pytest.fixture
def make_multicast_group():
    return _multicast_group_factory


@pytest.fixture
def multicast_group(request):
    return _multicast_group_factory(**request.param)
