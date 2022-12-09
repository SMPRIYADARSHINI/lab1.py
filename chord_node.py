"""
Implement using Python 3 the Chord system as described in the original paper
from 2001 by Stoica, Morris, Karger, Kaashoek, and Balakrishna. The chord
network is represented as a circle of nodes, each with an M-bit identifier
(default 160-bits) obtained via hashing of the node's IP address. Hashing is
done using SHA-1. Uses TCP sockets and multithreading to handle concurrent
RPC requests.


Author: PRIYADARSHINI SHANMUGASUNDARAM MURUGAN
Date: 11/18/2022
Course: DISTRIBUTED SYSTEM
"""

# Importing libraries

import socket
import sys
import pickle
import hashlib
from threading import Thread, Lock
from datetime import datetime
from enum import Enum

# M-bit identifier space
M_BIT = hashlib.sha1().digest_size * 8

# Node IDs range from (0, 2^M - 1)
NODES = 2 ** M_BIT

# socket connection
BUF_SZ = 8192  # socket.recv arg
BACKLOG = 100  # socket.listen arg
MIN_PORT = 43544
MAX_PORT = 2 ** 16
DEFAULT_HOST = 'localhost'
RPC_TIMEOUT = 1.5

# Last 25 finger table entries or all
TABLE_I = M_BIT - 25 if M_BIT - 25 > 0 else 1


class ModRange(object):

    def __init__(self, start, stop, divisor):
        self.divisor = divisor
        self.start = start % self.divisor
        self.stop = stop % self.divisor

        # we want to use ranges to make things speedy, but if it wraps around
        # the 0 node, we have to use two
        if self.start < self.stop:
            self.intervals = (range(self.start, self.stop),)
        elif self.stop == 0:
            self.intervals = (range(self.start, self.divisor),)
        else:
            self.intervals = (range(self.start, self.divisor), range(0, self.stop))

    def __repr__(self):
        """ Something like the interval|node charts in the paper """
        return ''.format(self.start, self.stop, self.divisor)

    def __contains__(self, id):
        """ Is the given id within this finger's interval? """
        for interval in self.intervals:
            if id in interval:
                return True
        return False

    def __len__(self):
        total = 0
        for interval in self.intervals:
            total += len(interval)
        return total

    def __iter__(self):
        return ModRangeIter(self, 0, -1)


class ModRangeIter(object):
    """ Iterator class for ModRange """

    def __init__(self, mr, i, j):
        self.mr, self.i, self.j = mr, i, j

    def __iter__(self):
        return ModRangeIter(self.mr, self.i, self.j)

    def __next__(self):
        if self.j == len(self.mr.intervals[self.i]) - 1:
            if self.i == len(self.mr.intervals) - 1:
                raise StopIteration()
            else:
                self.i += 1
                self.j = 0
        else:
            self.j += 1
        return self.mr.intervals[self.i][self.j]


class FingerEntry(object):


    def __init__(self, n, k, node=None):
        if not (0 <= n < NODES and 0 < k <= M_BIT):
            raise ValueError('invalid finger entry values')
        self.start = (n + 2 ** (k - 1)) % NODES
        self.next_start = (n + 2 ** k) % NODES if k < M_BIT else n
        self.interval = ModRange(self.start, self.next_start, NODES)
        self.node = node
        self.k = k

    def __repr__(self):
        """ Something like the interval|node charts in the paper """
        return '{:3} | {:<2} | [{:2}, {:<2}) | {}'.format(self.k, self.start, self.start, self.next_start, self.node)

    def __contains__(self, id):
        """ Is the given id within this finger's interval? """
        return id in self.interval


class RPC(Enum):
    """
    Remote procedure call (RPC) enum class for organizing names of methods that
    can be invoked on other nodes via an RPC call.
    """

    FIND_SUCCESSOR = 'find_successor'
    FIND_PREDECESSOR = 'find_predecessor'
    CLOSEST_PRECEDING_FINGER = 'closest_preceding_finger'
    SUCCESSOR = 'successor'
    UPDATE_FINGER_TABLE = 'update_finger_table'
    SET_PREDECESSOR = 'set_predecessor'
    GET_PREDECESSOR = 'get_predecessor'
    ADD_KEY = 'add_key'
    GET_DATA = 'get_data'
    UPDATE_KEYS = 'update_keys'


class ChordNode(object):
    """
    A single node in a Chord network. Each node has a finger table and knows its
    successor and predecessor nodes.
    """

    def __init__(self, port, buddy_port=None):
        """
        Initializes this chord node's ID, listening address, server thread, and
        finger table layout.
        """

        self.address = (DEFAULT_HOST, port)
        self.node = Chord.lookup_node(self.address)
        # 1-based indexing -> 1 <= i <= M
        self.finger = [None] + [FingerEntry(self.node, k) for k in range(1, M_BIT + 1)]
        self.predecessor = None
        self.keys = {}
        self.buddy_node = Chord.lookup_node((DEFAULT_HOST, buddy_port)) if buddy_port else None
        self.lock = Lock()
        self.listener = self.start_listening_server()
        self.joined = False
        print('Node ID = {} is on {}'.format(self.node, self.address))
        Thread(target=self.run_server).start()

    def start_listening_server(self):
        """
        Starts a TCP listening server.
        """

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(self.address)
        listener.listen(BACKLOG)
        return listener

    def run_server(self):
        """
        Runs the server loop that listens for incoming connections using
        multithreading.
        """

        while True:
            if self.joined:
                print(self.print_node_data())

            print('\nPort {}: waiting for incoming connection ...\n'.format(self.address[1]))
            client_sock, client_address = self.listener.accept()
            Thread(target=self.handle_rpc, args=(client_sock,)).start()

    def handle_rpc(self, client_sock):
        """
        Handles any RPC calls requested from other nodes, discovered from the
        thread server loop, and sends back the result to the client node.
        """

        rpc = client_sock.recv(BUF_SZ)
        method, arg1, arg2 = pickle.loads(rpc)
        print('Received RPC request: \"{}\" at [{}]'.format(method, Chord.print_time()))
        result = self.dispatch_rpc(method, arg1, arg2)
        client_sock.sendall(pickle.dumps(result))

    def dispatch_rpc(self, method, arg1=None, arg2=None):
        """
        Dispatches RPC call from another node to a local method call on
        this node.
        """

        if method == RPC.FIND_SUCCESSOR.value:
            return self.find_successor(arg1)

        elif method == RPC.SUCCESSOR.value:
            if arg1:
                self.successor(arg1)
            else:
                return self.successor

        elif method == RPC.CLOSEST_PRECEDING_FINGER.value:
            return self.closest_preceding_finger(arg1)

        elif method == RPC.UPDATE_FINGER_TABLE.value:
            print(self.update_finger_table(arg1, arg2))

        elif method == RPC.SET_PREDECESSOR.value:
            self.set_predecessor(arg1)

        elif method == RPC.GET_PREDECESSOR.value:
            return self.get_predecessor()

        elif method == RPC.ADD_KEY.value:
            return self.add_key(arg1, arg2)

        elif method == RPC.GET_DATA.value:
            return self.get_data(arg1)

        elif method == RPC.UPDATE_KEYS.value:
            return self.update_keys()

        else:
            print('RPC failure at [{}]: no such method exists'
                  .format(Chord.print_time()))

        return 'no return value'

    def call_rpc(self, n_prime, method: RPC, arg1=None, arg2=None):
        """
        Makes an RPC call to the given method, with the given arguments. If no
        arguments are passed, assume that the method to invoke does not take
        any arguments. No RPC method takes more than 2 arguments currently.
        """
        method_name = method.value

        if n_prime == self.node:
            # If RPC requested on myself, then just do a local call
            return self.dispatch_rpc(method_name, arg1, arg2)

        bad_port = None
        for _ in range(50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as n_prime_sock:
                n_prime_address = Chord.lookup_address(n_prime, bad_port)
                n_prime_sock.settimeout(RPC_TIMEOUT)

                try:
                    n_prime_sock.connect(n_prime_address)
                    marshalled_data = pickle.dumps((method_name, arg1, arg2))
                    n_prime_sock.sendall(marshalled_data)
                    return pickle.loads(n_prime_sock.recv(BUF_SZ))

                except Exception as e:
                    print('Failed to connect to Node ID = {}, thread might be busy. RPC aborted at [{}]'
                          .format(n_prime, Chord.print_time()))
                    if bad_port:
                        bad_port = n_prime_address[1]

    @property
    def successor(self):
        """
        Returns successor of this node which is first entry in its finger table.
        """
        return self.finger[1].node

    @successor.setter
    def successor(self, id):
        """
        Sets the successor of this node at the first entry in its finger table.
        """

        self.finger[1].node = id

    def set_predecessor(self, node):
        """
        Sets the predecessor of this node
        """
        self.predecessor = node

    def get_predecessor(self):
        """
        Returns the predecessor of this node.
        """
        return self.predecessor

    def find_successor(self, id):
        """
        Finds and returns the successor of the given M-bit ID.
        """

        # Ask predecessor node for its successor through RPC call
        n_prime = self.find_predecessor(id)
        return self.call_rpc(n_prime, RPC.SUCCESSOR)

    def find_predecessor(self, id):
        """
        Finds and returns the predecessor of the given M-bit ID.
        """
        n_prime = self.node
        while id not in ModRange(n_prime + 1, self.call_rpc(n_prime, RPC.SUCCESSOR) + 1, NODES):
            n_prime = self.call_rpc(n_prime, RPC.CLOSEST_PRECEDING_FINGER, id)
        return n_prime

    def closest_preceding_finger(self, id):
        """
        Finds and returns the node, in this node's finger table, that is the
        closest preceding node to the given M-bit ID.
        """
        # Starting at the bottom of the table
        for i in range(M_BIT, 0, -1):
            if self.finger[i].node in ModRange(self.node + 1, id, NODES):
                return self.finger[i].node
        return self.node

    def join(self):
        """
        Joins this node to the network. If there's an existing network, it will
        ask its buddy node for help setting up its finger table.
        """
        if self.buddy_node is not None:
            self.init_finger_table()
            self.update_others()
            # Tell successor that I'll take over the keys from your old
            # predecessor because that's now my predecessor
            self.call_rpc(self.successor, RPC.UPDATE_KEYS)
        else:
            for i in range(1, M_BIT + 1):
                self.finger[i].node = self.node
            self.predecessor = self.node

        self.joined = True
        print('Joined network at [{}]'.format(Chord.print_time()))
        print('Initialize finger table complete at [{}]'.format(Chord.print_time()))
        print(self.print_node_data())

    def update_keys(self):
        """
        Updates this node's key bucket. Transfers any keys that are now out of
        range from predecessor to myself to the key's new successor, then
        removes any keys that were transferred.
        """
        if not self.keys:
            print('did nothing')
            return

        self.lock.acquire()
        remove_list = []
        for key, data in self.keys.items():
            # Transfer and remove any keys that are not between my predecessor
            # and myself
            if key not in ModRange(self.predecessor + 1, self.node + 1, NODES):
                remove_list.append(key)
                n_prime = self.find_successor(key)
                self.call_rpc(n_prime, RPC.ADD_KEY, key, data)
                print('Transferred key {} to Node ID = {} at [{}]'.format(key, n_prime, Chord.print_time()))
        self.lock.release()

        self.remove_keys(remove_list)
        if self.keys:
            print('Keys: {}'.format(self.print_keys()))

    def remove_keys(self, remove_list):
        """
        Remove any keys from the key bucket recorded in the given list.
        """
        # Give access to only one thread at a time
        self.lock.acquire()
        for key in remove_list:
            del self.keys[key]
        self.lock.release()

    def init_finger_table(self):
        """
        Initializes this node's finger table of successor nodes with help from
        the buddy node.
        """
        self.successor = self.call_rpc(self.buddy_node, RPC.FIND_SUCCESSOR, self.finger[1].start)
        self.predecessor = self.call_rpc(self.successor, RPC.GET_PREDECESSOR)
        self.call_rpc(self.successor, RPC.SET_PREDECESSOR, self.node)

        for i in range(1, M_BIT):
            if self.finger[i + 1].start in ModRange(self.node, self.finger[i].node, NODES):
                self.finger[i + 1].node = self.finger[i].node
            else:
                self.finger[i + 1].node = self.call_rpc(self.buddy_node, RPC.FIND_SUCCESSOR, self.finger[i + 1].start)

    def update_others(self):
        """
        Update all other node that should have this node in their
        finger tables
        """
        # find last node p whose i-th finger might be this node
        for i in range(1, M_BIT + 1):
            p = self.find_predecessor((1 + self.node - 2 ** (i - 1) + NODES) % NODES)
            self.call_rpc(p, RPC.UPDATE_FINGER_TABLE, self.node, i)

    def update_finger_table(self, s, i):
        """ If s is i-th finger of n, update this node's finger table with s """
        if (self.finger[i].start != self.finger[i].node
                and s in ModRange(self.finger[i].start, self.finger[i].node, NODES)):
            print('update_finger_table({},{}): {}[{}] = {} since {} in [{},{}) at [{}]'
                  .format(s, i, self.node, i, s, s, self.finger[i].start, self.finger[i].node, Chord.print_time()))
            self.finger[i].node = s
            p = self.predecessor  # get first node preceding myself
            self.call_rpc(p, RPC.UPDATE_FINGER_TABLE, s, i)
            return print(self.print_finger_table())
        else:
            return 'did nothing {}'.format(self.node)

    def add_key(self, key, data):
        """
        Adds the data to the key map. Recursively finds successor of the key
        through RPC calls. The data maps to an M-bit key, defined by the
        identifier space, so no key ID shall be >= NODES.
        """
        if key >= NODES:
            raise ValueError('Error: maximum ID allowed is {}'.format(NODES - 1))

        if key in ModRange(self.predecessor + 1, self.node + 1, NODES):
            self.keys[key] = data
            msg = 'Added key {} at [{}]'.format(key, Chord.print_time())
            print(msg)
            return 'Node ID = {} {}'.format(self.node, msg)
        else:
            # If key is not mine, then find the successor who should be
            # responsible and tell them to add it to their bucket
            n_prime = self.find_successor(key)
            return self.call_rpc(n_prime, RPC.ADD_KEY, key, data)

    def get_data(self, key):
        """
        Get data associated with the key.
        """
        if key >= NODES:
            raise ValueError('Error: maximum ID stored is {}'.format(NODES - 1))

        if key in ModRange(self.predecessor + 1, self.node + 1, NODES):
            print('Retrieved key {} at [{}]'.format(key, Chord.print_time()))
            return self.keys[key] if key in self.keys else None
        else:
            # If key is not mine, then find the successor who is responsible
            n_prime = self.find_successor(key)
            return self.call_rpc(n_prime, RPC.GET_DATA, key)

    def print_node_data(self):
        """Printing helper for this node's data."""
        return ''.join(['\n******** Data ********\n',
                        'node ID: {}\n'.format(self.node),
                        'predecessor: {}\n'.format(self.predecessor),
                        'successor: {}\n'.format(self.successor),
                        'keys: {}\n'.format(self.print_keys()),
                        '\nFinger table:\n', self.print_finger_table(),
                        '\n**********************\n'])

    def print_keys(self):
        key_list = list(self.keys.keys())
        return ', '.join(str(key) for key in key_list) if self.keys else 'nothing'

    def print_finger_table(self):
        """Printing helper for finger table contents."""
        return '\n'.join([str(row) for row in self.finger[TABLE_I:]])


class Chord(object):
    """
    Responsible for any client-requested Chord lookup operations, such as
    populating or requesting data from the Chord network.
    """

    # Key: node ID -> computed using SHA1 160-bit hash of the IP address
    # Value: IP address -> (host, port) pair

    node_map = {}

    # Included this for testing environments where is M much smaller than the
    # default 160-bits, in which case hash key collisions are bound to occur.
    # If using default M = 160-bits keeping track of "bad ports" shouldn't
    # be necessary.

    bad_port_list = []

    @staticmethod
    def contact_node(address, method: RPC, key_map=None, key=None):
        """
        Helper method for either populating data to or retrieving data from the
        node at the given address in the chord network Chord  network.
        - If key_map is supplied, an RPC request for ADD_KEY is made: each key
          gets added to the network
        - If key is supplied, an RPC request for GET_DATA is made: the data is
          mapped to the given key is retrieved
       """
        if method != RPC.ADD_KEY and method != RPC.GET_DATA:
            raise ValueError('Only \'{}\' or \'{}\' RPC requests are permitted.'
                             .format(RPC.ADD_KEY.value, RPC.GET_DATA.value))

        if key:
            key_map = {key: None}

        data_retrieved = []

        for key, data in key_map.items():
            key_id = Chord.hash_160(key) % NODES

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.connect(address)
                    marshalled_data = pickle.dumps((method.value, key_id, data))
                    sock.sendall(marshalled_data)

                except Exception as e:
                    print('RPC request \'{}\' failed at [{}].'.format(method.value, Chord.print_time()))
                    data_retrieved.append(None)
                    return data_retrieved

                else:
                    data_retrieved.append(pickle.loads(sock.recv(BUF_SZ)))

        return data_retrieved

    @staticmethod
    def populate(address, keys: dict):
        """
        Populates the Chord network with the given dictionary keys mapped to
        their data elements.
        """
        return Chord.contact_node(address, RPC.ADD_KEY, key_map=keys)

    @staticmethod
    def lookup_key(address, key: str):
        """
        Asks the Chord node at the given address to lookup the given key, and
        returns the data that the key is mapped to.
        """
        return Chord.contact_node(address, RPC.GET_DATA, key=key)[0]

    @staticmethod
    def lookup_address(node, bad_port=None):
        """
        Returns the address of the given node in the node_map. If the node
        has no address mapping yet, finds the address and records it for
        any future lookups for the same node.
        """
        if bad_port:
            # Record any ports whose addresses hashed to an existing node ID
            # who wasn't actually listening on that port
            Chord.bad_port_list.append(bad_port)
            del Chord.node_map[node]

        if node not in Chord.node_map:
            for port in range(MIN_PORT, MAX_PORT):
                # Skip bad port
                if port in Chord.bad_port_list:
                    continue

                address = (DEFAULT_HOST, port)
                generated_node = Chord.lookup_node(address)

                if generated_node == node:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        try:
                            sock.bind(address)
                        except Exception as e:
                            # If binding fails, node is listening at that port
                            Chord.node_map[node] = address
                            return address

            return None

        return Chord.node_map[node]

    @staticmethod
    def lookup_node(address):
        """
        Converts a (host, port) address to an M_BIT ID, and returns that ID.
        """
        return Chord.hash_160(address) % NODES

    @staticmethod
    def hash_160(data):
        """
        Returns 160-bit integer of the hash computed using SHA1.
        """
        marshalled_data = pickle.dumps(data)
        marshalled_hash = hashlib.sha1(marshalled_data).digest()
        return int.from_bytes(marshalled_hash, byteorder='big')

    @staticmethod
    def get_empty_port():
        """
        Returns a system-assigned port number within the specified port range.
        """
        port = -1
        while port not in range(MIN_PORT, MAX_PORT):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((DEFAULT_HOST, 0))
                port = sock.getsockname()[1]
        return port

    @staticmethod
    def print_time():
        """
        Printing helper for current timestamp.
        """
        return datetime.now().strftime('%H:%M:%S.%f')


def main():
    """
    Executing program from the main .
    """

    # Expects one additional argument
    if len(sys.argv) != 2:
        print('Usage note: chord_node.py NODE_PORT_NUMBER (Enter zero if '
              'it is new network)')
        exit(1)

    known_node_port = int(sys.argv[1])
    new_node_port = Chord.get_empty_port()

    if known_node_port == 0:

        # Start new network
        new_node = ChordNode(new_node_port)
    else:

        # Join existing network with a next node
        new_node = ChordNode(new_node_port, known_node_port)

    new_node.join()
    new_node.run_server()


if __name__ == '__main__':
    main()
