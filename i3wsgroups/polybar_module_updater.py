#!/usr/bin/python3

import asyncio
import subprocess

from i3ipc import Event
from i3ipc.aio import Connection


def _update_polybar(*_):
    # As of 2021-10-15 and PR #2539 [1] running the hook action is deprecated.
    # We should switch to the commented out alternative, but we'll wait till
    # this change is a bit older to reduce the risk that we break the setup of
    # people that run older versions of polybar.
    # [1] https://github.com/polybar/polybar/pull/2539
    # subprocess.run(['polybar-msg', 'action', '#i3-mod.hook.0'], check=False)
    subprocess.run(['polybar-msg', 'hook', 'i3-mod', '1'], check=False)


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
