#!/usr/bin/python3 -u

import serial
import re
from prometheus_client import start_http_server, Gauge, Info

SIGN_ON_SEQUENCE = b'\x2F\x3F\x21\x0D\x0A'

serial_number = None
version_number = None

power_meter_info = Info('power_meter', "Serial and version of power meter")
power_consumption = Gauge('power_consumption', 'Power consumption in kWh')
power_failures = Gauge('power_failures', 'Number of power failures', labelnames=['line'])


def process_line(line):
    global serial_number, version_number
    obiscode_match = re.search(r'\w\.\w\.\w', line.decode("ascii"))
    content_match = re.search(r'\((.*)\)', line.decode("ascii"))
    if obiscode_match and content_match:
        obiscode = obiscode_match.group()
        content = content_match.group(1)
        if obiscode == "0.0.0":
            serial_number = content
        elif obiscode == "0.2.1":
            version_number = content
        elif obiscode == "1.8.0":
            kwh = re.search(r'\d*\.\d*', content).group()
            power_consumption.set(kwh)
        elif obiscode == "C.7.1":
            power_failures.labels(line='L1').set(content)
        elif obiscode == "C.7.2":
            power_failures.labels(line='L2').set(content)
        elif obiscode == "C.7.3":
            power_failures.labels(line='L3').set(content)
        if serial_number and version_number:
            power_meter_info.info({'serial': serial_number, 'version': version_number})


if __name__ == '__main__':
    start_http_server(3223)
    ser = serial.Serial(port='/dev/ttyUSB0',
                        baudrate=300,
                        bytesize=serial.SEVENBITS,
                        parity=serial.PARITY_EVEN,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=10)
    ser.write(SIGN_ON_SEQUENCE)
    while True:
        result = ser.readline()
        if len(result) == 0:
            # Apparently we reached the end of transmission.
            ser.write(SIGN_ON_SEQUENCE)
            result = ser.readline()
        process_line(result)
