import uuid

import pytest

from drivers.device_driver import DeviceTimeout

@pytest.mark.wifi
@pytest.mark.parametrize(
    "variant_name",
    [
        "uppercase_suffix",
        "lowercase_suffix",
        "without_space",
        "double_space",
        "trailing_space",
        "extra_letter",
        "extra_digit",
        "digits_only",
    ],
)
def test_wrong_password(disconnected_device, wifi_credentials, variant_name):
    ssid, correct_password = wifi_credentials

    variants = {
        "uppercase_suffix": correct_password[:-2] + correct_password[-2:].upper(),
        "lowercase_suffix": correct_password[:-2] + correct_password[-2:].lower(),
        "without_space": correct_password.replace(" ", "", 1),
        "double_space": correct_password.replace(" ", "  ", 1),
        "trailing_space": correct_password + " ",
        "extra_letter": correct_password + "c",
        "extra_digit": correct_password + "1",
        "digits_only": correct_password.split(" ", 1)[0],
    }
    wrong_password = variants[variant_name]

    if wrong_password == correct_password or len(wrong_password) < 8:
        pytest.fail(f"{variant_name}: не підходить поточний тестовий пароль")

    device = disconnected_device
    connected = device.wifi_connect(ssid, wrong_password)
    assert connected is False, f"{variant_name}: підключення з хибним паролем вдалося"

    response = device.last_response.lower()
    failure_markers = (
        "failed to connect",
        "connection timeout",
        "connect to the ap fail",
    )
    if not any(phrase in response for phrase in failure_markers):
        safe_uart_lines = [
            line.strip()
            for line in device.last_response.splitlines()
            if "wifi station:" in line.lower() and "password" not in line.lower()
        ]
        pytest.fail(
            f"{variant_name}: wifi_connect повернув False, але у прочитаній UART-відповіді "
            f"немає очікуваної фрази про помилку. Останні рядки UART: "
            f"{safe_uart_lines[-5:]}"
        )

    status = device.wifi_status()
    assert status["connected"] is False, f"{variant_name}: пристрій показує підключення"


@pytest.mark.wifi
@pytest.mark.parametrize(
    "short_password",
    [pytest.param("", id="empty"), pytest.param("1234567", id="seven_chars")],
)
def test_short_password(disconnected_device, wifi_credentials, short_password):
    ssid, _ = wifi_credentials
    device = disconnected_device

    connected = device.wifi_connect(ssid, short_password)

    assert connected is False
    assert "password too short" in device.last_response.lower()
    with pytest.raises(DeviceTimeout):
        device.wait_for_pattern(r"connecting to SSID", timeout=1.0)
    assert device.wifi_status()["connected"] is False


@pytest.mark.wifi
def test_nonexistent_ssid(disconnected_device, wifi_credentials):
    device = disconnected_device
    _, correct_password = wifi_credentials
    missing_ssid = f"DZ14_missing_{uuid.uuid4().hex[:8]}"

    connected = device.wifi_connect(missing_ssid, correct_password)

    assert connected is False, "Неіснуюча мережа не повинна підключитися"
    response = device.last_response.lower()
    assert "brownout" not in response and "esp-rom" not in response, (
        "Плата перезавантажилася під час перевірки неіснуючої мережі"
    )
    assert "Available commands:" in device.help()
