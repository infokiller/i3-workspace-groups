#!/usr/bin/env python3
# pylint: disable=invalid-name

import socket
import sys


def main():
    if len(sys.argv) != 2:
        raise ValueError('Usage: i3-workspace-groups-nc SOCKET')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sys.argv[1])
    cmd = sys.stdin.buffer.read()
    sock.sendall(cmd)
    output = sock.recv(100000)
    print(output.decode('utf-8'))


if __name__ == '__main__':
    main()
