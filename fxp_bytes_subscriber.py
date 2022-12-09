import ipaddress
from array import array
from datetime import datetime, timedelta


def serialize_address(ip_str, port) -> bytes:
    ip = ipaddress.IPv4Address(ip_str).packed
    # ip = int(ip_addr).to_bytes(4, "big")   # extracting ip address as int
    port_bytes = port.to_bytes(2, "big")
    return ip + port_bytes


def deserialize_utcdatetime(data: bytes) -> datetime:
    epoch = datetime(1970, 1, 1)
    temp_arr = array('Q')
    temp_arr.frombytes(data)
    temp_arr.byteswap()
    micros = int(temp_arr[0])
    detime = epoch + timedelta(microseconds=micros)
    return detime


def deserialize_price(data: bytes) -> float:
    temp_arr = array('d')
    temp_arr.frombytes(data)
    return temp_arr[0]


def unmarshal_message(data: bytes):
    """
    Bytes[0:8] == date time
    Bytes[8:14] == currency names
    Bytes[14:22] == exchange rate
    Bytes[22:32] == Reserved.
    """
    data_size = len(data)
    msg = []
    for i in range(0, data_size, 32):   # 32 is the size of msg
        each_packet = data[i:i+32]
        dt = deserialize_utcdatetime(each_packet[0:8])
        from_currency = each_packet[8:11].decode('utf-8')
        to_currency = each_packet[11:14].decode('utf-8')
        price = deserialize_price(each_packet[14:22])
        msg.append({'time': dt, 'from': from_currency, 'to': to_currency, 'price': price})
    return msg
