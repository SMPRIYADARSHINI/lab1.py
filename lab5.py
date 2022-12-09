"""
Bitcoin blockchain explorer: establishes a connection to a Bitcoin node using
version and version acknowledgement messages. Then retrieves a desired block
number using the getblocks message, and prints the transactions found inside
the block. There is also an experiment at the end where we change the reward
value of a transaction and print out the new merkle root and block hashes,
which would cause the block to get rejected by the rest of the Bitcoin network.

Author:PRIYADARSHINI SHANMUGASUNDARAM MURUGAN
Date: 12/01/2022
"""

import random
import time
import socket
import sys

from time import strftime, gmtime
from hashlib import sha256


''' 
IPs used :
'''
BTC_IP = '188.40.164.205'
BTC_PORT = 8333  # Mainnet
BTC_PEER_ADDRESS = (BTC_IP, BTC_PORT)
BTC_SOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket
MAX_BLOCKS = 500  # Blocks from inv message
BLOCK_GENESIS = bytes.fromhex('000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f')
MY_IP = '127.0.0.1'
START_STRING = bytes.fromhex('f9beb4d9')  # Magic bytes
EMPTY_STRING = ''.encode()  # Empty payload
HEADER_SIZE = 24  # For all Bitcoin message headers
COMMAND_SIZE = 12  # Message command length
VERSION = 70015
BLOCK_NUMBER = 6554  # Pick any block number
BUFFER_SIZE = 64000  # sock recv argument
PREFIX = '  '


def compactsize_t(n):
    """
    Marshals compactsize data type.

    """
    if n < 252:
        return uint8_t(n)
    if n < 0xffff:
        return uint8_t(0xfd) + uint16_t(n)
    if n < 0xffffffff:
        return uint8_t(0xfe) + uint32_t(n)
    return uint8_t(0xff) + uint64_t(n)


def unmarshal_compactsize(b):
    """
    Unmarshals compactsize data type.

    """
    key = b[0]
    if key == 0xff:
        return b[0:9], unmarshal_uint(b[1:9])
    if key == 0xfe:
        return b[0:5], unmarshal_uint(b[1:5])
    if key == 0xfd:
        return b[0:3], unmarshal_uint(b[1:3])
    return b[0:1], unmarshal_uint(b[0:1])


def bool_t(flag):
    """Marshal bool to unsigned, 8 bit"""
    return uint8_t(1 if flag else 0)


def ipv6_from_ipv4(ipv4_str):
    """Marshal ipv4 string to ipv6"""
    pchIPv4 = bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff])
    return pchIPv4 + bytearray((int(x) for x in ipv4_str.split('.')))


def ipv6_to_ipv4(ipv6):
    """Unmarshal ipv6 bytes to ipv4 string"""
    return '.'.join([str(b) for b in ipv6[12:]])


def uint8_t(n):
    """Marshal integer to unsigned, 8 bit"""
    return int(n).to_bytes(1, byteorder='little', signed=False)


def uint16_t(n):
    """Marshal integer to unsigned, 16 bit"""
    return int(n).to_bytes(2, byteorder='little', signed=False)


def int32_t(n):
    """Marshal integer to signed, 32 bit"""
    return int(n).to_bytes(4, byteorder='little', signed=True)


def uint32_t(n):
    """Marshal integer to unsigned, 32 bit"""
    return int(n).to_bytes(4, byteorder='little', signed=False)


def int64_t(n):
    """Marshal integer to signed, 64 bit"""
    return int(n).to_bytes(8, byteorder='little', signed=True)


def uint64_t(n):
    """Marshal integer to unsigned, 64 bit"""
    return int(n).to_bytes(8, byteorder='little', signed=False)


def unmarshal_int(b):
    """Unmarshal signed integer"""
    return int.from_bytes(b, byteorder='little', signed=True)


def unmarshal_uint(b):
    """Unmarshal unsigned integer"""
    return int.from_bytes(b, byteorder='little', signed=False)


def swap_endian(b: bytes):
    """
    Swap the endianness of the given bytes. If little, swaps to big. If big,
    swaps to little.

    """
    swapped = bytearray.fromhex(b.hex())
    swapped.reverse()
    return swapped
def build_message(command, payload):
    """
    Returns the complete message bytes (header + payload).

    """
    return message_header(command, payload) + payload


def version_message():
    """
    Builds the version message payload, per the Bitcoin protocol.

    """
    version = int32_t(VERSION)  # Version 70015
    services = uint64_t(0)  # Unnamed - not full node
    timestamp = int64_t(int(time.time()))  # Current UNIX epoch
    addr_recv_services = uint64_t(1)  # Full node
    addr_recv_ip_address = ipv6_from_ipv4(BTC_IP)  # Big endian
    addr_recv_port = uint16_t(BTC_PORT)
    addr_trans_services = uint64_t(0)  # Identical to services
    addr_trans_ip_address = ipv6_from_ipv4(MY_IP)  # Big endian
    addr_trans_port = uint16_t(BTC_PORT)
    nonce =uint64_t(0)
    user_agent_bytes = compactsize_t(0)  # 0 so no user agent field
    start_height = int32_t(0)
    relay = bool_t(False)
    return b''.join([version, services, timestamp,
                     addr_recv_services, addr_recv_ip_address, addr_recv_port,
                     addr_trans_services, addr_trans_ip_address, addr_trans_port,
                     nonce, user_agent_bytes, start_height, relay])


def getdata_message(tx_type, header_hash):
    """
    Builds the getdata payload, per the Bitcoin protocol.

    """
    # Identical to inv
    count = compactsize_t(1)
    entry_type =uint32_t(tx_type)
    entry_hash = bytes.fromhex(header_hash.hex())
    return count + entry_type + entry_hash


def getblocks_message(header_hash):
    """
    Builds the getblocks payload, per the Bitcoin protocol.

    """
    version = uint32_t(VERSION)
    hash_count = compactsize_t(1)
    # Assuming we pass in an already computed sha256(sha256(block)) hash
    block_header_hashes = bytes.fromhex(header_hash.hex())
    # Always ask for max number of blocks
    stop_hash = b'\0' * 32
    return b''.join([version, hash_count, block_header_hashes, stop_hash])


def ping_message():
    """
    Build the ping payload, per the Bitcoin protocol.

    """
    return uint64_t(random.getrandbits(64))


def message_header(command, payload):
    """
    Builds a Bitcoin message header.

    """
    magic = START_STRING
    command_name = command.encode('ascii')
    while len(command_name) < COMMAND_SIZE:
        command_name += b'\0'
    payload_size = uint32_t(len(payload))
    check_sum = checksum(payload)
    return b''.join([magic, command_name, payload_size, check_sum])


def checksum(payload: bytes):
    """
    Calculate Bitcoin protocol checksum - first 4 bytes of
    sha256(sha256(payload)).

    """
    return hash(payload)[:4]


def hash(payload: bytes):
    """
    Calculate the Bitcoin protocol hash - nested sha256 hash.

    """
    return sha256(sha256(payload).digest()).digest()


def sat_to_btc(sat):
    """Converts sat to BTC"""
    return sat * 0.00000001


def btc_to_sat(btc):
    """Converts BTC to sat"""
    return btc * 10e7


def print_message(msg, text=None, height=None):
    """
    Report the contents of the given bitcoin message

    """
    print('\n{}MESSAGE'.format('' if text is None else (text + ' ')))
    print('({}) {}'.format(len(msg), msg[:60].hex() + ('' if len(msg) < 60 else '...')))
    payload = msg[HEADER_SIZE:]
    command = print_header(msg[:HEADER_SIZE], checksum(payload))
    if payload:
        header_hash =swap_endian(hash(payload[:80])).hex() if command == 'block' else ''
        print('{}{} {}'.format(PREFIX, command.upper(), header_hash))
        print(PREFIX + '-' * 56)

    if command == 'version':
        print_version_msg(payload)
    elif command == 'sendcmpct':
        print_sendcmpct_message(payload)
    elif command == 'ping' or command == 'pong':
        print_ping_pong_message(payload)
    elif command == 'addr':
        print_addr_message(payload)
    elif command == 'feefilter':
        print_feefilter_message(payload)
    elif command == 'getblocks':
        print_getblocks_message(payload)
    elif command == 'inv' or command == 'getdata' or command == 'notfound':
        print_inv_message(payload, height)
    elif command == 'block':
        print_block_message(payload)
    return command


def print_inv_message(payload, height):
    """
    Prints the contents of the inv message.

    """
    count_bytes, count =unmarshal_compactsize(payload)
    i = len(count_bytes)
    inventory = []
    for _ in range(count):
        inv_entry = payload[i: i + 4], payload[i + 4:i + 36]
        inventory.append(inv_entry)
        i += 36

    prefix = PREFIX * 2
    print('{}{:32} count: {}'.format(prefix, count_bytes.hex(), count))
    for i, (tx_type, tx_hash) in enumerate(inventory, start=height if height else 1):
        print('\n{}{:32} type: {}\n{}-'
              .format(prefix, tx_type.hex(),unmarshal_uint(tx_type), prefix))
        block_hash = swap_endian(tx_hash).hex()
        print('{}{:32}\n{}{:32} block #{} hash'.format(prefix, block_hash[:32], prefix, block_hash[32:], i))


def print_getblocks_message(payload):
    """
    Prints contents of the getblocks message.

    """
    version = payload[:4]
    hash_count_bytes, hash_count =unmarshal_compactsize(payload[4:])
    i = 4 + len(hash_count_bytes)
    block_header_hashes = []
    for _ in range(hash_count):
        block_header_hashes.append(payload[i:i + 32])
        i += 32
    stop_hash = payload[i:]

    prefix = PREFIX * 2
    print('{}{:32} version: {}'.format(prefix, version.hex(),unmarshal_uint(version)))
    print('{}{:32} hash count: {}'.format(prefix, hash_count_bytes.hex(), hash_count))
    for hash in block_header_hashes:
        hash_hex =swap_endian(hash).hex()
        print('\n{}{:32}\n{}{:32} block header hash # {}: {}'
              .format(prefix, hash_hex[:32], prefix, hash_hex[32:], 1,unmarshal_uint(hash)))
    stop_hash_hex = stop_hash.hex()
    print('\n{}{:32}\n{}{:32} stop hash: {}'
          .format(prefix, stop_hash_hex[:32], prefix, stop_hash_hex[32:],unmarshal_uint(stop_hash)))


def print_feefilter_message(feerate):
    """
    Prints contents of the feefilter message.

    """
    prefix = PREFIX * 2
    print('{}{:32} count: {}'.format(prefix, feerate.hex(),unmarshal_uint(feerate)))


def print_addr_message(payload):
    """
    Prints contents of the addr message.

    """
    ip_count_bytes, ip_addr_count = unmarshal_compactsize(payload)
    i = len(ip_count_bytes)
    epoch_time, services, ip_addr, port = \
        payload[i:i + 4], payload[i + 4:i + 12], \
        payload[i + 12:i + 28], payload[i + 28:]
    prefix = PREFIX * 2
    print('{}{:32} count: {}'.format(prefix, ip_count_bytes.hex(), ip_addr_count))
    time_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(unmarshal_int(epoch_time)))
    print('{}{:32} epoch time: {}'.format(prefix, epoch_time.hex(), time_str))
    print('{}{:32} services: {}'.format(prefix, services.hex(),unmarshal_uint(services)))
    print('{}{:32} host: {}'.format(prefix, ip_addr.hex(), ipv6_to_ipv4(ip_addr)))
    print('{}{:32} port: {}'.format(prefix, port.hex(), unmarshal_uint(port)))


def print_ping_pong_message(nonce):
    """
    Print contents of ping/pong message.

    """
    prefix = PREFIX * 2
    print('{}{:32} nonce: {}'.format(prefix, nonce.hex(), unmarshal_uint(nonce)))


def print_sendcmpct_message(payload):
    """
    Prints contents of the sendcmpct message.

    """
    announce, version = payload[:1], payload[1:]
    prefix = PREFIX * 2
    print('{}{:32} announce: {}'.format(prefix, announce.hex(), bytes(announce) != b'\0'))
    print('{}{:32} version: {}'.format(prefix, version.hex(), unmarshal_uint(version)))


def print_version_msg(b):
    """
    Report the contents of the given bitcoin version message (sans the header)

    """
    # pull out fields
    version, my_services, epoch_time, your_services = b[:4], b[4:12], b[12:20], b[20:28]
    rec_host, rec_port, my_services2, my_host, my_port = b[28:44], b[44:46], b[46:54], b[54:70], b[70:72]
    nonce = b[72:80]
    user_agent_size, uasz = unmarshal_compactsize(b[80:])
    i = 80 + len(user_agent_size)
    user_agent = b[i:i + uasz]
    i += uasz
    start_height, relay = b[i:i + 4], b[i + 4:i + 5]
    extra = b[i + 5:]

    # print report
    prefix = PREFIX * 2
    print('{}{:32} version {}'.format(prefix, version.hex(), unmarshal_int(version)))
    print('{}{:32} my services'.format(prefix, my_services.hex()))
    time_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(unmarshal_int(epoch_time)))
    print('{}{:32} epoch time {}'.format(prefix, epoch_time.hex(), time_str))
    print('{}{:32} your services'.format(prefix, your_services.hex()))
    print('{}{:32} your host {}'.format(prefix, rec_host.hex(),ipv6_to_ipv4(rec_host)))
    print('{}{:32} your port {}'.format(prefix, rec_port.hex(), unmarshal_uint(rec_port)))
    print('{}{:32} my services (again)'.format(prefix, my_services2.hex()))
    print('{}{:32} my host {}'.format(prefix, my_host.hex(),ipv6_to_ipv4(my_host)))
    print('{}{:32} my port {}'.format(prefix, my_port.hex(), unmarshal_uint(my_port)))
    print('{}{:32} nonce'.format(prefix, nonce.hex()))
    print('{}{:32} user agent size {}'.format(prefix, user_agent_size.hex(), uasz))
    print('{}{:32} user agent \'{}\''.format(prefix, user_agent.hex(), str(user_agent, encoding='utf-8')))
    print('{}{:32} start height {}'
          .format(prefix, start_height.hex(),unmarshal_uint(start_height)))
    print('{}{:32} relay {}'.format(prefix, relay.hex(), bytes(relay) != b'\0'))
    if len(extra) > 0:
        print('{}{:32} EXTRA!!'.format(prefix, extra.hex()))


def print_header(header, expected_cksum=None):
    """
    Report the contents of the given bitcoin message header

    """
    magic, command_hex, payload_size, cksum = header[:4], header[4:16], header[16:20], header[20:]
    command = str(bytearray([b for b in command_hex if b != 0]), encoding='utf-8')
    psz = unmarshal_uint(payload_size)
    if expected_cksum is None:
        verified = ''
    elif expected_cksum == cksum:
        verified = '(verified)'
    else:
        verified = '(WRONG!! ' + expected_cksum.hex() + ')'
    prefix = '  '
    print(prefix + 'HEADER')
    print(prefix + '-' * 56)
    prefix *= 2
    print('{}{:32} magic'.format(prefix, magic.hex()))
    print('{}{:32} command: {}'.format(prefix, command_hex.hex(), command))
    print('{}{:32} payload size: {}'.format(prefix, payload_size.hex(), psz))
    print('{}{:32} checksum {}'.format(prefix, cksum.hex(), verified))
    return command


def print_block_message(payload):
    """
    Prints the contents of the block message.

    """
    # Block header (80 bytes)
    version, prev_block, merkle_root, epoch_time, bits, nonce = \
        payload[:4], payload[4:36], payload[36:68], payload[68:72], payload[72:76], payload[76:80]

    txn_count_bytes, txn_count =unmarshal_compactsize(payload[80:])
    txns = payload[80 + len(txn_count_bytes):]

    prefix = PREFIX * 2
    print('{}{:32} version: {}\n{}-'
          .format(prefix, version.hex(),unmarshal_int(version), prefix))
    prev_hash =swap_endian(prev_block)
    print('{}{:32}\n{}{:32} prev block hash\n{}-'
          .format(prefix, prev_hash.hex()[:32], prefix, prev_hash.hex()[32:], prefix))
    merkle_hash =swap_endian(merkle_root)
    print('{}{:32}\n{}{:32} merkle root hash\n{}-'
          .format(prefix, merkle_hash.hex()[:32], prefix, merkle_hash.hex()[32:], prefix))
    time_str = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime(unmarshal_int(epoch_time)))
    print('{}{:32} epoch time: {}'.format(prefix, epoch_time.hex(), time_str))
    print('{}{:32} bits: {}'.format(prefix, bits.hex(),unmarshal_uint(bits)))
    print('{}{:32} nonce: {}'.format(prefix, nonce.hex(),unmarshal_uint(nonce)))
    print('{}{:32} transaction count: {}'.format(prefix, txn_count_bytes.hex(), txn_count))
    print_transaction(txns)


def print_transaction(txn_bytes):
    """
    Prints the contents of the transactions portion of a block.

    """
    # Parse version and transaction input count bytes
    version = txn_bytes[:4]
    tx_in_count_bytes, tx_in_count =unmarshal_compactsize(txn_bytes[4:])
    i = 4 + len(tx_in_count_bytes)

    # Parse coinbase bytes
    cb_txn, cb_script_bytes_count = parse_coinbase(txn_bytes[i:], version)
    tx_in_list = [(cb_txn, cb_script_bytes_count)]
    i += len(b''.join(cb_txn))

    # Parse transaction input bytes
    for _ in range(1, tx_in_count):
        tx_in, script_bytes_count = parse_tx_in(txn_bytes[i:])
        tx_in_list.append((tx_in, script_bytes_count))
        i += len(b''.join(tx_in))

    # Parse transaction output count bytes
    tx_out_count_bytes, tx_out_count = unmarshal_compactsize(txn_bytes[i:])
    tx_out_list = []
    i += len(tx_out_count_bytes)

    # Parse transaction output bytes
    for _ in range(tx_out_count):
        tx_out, pk_script_bytes_count = parse_tx_out(txn_bytes[i:])
        tx_out_list.append((tx_out, pk_script_bytes_count))
        i += len(b''.join(tx_out))

    lock_time = txn_bytes[i:i+4]

    prefix = PREFIX * 2
    print('{}{:32} version: {}'.format(prefix, version.hex(), unmarshal_uint(version)))

    print('\n{}Transaction Inputs:'.format(prefix))
    print(prefix + '-' * 32)
    print('{}{:32} input txn count: {}'.format(prefix, tx_in_count_bytes.hex(), tx_in_count))
    print_transaction_inputs(tx_in_list)

    print('\n{}Transaction Outputs:'.format(prefix))
    print(prefix + '-' * 32)
    print('{}{:32} output txn count: {}'.format(prefix, tx_out_count_bytes.hex(), tx_out_count))
    print_transaction_outputs(tx_out_list)

    print('{}{:32} lock time: {}'.format(prefix, lock_time.hex(), unmarshal_uint(lock_time)))
    if txn_bytes[i + 4:]:
        print('EXTRA: {}'.format(txn_bytes[i + 4:].hex()))


def print_transaction_inputs(tx_in_list):
    """
    Prints the transaction inputs from the transactions portion of the block.

    """
    prefix = PREFIX * 2
    for i, tx_in in enumerate(tx_in_list, start=1):
        print('\n{}Transaction {}{}:'.format(prefix, i, ' (Coinbase)' if i == 1 else ''))
        print(prefix + '*' * 32)
        hash, index, script_bytes, sig_script, seq = tx_in[0]
        script_bytes_count = tx_in[1]
        print('{}{:32}\n{}{:32} hash\n{}-'.format(prefix, hash.hex()[:32], prefix, hash.hex()[32:], prefix))
        print('{}{:32} index: {}'.format(prefix, index.hex(),unmarshal_uint(index)))
        print('{}{:32} script bytes: {}'.format(prefix, script_bytes.hex(), script_bytes_count))
        print('{}{:32} {}script'.format(prefix, sig_script.hex(), 'coinbase ' if i == 1 else ''))
        print('{}{:32} sequence number'.format(prefix, seq.hex()))


def print_transaction_outputs(tx_out_list):
    """
    Prints the transaction outputs from the transactions portion of the block.

    """
    prefix = PREFIX * 2
    for i, tx_out in enumerate(tx_out_list, start=1):
        print('\n{}Transaction {}:'.format(prefix, i))
        print(prefix + '*' * 32)
        value, pk_script_bytes, pk_script = tx_out[0]
        pk_script_bytes_count = tx_out[1]
        sat= unmarshal_uint(value)
        btc = sat_to_btc(sat)
        print('{}{:32} value: {} sat = {} BTC'.format(prefix, value.hex(), sat, btc))
        print('{}{:32} public key script length: {}\n{}-'
              .format(prefix, pk_script_bytes.hex(), pk_script_bytes_count, prefix))
        for j in range(0, pk_script_bytes_count * 2, 32):
            print('{}{:32}{}' .format(prefix, pk_script.hex()[j:j + 32],
                                      ' public key script\n{}-'.format(prefix)
                                      if j + 32 > pk_script_bytes_count * 2 else ''))


def parse_coinbase(cb_bytes, version):
    """
    Parses the bytes of a coinbase transaction.

    """
    hash_null = cb_bytes[:32]
    index = cb_bytes[32:36]
    script_bytes, script_bytes_count =unmarshal_compactsize(cb_bytes[36:])
    i = 36 + len(script_bytes)

    height = None
    # Version 1 doesn't require height parameter prior to block 227,836
    if unmarshal_uint(version) > 1:
        height = cb_bytes[i:i + 4]
        i += 4

    cb_script = cb_bytes[i:i + script_bytes_count]
    sequence = cb_bytes[i + script_bytes_count: i + script_bytes_count + 4]

    if height:
        return [hash_null, index, script_bytes, height, cb_script, sequence], script_bytes_count
    else:
        return [hash_null, index, script_bytes, cb_script, sequence], script_bytes_count


def parse_tx_out(tx_out_bytes):
    """
    Parses the transaction output bytes of a transaction.

    """
    value = tx_out_bytes[:8]
    pk_script_bytes, pk_script_bytes_count = unmarshal_compactsize(tx_out_bytes[8:])
    i = 8 + len(pk_script_bytes)
    pk_script = tx_out_bytes[i:i + pk_script_bytes_count]
    return [value, pk_script_bytes, pk_script], pk_script_bytes_count


def parse_tx_in(tx_in_bytes):
    """
    Parses the transaction input bytes of a transaction.

    """
    hash = tx_in_bytes[:32]
    index = tx_in_bytes[32:36]
    script_bytes, script_bytes_count =unmarshal_compactsize(tx_in_bytes[36:])
    i = 36 + len(script_bytes)
    sig_script = tx_in_bytes[i:i + script_bytes_count]
    sequence = tx_in_bytes[i + script_bytes_count:]
    return [hash, index, script_bytes, sig_script, sequence], script_bytes_count


def split_message(peer_msg_bytes):
    """
    Splits the bytes into a list of each individual message.

    """
    msg_list = []
    while peer_msg_bytes:
        payload_size = unmarshal_uint(peer_msg_bytes[16:20])
        msg_size = HEADER_SIZE + payload_size
        msg_list.append(peer_msg_bytes[:msg_size])
        # Discard to move onto next message
        peer_msg_bytes = peer_msg_bytes[msg_size:]
    return msg_list


def get_last_block_hash(inv_bytes):
    """
    Get the last block hash from an inv message.

    """
    return inv_bytes[len(inv_bytes) - 32:]


def update_current_height(block_list, curr_height):
    """
    Update the current height of our local block chain.

    """
    return curr_height + (len(block_list[-1]) - 27) // 36


def exchange_messages(bytes_to_send, expected_bytes=None, height=None, wait=False):
    """
    Exchanges messages with the Bitcoin node and prints the messages that
    are being sent and received.

    """
    print_message(bytes_to_send, 'send', height=height)
    BTC_SOCK.settimeout(0.5)
    bytes_received = b''

    try:
        BTC_SOCK.sendall(bytes_to_send)

        if expected_bytes:
            # Message size is fixed: receive until byte sizes match
            while len(bytes_received) < expected_bytes:
                bytes_received += BTC_SOCK.recv(BUFFER_SIZE)
        elif wait:
            # Message size could vary: wait until timeout to receive all bytes
            while True:
                bytes_received += BTC_SOCK.recv(BUFFER_SIZE)

    except Exception as e:
        print('\nNo bytes left to receive from {}: {}'
              .format(BTC_PEER_ADDRESS, str(e)))

    finally:
        print('\n****** Received {} bytes from BTC node {} ******'
              .format(len(bytes_received), BTC_PEER_ADDRESS))
        peer_msg_list = split_message(bytes_received)
        for msg in peer_msg_list:
            print_message(msg, 'receive', height)
        return peer_msg_list


def send_getblocks_message(input_hash, current_height):
    """
    Helper method for sending the getblocks message to the Bitcoin node.

    """
    getblocks_bytes = build_message('getblocks', getblocks_message(input_hash))
    peer_inv = exchange_messages(getblocks_bytes, expected_bytes=18027, height=current_height + 1)
    peer_inv_bytes = b''.join(peer_inv)
    last_500_headers = [peer_inv_bytes[i:i + 32] for i in range(31, len(peer_inv_bytes), 36)]
    current_height = update_current_height(peer_inv, current_height)
    return last_500_headers, current_height


def peer_height_from_version(vsn_bytes):
    """
    Retrieves the height of the peer's blockchain using the start_height bytes
    from their version message.

    """
    return unmarshal_uint(vsn_bytes[-5:-1])


def change_block_value(block, block_number, new_amt):
    """
    Change the satoshi reward value of the block.

    """
    # Jump to the value index in the block
    txn_count_bytes = unmarshal_compactsize(block[104:])[0]
    index = 104 + len(txn_count_bytes)
    version = block[index:index + 4]
    index += 4
    tx_in_count_bytes = unmarshal_compactsize(block[index:])[0]
    index += len(tx_in_count_bytes)
    tx_in = parse_coinbase(block[index:], version)[0]
    index += len(b''.join(tx_in))
    txn_out_count_bytes = unmarshal_compactsize(block[index:])[0]
    index += len(txn_out_count_bytes)

    # Display old value
    old_value_bytes = block[index:index + 8]
    old_value = unmarshal_uint(old_value_bytes)
    print('Block {}: change value from {} BTC to {} BTC'
          .format(block_number, sat_to_btc(old_value), sat_to_btc(new_amt)))
    print('-' * 41)
    print('{:<24}'.format('old value:') + '{} BTC = {} sat'.format(sat_to_btc(old_value), old_value))

    # Verify old merkle hash
    old_merkle = swap_endian(block[60:92])
    calc_old_merkle =swap_endian(hash(block[104 + len(tx_in_count_bytes):]))
    print('{:<24}'.format('old merkle hash:') + old_merkle.hex())
    print('{:<24}'.format('verify old merkle hash:') + 'hash(txn) = {}'.format(calc_old_merkle.hex()))
    old_hash = swap_endian(hash(block[HEADER_SIZE:HEADER_SIZE + 80]))
    print('{:<24}'.format('old block hash:') + old_hash.hex())

    print('*' * 16)

    # Change the value bytes in the block
    block = block.replace(block[index:index + 8], uint64_t(new_amt))
    new_value_bytes = block[index:index + 8]
    new_value =unmarshal_uint(new_value_bytes)
    print('{:<24}'.format('new value:') + '{} BTC = {} sat'.format(sat_to_btc(new_value), new_value))

    # Calculate and display new merkle root
    calc_new_merkle = hash(block[104 + len(tx_in_count_bytes):])
    block = block.replace(block[60:92], calc_new_merkle)
    new_merkle = swap_endian(block[60:92])
    calc_new_merkle =swap_endian(calc_new_merkle)
    print('{:<24}'.format('new merkle:') + new_merkle.hex())
    print('{:<24}'.format('verify new merkle:') + 'hash(txn) = {}'.format(calc_new_merkle.hex()))

    # Calculate and display new block hash
    new_hash =swap_endian(hash(block[HEADER_SIZE:HEADER_SIZE + 80]))
    print('{:<24}'.format('new block hash:') + new_hash.hex())
    print('-' * 32)
    return block


def thief_experiment(my_block, block_number, last_500_blocks, new_value):
    """
    Experiment with being a Bitcoin thief by changing the value of a transaction
    then showing how the new block would not get accepted by the Bitcoin
    network, due to changes to the merkle root and block hash.

    """
    print('\nBitcoin thief experiment')
    print('*' * 64 + '\n')
    btcs = new_value
    sat = btc_to_sat(btcs)

    # Change block value, merkle hash, and update checksum
    thief_block = change_block_value(my_block, block_number, sat)
    thief_block = thief_block.replace(thief_block[20:HEADER_SIZE], checksum(thief_block[HEADER_SIZE:]))

    # Print fields of the new thief block
    end = HEADER_SIZE + 80
    thief_block_hash = swap_endian(hash(thief_block[HEADER_SIZE:end])).hex()
    print_message(thief_block, '*** TEST (value has changed) *** ')

    # Get the next block and verify it's prev block hash doesn't match the
    # new hash of the altered/thief block
    print('\nBlock # {} data: '.format(block_number + 1))
    next_block_hash = last_500_blocks[(block_number) % 500]
    getdata_msg = build_message('getdata', getdata_message(2, next_block_hash))
    next_block = exchange_messages(getdata_msg, wait=True)
    next_block = b''.join(next_block)
    prev_block_hash =swap_endian(next_block[28:60]).hex()
    print('\nBlock {} prev block hash : {}'.format(block_number + 1, prev_block_hash))
    print('Block {} altered hash: {}'.format(block_number, thief_block_hash))
    print('{} == {} -> {} -> reject!'.format(prev_block_hash, thief_block_hash,
                                             prev_block_hash == thief_block_hash))


def main():
    """Executes program from main entry point."""
    if len(sys.argv) != 2:
        print('Usage: bitcoin_explorer.py BLOCK_NUMBER')
        exit(1)

    # Block number from command line argument
    block_number = int(sys.argv[1])

    with BTC_SOCK:
        # Establish connection with Bitcoin node
        BTC_SOCK.connect(BTC_PEER_ADDRESS)

        # Send version -> receive version, verack
        version_bytes = build_message('version', version_message())
        peer_vsn_bytes = exchange_messages(version_bytes, expected_bytes=126)[0]
        peer_height = peer_height_from_version(peer_vsn_bytes)

        # Send verack -> receive sendheaders, sendcmpct, ping, addr, feefilter
        verack_bytes = build_message('verack', EMPTY_STRING)
        exchange_messages(verack_bytes, expected_bytes=202)

        # Send ping -> receive pong
        ping_bytes = build_message('ping', ping_message())
        exchange_messages(ping_bytes, expected_bytes=32)

        # Check supplied block number against peer's blockchain height
        if block_number > peer_height:
            print('\nCould not retrieve block {}: max height is {}'.format(block_number, peer_height))
            exit(1)

        # Send getblocks (starting from genesis) -> receive inv
        block_hash = swap_endian(BLOCK_GENESIS)
        current_height = 0
        # Store last 500 blocks from inv messages
        last_500_blocks = []
        # Keep sending getblocks until inventory has the desired block number
        while current_height < block_number:
            last_500_blocks, current_height = send_getblocks_message(block_hash, current_height)
            block_hash = last_500_blocks[-1]

        # Retrieve block, send getdata for the block -> receive block message
        my_block_hash = last_500_blocks[(block_number - 1) % 500]
        getdata_bytes = build_message('getdata', getdata_message(2, my_block_hash))
        msg_list = exchange_messages(getdata_bytes, height=block_number, wait=True)
        my_block = b''.join(msg_list)

        # Pick new reward value for the bitcoin
        thief_experiment(my_block, block_number, last_500_blocks, 4000)


if __name__ == '__main__':
    main()
