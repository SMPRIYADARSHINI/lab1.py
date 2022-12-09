"""""
 CPSC 5520, Seattle University
 programmer : Priyadarshini
"""


import pickle   # importing libraries
import sys
import socket

if __name__ == '__main__':
    gcd = sys.argv[1]      # getting host
    port = int(sys.argv[2])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as a:  #  building socket server

        a.connect((gcd,port))                                   # Connect to an IP with Port
        print("JOIN", (gcd,port))
        a.sendall(pickle.dumps('JOIN'))                         # sending message
                                                                # receiving a message
        subject = pickle.loads(a.recv(1024))

    for s in subject:
        y = s['host']
        q = s['port']
        print("Hello to", s)
        try:                                                            # error handling
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as x:
                x.settimeout(1.5)
                x.connect((y, q))
                x.sendall(pickle.dumps('HELLO'))
                t = pickle.loads(x.recv(1024))
                print('Received', t)
        except socket.error as e:
            print(e)






