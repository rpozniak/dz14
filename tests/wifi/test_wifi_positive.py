import os

import re
import pytest


@pytest.mark.wifi
def test_scan_finds_networks(disconnected_device):
    expected_ssid = os.environ.get("WIFI_SSID")
    assert expected_ssid, "Не задано WIFI_SSID"

    networks = disconnected_device.wifi_scan()

    assert networks, "Сканування повернуло порожній список"
    assert expected_ssid in networks, f"Мережі {expected_ssid!r} немає серед {networks}"

@pytest.mark.wifi
def test_connect_success(disconnected_device, wifi_credentials):
    ssid, password = wifi_credentials

    connected = disconnected_device.wifi_connect(ssid, password)
    assert connected, "Не вдалося підключитися до Wi-Fi"

    status = disconnected_device.wifi_status()
    assert status["connected"] is True
    assert status["ssid"] == ssid
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", status["ip"])
    assert status["ip"] != "0.0.0.0"

@pytest.mark.wifi
def test_disconnect(disconnected_device, wifi_credentials):
    ssid, password = wifi_credentials
    device = disconnected_device

    connected = device.wifi_connect(ssid, password)
    assert connected, "Не вдалося підключитися перед перевіркою disconnect"
    assert device.wifi_status()["connected"] is True

    device.wifi_disconnect()
    status = device.wifi_status()
    if status == {"connected": True, "ssid": "", "ip": "0.0.0.0", "rssi": 0}:
        pytest.xfail("FR-W5: після disconnect status помилково показує connected")

    assert status["connected"] is False, f"Після disconnect отримали: {status}"

@pytest.mark.wifi
def test_credentials_survive_reboot(disconnected_device, wifi_credentials):
    ssid, password = wifi_credentials
    device = disconnected_device

    connected = device.wifi_connect(ssid, password)
    assert connected, "Початкове підключення не вдалося"
    assert device.wifi_status()["ssid"] == ssid

    device.reboot()
    assert device.wifi_status()["connected"] is False

    connected_from_saved = device.wifi_connect("", "")
    assert connected_from_saved, "Підключення зі збереженими даними не вдалося"

    status = device.wifi_status()
    assert status["connected"] is True
    assert status["ssid"] == ssid
    assert status["ip"] != "0.0.0.0"