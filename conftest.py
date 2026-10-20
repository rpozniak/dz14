import os

import pytest

from drivers.device_driver import DeviceDriver


@pytest.fixture
def device():
    vid = int(os.environ.get("UART_VID", "1A86"), 16)
    driver = DeviceDriver(vid=vid)
    driver.open()
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture
def wifi_credentials():
    ssid = os.environ.get("WIFI_SSID")
    password = os.environ.get("WIFI_PASSWORD")
    if not ssid or not password:
        pytest.fail("Set WIFI_SSID and WIFI_PASSWORD for the test hotspot")
    return ssid, password


@pytest.fixture
def disconnected_device(device):
    device.reboot()
    status = device.wifi_status()
    assert status["connected"] is False, f"Після reboot стан: {status}"
    return device
