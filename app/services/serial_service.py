"""Serial communication with ESP32-SERVO — sends servo commands."""

import logging
import serial
import serial.tools.list_ports
from typing import Optional

logger = logging.getLogger(__name__)

SERIAL_BAUDRATE = 115200


def find_esp32_port() -> Optional[str]:
    """Tìm cổng COM có ESP32-SERVO."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description or ""
        if "USB" in desc or "CH340" in desc or "Silicon" in desc or "COM" in port.device:
            logger.info(f"ESP32-SERVO found on {port.device}: {desc}")
            return port.device
    if ports:
        logger.warning(f"No ESP32 found, using first port: {ports[0].device}")
        return ports[0].device
    return None


class ESP32ServoSerial:
    def __init__(self, port: Optional[str] = None):
        self.port = port or find_esp32_port()
        self.serial: Optional[serial.Serial] = None

    def connect(self) -> bool:
        if self.port is None:
            logger.error("No serial port found")
            return False
        try:
            self.serial = serial.Serial(self.port, baudrate=SERIAL_BAUDRATE, timeout=1.0)
            logger.info(f"Serial connected on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Serial connect error: {e}")
            return False

    def disconnect(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("Serial disconnected")

    def send(self, cmd: str) -> bool:
        if not self.serial or not self.serial.is_open:
            return False
        try:
            self.serial.write(f"{cmd}\n".encode("utf-8"))
            self.serial.flush()
            logger.info(f"SERIAL TX: {cmd}")
            return True
        except Exception as e:
            logger.error(f"Serial send error: {e}")
            return False

    def send_classify(self, output_code: int) -> bool:
        """Gửi lệnh phân loại: C1-C5."""
        if 1 <= output_code <= 5:
            return self.send(f"C{output_code}")
        return False

    def send_push(self) -> bool:
        """Gửi lệnh đẩy rác: P."""
        return self.send("P")


_esp32_servo_serial: Optional[ESP32ServoSerial] = None


def get_esp32_servo_serial() -> Optional[ESP32ServoSerial]:
    return _esp32_servo_serial


def init_serial(port: Optional[str] = None) -> bool:
    global _esp32_servo_serial
    _esp32_servo_serial = ESP32ServoSerial(port)
    return _esp32_servo_serial.connect()


def close_serial() -> None:
    global _esp32_servo_serial
    if _esp32_servo_serial:
        _esp32_servo_serial.disconnect()
        _esp32_servo_serial = None
