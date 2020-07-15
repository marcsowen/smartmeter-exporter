#!/usr/bin/python3 -u

import serial
import re
from prometheus_client import start_http_server, Gauge, Info

WAKE_UP_SEQUENCE = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
SIGN_ON_SEQUENCE = b'\x2F\x3F\x21\x0D\x0A'

serial_number = None
version_number = None

power_meter_info = Info('power_meter', "Serial and version of power meter")
power_consumption = Gauge('power_consumption', 'Power consumption in kWh')
power_failures = Gauge('power_failures', 'Number of power failures', labelnames=['line'])

heat_energy_consumption = Gauge('heat_energy_consumption', 'Heat energy consumption in MWh')
heat_flow = Gauge('heat_flow', 'Heat flow in m^3')
power_on_hours = Gauge('power_on_hours', 'Power on hours')
heat_flow_hours = Gauge('heat_flow_hours', 'Hours with heat flow')


def process_line(line):
    global serial_number, version_number
    matches = re.finditer(r'(\w{1,3}(?:\.\w{1,3}){0,2}(?:\*\d{1,2})?)\(([a-zA-Z0-9:>.,\s*&-]*)\)', line.decode("ascii"))
    for match in matches:
        obis_code = match.group(1)
        content = match.group(2)
        if obis_code == "0.0.0":
            serial_number = content
        elif obis_code == "0.2.1":
            version_number = content
        elif obis_code == "1.8.0":
            kwh = re.search(r'\d*\.\d*', content).group()
            power_consumption.set(kwh)
        elif obis_code == "C.7.1":
            power_failures.labels(line='L1').set(content)
        elif obis_code == "C.7.2":
            power_failures.labels(line='L2').set(content)
        elif obis_code == "C.7.3":
            power_failures.labels(line='L3').set(content)
        elif obis_code == "6.8":
            mwh = re.search(r'\d*\.\d*', content).group()
            heat_energy_consumption.set(mwh)
        elif obis_code == "6.26":
            m3 = re.search(r'\d*\.\d*', content).group()
            heat_flow.set(m3)
        elif obis_code == "6.31":
            hours = re.search(r'\d*', content).group()
            power_on_hours.set(hours)
        elif obis_code == "9.31":
            hours = re.search(r'\d*', content).group()
            heat_flow_hours.set(hours)
        if serial_number and version_number:
            power_meter_info.info({'serial': serial_number, 'version': version_number})


def get_baudrate(baudrate_id):
    if baudrate_id == "A":
        return 600
    elif baudrate_id == "B":
        return 1200
    elif baudrate_id == "C":
        return 2400
    elif baudrate_id == "D":
        return 4800
    elif baudrate_id == "E":
        return 9600
    elif baudrate_id == "F":
        return 19200
    else:
        return 300


def process_id(serial_device, id_byte):
    id_str = id_byte.decode("ascii")
    baudrate = get_baudrate(id_str[3])

    print("Manufacturer: " + id_str[0:3])
    print("Device      : " + id_str[4:-2])
    print("Baudrate    : " + str(baudrate))

    serial_device.baudrate = baudrate


def login(serial_device):
    serial_device.baudrate = 300
    serial_device.write(WAKE_UP_SEQUENCE)
    serial_device.write(SIGN_ON_SEQUENCE)
    serial_device.flush()
    serial_device.read_until(b'\x2F')

    identification = serial_device.readline()
    process_id(ser, identification)


if __name__ == '__main__':
    print("SmartMeter Exporter v0.1\n")
    start_http_server(3224)
    ser = serial.Serial(port='/dev/ttyUSB0',
                        baudrate=300,
                        bytesize=serial.SEVENBITS,
                        parity=serial.PARITY_EVEN,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=10)

    login(ser)
    while True:
        result = ser.readline()
        if len(result) == 0:
            # Apparently we reached the end of transmission.
            login(ser)
            result = ser.readline()
        process_line(result)
