"""
Query a single node in the Chord network for a key from the csv file.

Author: PRIYADARSHINI SHANMUGASUNDARAM MURUGAN
Date: 11/18/2022
Course: DISTRIBUTED SYSTEM
"""

from chord_node import Chord
import sys


def print_data(key, data_list):
    """
    PRINT THE DETAILS OF THE PLAYER BY PASSING KEY AND YEAR AS A ARGUMENT
    """
    if data_list:
        id = data_list[0][1]
        year = data_list[2][1] if data_list[2][0] == 'Year' else data_list[3][1]
        retrieved_key = id + year

        if retrieved_key == key:
            for label, data in data_list:
                print('{}: {}'.format(label, data))
        else:
            print('KEY IS IN VALID: key \'{}\' DOES NOT MATCH'
                  'key \'{}\''.format(key, retrieved_key))
    else:
        print('THERE IS NO DATA FOUND HERE.....')


def main():
    """
    Executes program from the main entry point.
    """
    # Expects 2 additional arguments

    if len(sys.argv) != 3:
        print('Usage: chord_query.py NODE_PORT KEY (playerID + year)')
        exit(1)

    address = ('localhost', int(sys.argv[1]))
    key = sys.argv[2]
    print('Asking Node {} to lookup up data for key = \'{}\' ...\n'
          .format(Chord.lookup_node(address), key))

    data_list = Chord.lookup_key(address, key)
    print_data(key, data_list)


if __name__ == '__main__':
    main()
