#!/usr/bin/env python3

# This is a simple implementation of an i3-workspace-groups client in pure
# python with no external dependencies. This is slower than
# ./i3-workspace-groups-client which uses external tools under the hood (socat,
# nc, etc.), so it's not used except for benchmarking.

# pylint: disable=invalid-name

from __future__ import annotations

import os
import socket
import sys


def main():
    socket_path = os.environ.get(
        'I3_WORKSPACE_GROUPS_SOCKET',
        os.path.expandvars('${XDG_RUNTIME_DIR}/i3-workspace-groups-' +
                           os.environ['DISPLAY'].replace(':', '')))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    sock.sendall('\n'.join(sys.argv[1:]).encode('utf-8'))
    output = sock.recv(100000).decode('utf-8')
    print(output)
    if output.startswith('error:'):
        sys.exit(1)


if __name__ == '__main__':
    main()
