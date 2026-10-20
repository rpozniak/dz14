from __future__ import annotations

import codecs
import re
import time
from typing import Pattern

import serial
from serial.tools import list_ports


class DeviceError(Exception):
    """Base error for device communication."""


class DeviceTimeout(DeviceError):
    """The expected UART response did not arrive in time."""


class ProtocolError(DeviceError):
    """The firmware response did not match its documented format."""


class DeviceDriver:
    def __init__(self, vid: int = 0x1A86, baudrate: int = 115200):
        self.vid = vid
        self.baudrate = baudrate
        self.connection: serial.Serial | None = None
        self.last_response = ""
        self._text = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def find_port(self) -> str:
        """Select exactly one USB serial port by vendor ID."""
        ports = [p.device for p in list_ports.comports() if p.vid == self.vid]
        if len(ports) != 1:
            raise DeviceError(
                f"Expected one UART port with VID {self.vid:04X}, found {ports}"
            )
        return ports[0]

    def open(self) -> None:
        if self.connection is not None and self.connection.is_open:
            return
        self.connection = serial.Serial(
            self.find_port(),
            self.baudrate,
            timeout=0.1,
            write_timeout=2,
        )
        self.clear_input()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _serial(self) -> serial.Serial:
        if self.connection is None or not self.connection.is_open:
            raise DeviceError("UART port is not open")
        return self.connection

    def clear_input(self) -> None:
        """Discard old output before a new action is triggered."""
        self._serial().reset_input_buffer()
        self._text = ""
        self._decoder.reset()

    def send_line(self, value: str) -> None:
        """Send one CLI input, including an empty Enter."""
        wire = (value.rstrip("\r\n") + "\n").encode("utf-8")
        port = self._serial()
        written = port.write(wire)
        port.flush()
        if written != len(wire):
            raise DeviceError(f"Only {written}/{len(wire)} UART bytes were sent")

    def wait_for_any(
        self,
        patterns: tuple[str | Pattern[str], ...],
        timeout: float = 5.0,
    ) -> tuple[int, str]:
        """Wait for text anywhere in the UART stream, even without a newline."""
        if timeout <= 0 or not patterns:
            raise ValueError("timeout and patterns must be positive/nonempty")
        regexes = [
            re.compile(p, re.IGNORECASE) if isinstance(p, str) else p
            for p in patterns
        ]
        deadline = time.monotonic() + timeout
        observed = ""
        while True:
            matches = [
                (match.start(), index, match)
                for index, regex in enumerate(regexes)
                if (match := regex.search(self._text)) is not None
            ]
            if matches:
                _, index, match = min(matches, key=lambda item: item[0])
                observed += self._text[: match.end()]
                self._text = self._text[match.end() :]
                return index, observed
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.last_response = observed + self._text
                raise DeviceTimeout(
                    f"Timed out waiting for {patterns!r}; received {self.last_response!r}"
                )
            chunk = self._serial().read(self._serial().in_waiting or 1)
            if chunk:
                self._text += self._decoder.decode(chunk)

    def wait_for_pattern(self, pattern: str, timeout: float = 5.0) -> str:
        return self.wait_for_any((pattern,), timeout=timeout)[1]

    def _command(self, command: str) -> None:
        self.clear_input()
        self.send_line(command)

    def wifi_scan(self, timeout: float = 15.0) -> list[str]:
        """Return SSIDs from the firmware's scan list."""
        self._command("scan")
        header = self.wait_for_pattern(r"found\s+\d+\s+networks:", timeout)
        count_match = re.search(r"found\s+(\d+)\s+networks:", header, re.I)
        if count_match is None:
            raise ProtocolError(f"No network count in {header!r}")
        count = int(count_match.group(1))
        networks = []
        row_pattern = r"\[\s*\d+\]\s+SSID:\s*(.*?)\s+RSSI:\s*-?\d+\s*dBm"
        for _ in range(count):
            row = self.wait_for_pattern(row_pattern, timeout)
            match = re.search(row_pattern, row, re.I)
            if match is None:
                raise ProtocolError(f"Invalid scan row: {row!r}")
            networks.append(match.group(1).strip())
        self.last_response = header + "\n" + "\n".join(networks)
        return networks

    def wifi_connect(
        self, ssid: str, password: str, timeout: float = 20.0
    ) -> bool:
        """Follow the firmware's interactive connect dialogue."""
        self._command("connect")
        transcript = ""
        try:
            _, part = self.wait_for_any(
                (r"Enter SSID[^\r\n]*:\s*",), timeout=timeout
            )
            transcript += part

            # The firmware permits a number from its freshly scanned list.
            # This avoids terminal encoding problems with non-ASCII SSIDs.
            selection = ssid
            if ssid:
                rows = re.findall(
                    r"\[\s*(\d+)\]\s+SSID:\s*(.*?)\s+RSSI:",
                    part,
                    re.I,
                )
                selection = next(
                    (number for number, name in rows if name.strip() == ssid),
                    ssid,
                )
            self.send_line(selection)

            outcome = (
                r"Enter password:\s*",
                r"successfully connected to SSID:",
                r"failed to connect to SSID:",
                r"password too short",
                r"connect to the AP fail",
                r"connection timeout",
            )
            index, part = self.wait_for_any(outcome, timeout=timeout)
            transcript += part
            if index == 0:
                self.send_line(password)
                index, part = self.wait_for_any(outcome[1:], timeout=timeout)
                transcript += part
                success = index == 0
            else:
                success = index == 1
        except DeviceTimeout:
            self.last_response = transcript + self.last_response
            return False
        self.last_response = transcript
        return success

    def wifi_status(self, timeout: float = 5.0) -> dict[str, bool | str | int | None]:
        """Read state, SSID, IP and RSSI from the CLI status response."""
        self._command("status")
        index, text = self.wait_for_any(
            (r"WiFi:\s*connected", r"WiFi:\s*disconnected"), timeout
        )
        if index == 1:
            self.last_response = text
            return {"connected": False, "ssid": None, "ip": None, "rssi": None}
        text += self.wait_for_pattern(r"RSSI:\s*-?\d+\s*dBm", timeout)
        ssid = re.search(r"\bSSID:[ \t]*([^\r\n]*)", text)
        ip = re.search(r"\bIP:[ \t]*(\d+\.\d+\.\d+\.\d+)", text)
        rssi = re.search(r"\bRSSI:[ \t]*(-?\d+)[ \t]*dBm", text)
        if ssid is None or ip is None or rssi is None:
            raise ProtocolError(f"Incomplete Wi-Fi status: {text!r}")
        self.last_response = text
        return {
            "connected": True,
            "ssid": ssid.group(1).strip(),
            "ip": ip.group(1),
            "rssi": int(rssi.group(1)),
        }

    def wifi_disconnect(self, timeout: float = 5.0) -> str:
        self._command("disconnect")
        self.last_response = self.wait_for_pattern(
            r"wifi station:\s*disconnected", timeout
        )
        return self.last_response

    def reboot(self, timeout: float = 15.0) -> str:
        self._command("reboot")
        self.last_response = self.wait_for_pattern(
            r"station_WiFi fw .* ready", timeout
        )
        return self.last_response

    def help(self, timeout: float = 5.0) -> str:
        self._command("help")
        self.last_response = self.wait_for_pattern(
            r"Available commands:", timeout
        )
        return self.last_response
