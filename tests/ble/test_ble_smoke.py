import asyncio

import pytest


LED_UUID = "00001525-1212-efde-1523-785feabcd123"


@pytest.mark.ble
@pytest.mark.asyncio
async def test_ble_led_dual_channel(device, ble_client):
    device.clear_input()
    await ble_client.write_gatt_char(LED_UUID, b"\x01", response=True)
    on_log = await asyncio.to_thread(
        device.wait_for_pattern, r"GATTS_DEMO:\s*LED ON!", 5.0
    )
    assert "LED ON!" in on_log

    device.clear_input()
    await ble_client.write_gatt_char(LED_UUID, b"\x00", response=True)
    off_log = await asyncio.to_thread(
        device.wait_for_pattern, r"GATTS_DEMO:\s*LED OFF!", 5.0
    )
    assert "LED OFF!" in off_log
