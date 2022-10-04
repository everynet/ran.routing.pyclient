from datetime import datetime
from typing import Optional

import pytest
from pydantic import BaseModel

from ran.routing.core.domains import Device


class TestDevice(BaseModel):
    # Device model without constraints
    created_at: Optional[datetime]
    dev_eui: Optional[int]
    join_eui: Optional[int]
    active_dev_addr: Optional[int]
    target_dev_addr: Optional[int]
    details: Optional[str]


def _device_factory(*, dev_eui=None, join_eui=None, active_dev_addr=None, target_dev_addr=None, details=None):
    created_at = datetime.utcnow()
    device_dict = {
        "CreatedAt": created_at.isoformat(),
        "DevEUI": None if dev_eui is None else f"{dev_eui:0x}",
        "JoinEUI": None if join_eui is None else f"{join_eui:0x}",
        "ActiveDevAddr": None if active_dev_addr is None else f"{active_dev_addr:0x}",
        "TargetDevAddr": None if target_dev_addr is None else f"{target_dev_addr:0x}",
        "Details": details,
    }
    device_model = TestDevice(
        created_at=created_at,
        dev_eui=dev_eui,
        join_eui=join_eui,
        active_dev_addr=active_dev_addr,
        target_dev_addr=target_dev_addr,
        details=details,
    )
    return device_dict, device_model


@pytest.fixture
def make_device():
    return _device_factory


@pytest.fixture
def device(request):
    return _device_factory(**request.param)
