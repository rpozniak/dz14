# DZ-14 — звіт про тестування

## Частина A — Wi-Fi (`station_WiFi`)

Тестова мережа: хотспот iPhone у режимі 2,4 ГГц («Максимальна сумісність»). SSID і пароль передаються тестам через `WIFI_SSID` та `WIFI_PASSWORD`; пароль у звіті не зберігається.

### Конфігурація тестової мережі

Перед запуском у терміналі задавали `WIFI_SSID` як назву хотспота, а `WIFI_PASSWORD` — як його чинний пароль. Значення не записувалися в код або файли проєкту:

```bash
export WIFI_SSID='<SSID хотспота>'
read -r -s WIFI_PASSWORD
export WIFI_PASSWORD
```

Після `read` потрібно ввести пароль і натиснути Enter; ввід не показується на екрані. Для параметризованих негативних тестів пароль хотспота має формат: 9 цифр, пробіл, мала латинська літера, велика латинська літера. Це умова тестових даних, а не вимога прошивки.

### Покриття вимог

| Тест | Що перевіряє | Вимога |
| --- | --- | --- |
| `test_scan_finds_networks` | Сканування знаходить тестовий хотспот | FR-W1 |
| `test_connect_success` | Підключення з валідними даними; `status` показує SSID та IP | FR-W2, FR-W5 |
| `test_disconnect` | Після `disconnect` стан має бути відключеним | FR-W5 |
| `test_credentials_survive_reboot` | Збережені дані працюють після перезавантаження | FR-W4 |
| `test_wrong_password` | Вісім варіантів хибного пароля не дають підключення | A3 домашнього завдання |
| `test_short_password` | Порожній пароль і 7 символів відхиляються до підключення | FR-W3 |
| `test_nonexistent_ssid` | Неіснуюча мережа не підключається, плата відповідає на `help` | A3 домашнього завдання |

### Прогін автотестів

Команда: `python -m pytest tests/wifi -v`

Результат повного прогону: **14 passed, 1 xfailed** за 194,20 с. `test_disconnect` має очікуваний `XFAIL` для описаного нижче дефекту; інших падінь немає.

Доказ: [скріншот повного прогону](evidence/wifi/pytest_full.png) з командою, усіма результатами та підсумком pytest.

### Баг-репорт

**ID:** BUG-WIFI-001

**Назва:** Команда `status` показує `WiFi: connected` після виконання `disconnect`.

**Опис:** Після розриву Wi-Fi-з'єднання прошивка підтверджує `disconnected`, але наступна команда `status` повідомляє `connected` із порожнім SSID та IP `0.0.0.0`.

**Вимога:** FR-W5 — якщо пристрій не підключений, `status` повідомляє про відсутність з'єднання.

**Версії HW/FW та інтерфейс:** ESP32-S3 DevKit, чип ESP32-S3 (QFN56, revision v0.2); прошивка `station_WiFi fw v1.2`; UART, 115200 8N1.

**Передумови:** Пристрій працює з Wi-Fi-прошивкою. Тестовий хотспот увімкнений; пристрій успішно підключений до нього, а `status` показує його SSID та отриману IP-адресу.

**Кроки відтворення:**

1. Виконати команду `disconnect` у UART-консолі.
2. Дочекатися повідомлення `wifi station: disconnected`.
3. Виконати команду `status`.

**Очікуваний результат:** `status` повідомляє, що Wi-Fi не підключений. Точне формулювання цього повідомлення PRD не задає.

**Фактичний результат:** `status` виводить `WiFi: connected`, порожній `SSID`, `IP: 0.0.0.0` і `RSSI: 0 dBm`. Драйвер перетворює цей вивід на `{'connected': True, 'ssid': '', 'ip': '0.0.0.0', 'rssi': 0}`. Сам дефект видно у відповіді прошивки, до розбору її драйвером.

**Відтворюваність:** Проблему зафіксовано під час ручної перевірки та в 5 з 5-ти прогонів автотестів.

**Фрагмент UART-логу:**

```text
disconnect
I (446197) wifi station: disconnected
I (446197) wifi station: connect to the AP fail
status
W (454887) wifi:Haven't to connect to a suitable AP now!
I (454887) wifi station: WiFi: connected
I (454887) wifi station:   SSID:
I (454887) wifi station:   IP:   0.0.0.0
I (454887) wifi station:   RSSI: 0 dBm
```

**Автотест:** `test_disconnect` перевіряє успішне підключення до хотспота перед командою `disconnect`. `xfail` спрацьовує лише для зазначеного поєднання полів `status`; інші відхилення залишаються звичайним падінням тесту.

## Частина B — BLE (`Bluedroid_GATT_Server`)

### Ручний чек-лист

| Перевірка | Дії | Очікування за PRD | Фактичний результат | Доказ | Статус |
| --- | --- | --- | --- | --- | --- |
| Scan | Запустити сканування в nRF Connect for Mobile. | FR-A1: пристрій рекламується як `SENTRY-BLE` і доступний для підключення. | У списку знайдено `SENTRY-BLE` з RSSI −57 dBm; відображається кнопка Connect. | [Скріншот сканування](evidence/ble/scan_sentry_ble.jpg) | PASS |
| Connect + GATT discovery | Підключитися до `SENTRY-BLE` у nRF Connect і відкрити список сервісів. | FR-G1: сервіс Heart Rate `0x180D` з характеристикою `0x2A37` (Read, Indicate). FR-G3: сервіс Automation IO `0x1815` з LED `00001525-1212-efde-1523-785feabcd123` і RELAY `00001526-1212-efde-1523-785feabcd123` (Read, Write). | Застосунок показує `Connected`, обидва сервіси й усі три характеристики з відповідними властивостями. | [Скріншот GATT-сервісів](evidence/ble/gatt_discovery.jpg) | PASS для GATT-структури |
| Пункт 9 — Reconnect | Під час BLE-з'єднання виконати UART-команду `disconnect`, дочекатися відновлення реклами й повторно підключитися через nRF Connect без перезавантаження плати. | FR-A2: реклама відновлюється після розриву; FR-A3: розрив і нове підключення логуються в UART з адресою клієнта. | UART показав `dropping BLE connection`, `Disconnected, remote ... reason 0x16`, `Advertising start successfully`, а потім `Connected, conn_id 0, remote ...` для тієї самої адреси клієнта. Після повторного підключення nRF Connect показує `SENTRY-BLE` зі статусом `Connected` і відкритими GATT-сервісами. Ребуту не було; окремого скрину списку сканування немає. | [UART-лог](evidence/ble/reconnect_cli_uart.png), [nRF Connect після перепідключення](evidence/ble/reconnect_nrf_connected.jpg), [попередній UART-лог](evidence/ble/reconnect_uart.png) | PASS для розриву, реклами й перепідключення; список сканування не зафіксовано |
| Heart Rate indications | У nRF Connect увімкнути індикації характеристики `0x2A37` і спостерігати значення та UART. | FR-G1/FR-G2: пульс у межах 60–80 bpm оновлюється приблизно щосекунди; після підписки клієнт отримує індикації. | У nRF Connect підписка активна; показано `Last Read 78 bpm`. UART зафіксував запис CCCD `02 00`, `Indication enable`, подальші значення 67, 76, 72, 76, 66, 79 bpm з інтервалом близько 1 с та підтвердження `Confirm receive, status 0` після індикацій. | [nRF Connect](evidence/ble/heart_rate_nrf.jpg), [UART-лог](evidence/ble/heart_rate_uart.png) | PASS |
| HR spike | За активної підписки на `0x2A37` надіслати `hr spike` через UART і спостерігати показники в nRF Connect. | FR-C3: пульс зростає приблизно до 190–199 bpm на 5 с, після чого повертається до нормального діапазону. | nRF Connect показав 196 bpm. UART зафіксував `heart rate spike injected (5 ticks)`, послідовно 190, 196, 192, 198, 199 bpm, потім 67 і 74 bpm; для аномальних значень є `Confirm receive, status 0`. | [nRF Connect](evidence/ble/hr_spike_nrf.jpg), [UART-лог](evidence/ble/hr_spike_uart.png) | PASS |
| LED через BLE — увімкнення | У nRF Connect записати однобайтове значення `0x01` у LED-характеристику `00001525-1212-efde-1523-785feabcd123`. | FR-G4: фізичний LED вмикається, UART виводить `LED ON!`. | UART показав `value len 1`, `01`, `LED ON!`; nRF Connect — `Last Write: LED Enabled`; світлодіод на платі засвітився. | [nRF Connect](evidence/ble/led_on_nrf.jpg), [UART-лог](evidence/ble/led_on_uart.png), [фото плати](evidence/ble/led_on_board.jpg) | PASS для `0x01` |
| Пункт 7 — LED read після write `0x01` | Поки LED увімкнений, виконати Read тієї самої характеристики в nRF Connect. | FR-G5: прочитаний стан відповідає `0x01` (LED увімкнений). | `Last Read: LED Enabled` збігається з `Last Write: LED Enabled`. nRF Connect показує декодоване значення; сирий байт у цьому скріні не відображений. | [Скріншот читання LED](evidence/ble/led_read_on_nrf.jpg) | PASS для стану; сирий байт не показано |
| LED через BLE — вимкнення | У nRF Connect записати однобайтове значення `0x00` у LED-характеристику `00001525-1212-efde-1523-785feabcd123`. | FR-G4: фізичний LED вимикається, UART виводить `LED OFF!`. | UART показав `value len 1`, `00`, `LED OFF!`; nRF Connect — `Last Write: LED Disabled`; великий світлодіод на платі згас. `Last Read: LED Enabled` на першому скріні є результатом попереднього читання. | [nRF Connect](evidence/ble/led_off_nrf.jpg), [UART-лог](evidence/ble/led_off_uart.png), [фото плати](evidence/ble/led_off_board.jpg) | PASS для `0x00` |
| Пункт 7 — LED read після write `0x00` | Після вимкнення LED повторно виконати Read LED-характеристики. | FR-G5: прочитаний стан відповідає `0x00` (LED вимкнений). | Після нового Read застосунок показує `Last Read: LED Disabled` і `Last Write: LED Disabled`. Це декодований стан; сирий байт у скріні не відображений. | [Скріншот читання LED](evidence/ble/led_read_off_nrf.jpg) | PASS для стану; сирий байт не показано |
| Пункт 8 — конфлікт каналів керування LED | Записати `0x01` у LED-характеристику через BLE, виконати `led off` через UART, потім знову прочитати LED через BLE. | FR-G5: Read повертає актуальний стан `0x00` після вимкнення LED через інший канал. | UART: BLE write `01` → `LED ON!`, після команди `led off` → `LED OFF!`. Новий Read у nRF Connect показав `Last Read: LED Disabled` при `Last Write: LED Enabled`; фізичний RGB LED на платі згас. Застосунок показує декодований стан, сирий байт у скріні не відображений. | [UART-лог](evidence/ble/led_dual_channel_uart.png), [nRF Connect](evidence/ble/led_dual_channel_nrf.jpg), [фото плати](evidence/ble/led_dual_channel_board.jpg) | PASS для актуального стану; сирий байт не показано |

Решту ручних перевірок додамо після їх виконання.

### B2 — BLE smoke test

Команда: `python -m pytest tests/ble/test_ble_smoke.py -v` у `.venv` (2026-10-21, прошивка `Bluedroid_GATT_Server`). Bluetooth на Mac увімкнено. Порт UART тест знайшов автоматично за VID через фікстуру `device`.

Тест знайшов `SENTRY-BLE`, підключився, записав `0x01` і `0x00` у LED-характеристику та після кожного запису підтвердив через UART відповідно `LED ON!` і `LED OFF!`. BLE-з'єднання закрито фікстурою після тесту.

```text
tests/ble/test_ble_smoke.py::test_ble_led_dual_channel PASSED            [100%]
============================== 1 passed in 12.05s ===============================
```

Доказ: [скріншот прогону `pytest -v`](evidence/ble/pytest_ble_smoke_pass.png), на якому видно команду, `PASSED` і підсумок `1 passed in 12.05s`.

Результат: **PASS**. Перші два прогони після ручного від'єднання телефона пройшли. Після доповнення фікстури виконано ще один прогін, коли nRF Connect на телефоні показував `Connected`: якщо перший пошук не бачить `SENTRY-BLE`, фікстура надсилає UART-команду `disconnect` і повторює сканування. Тест пройшов без ручного від'єднання телефона (`1 passed in 6.37s`). Окремий прогін користувача наведено на скріншоті вище.
