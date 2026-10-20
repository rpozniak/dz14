import pytest
import pytest_asyncio
from bleak import BleakClient, BleakScanner


@pytest_asyncio.fixture
async def ble_client(device):
    target = await BleakScanner.find_device_by_name("SENTRY-BLE", timeout=5.0)
    if target is None:
        # The peripheral stops advertising while another client is connected.
        # Clear any partial UART command before asking it to disconnect.
        device.send_line("")
        device.send_line("disconnect")
        target = await BleakScanner.find_device_by_name("SENTRY-BLE", timeout=15.0)
    if target is None:
        pytest.fail(
            "SENTRY-BLE не знайдено навіть після UART disconnect: "
            "перевірте BLE-прошивку та Bluetooth"
        )

    async with BleakClient(target, timeout=15.0) as client:
        if not client.is_connected:
            pytest.fail("Не вдалося підключитися до SENTRY-BLE")
        yield client
