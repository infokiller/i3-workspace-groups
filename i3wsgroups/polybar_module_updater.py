#!/usr/bin/python3

import asyncio
import subprocess

from i3ipc import Event
from i3ipc.aio import Connection


def _update_polybar(*_):
    subprocess.run(['polybar-msg', 'action', '#i3-mod.hook.0'], check=False)


async def main():
    i3 = await Connection(auto_reconnect=True).connect()

    _update_polybar()
    i3.on(Event.WORKSPACE_FOCUS, _update_polybar)
    i3.on(Event.WORKSPACE_INIT, _update_polybar)
    i3.on(Event.WORKSPACE_RENAME, _update_polybar)
    i3.on(Event.WORKSPACE_MOVE, _update_polybar)
    i3.on(Event.WORKSPACE_EMPTY, _update_polybar)

    await i3.main()


if __name__ == '__main__':
    asyncio.run(main())
