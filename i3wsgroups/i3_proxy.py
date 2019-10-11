from typing import Dict, List, Optional

import i3ipc

from i3wsgroups import logger

logger = logger.logger

class I3Proxy:

    def __init__(self,
                 i3_connection: i3ipc.Connection,
                 dry_run: bool = True):
        self.i3_connection = i3_connection
        self.dry_run = dry_run
        # i3 tree is cached for performance. Timing the i3ipc get_tree function
        # using `%timeit` in ipython shows about 1-2ms in my high performance
        # desktop. For lower performance machines, multiple calls to get_tree
        # may be noticable, so this is cached.
        # Other operations like get_workspaces and get_outputs were about 50µs
        # using the same method, which is more negligible.
        self.tree = None

    def get_tree(self, cached: bool = True) -> i3ipc.Con:
        if self.tree and cached:
            return self.tree
        self.tree = self.i3_connection.get_tree()
        return self.tree

    def get_monitor_index(self, monitor_name):
        ordered_monitors = [
            output for output in self.i3_connection.get_outputs()
            if output.active
        ]
        # Sort monitors from top to bottom, and from left to right.
        ordered_monitors.sort(key=lambda m: (m.rect.y, m.rect.x))
        return [m.name for m in ordered_monitors].index(monitor_name)

    def get_focused_monitor_name(self) -> str:
        con = self.get_tree().find_focused()
        while con.type != 'output':
            con = con.parent
        return con.name

    def get_monitor_workspaces(self, monitor_name: Optional[str] = None
                              ) -> List[i3ipc.Con]:
        if monitor_name is None:
            monitor_name = self.get_focused_monitor_name()
        return self.get_monitor_to_workspaces()[monitor_name]

    def get_monitor_to_workspaces(self) -> Dict[str, List[i3ipc.Con]]:
        active_monitor_names = [
            output.name for output in self.i3_connection.get_outputs()
            if output.active
        ]
        monitor_to_workspaces = {}
        # We could do this more efficiently by assuming that the outputs are the
        # direct children of the root, instead of scanning the whole tree to
        # find them, but this should be negligible.
        for con in self.get_tree():
            if con.type == 'output' and con.name in active_monitor_names:
                workspaces = [c for c in con if c.type == 'workspace']
                monitor_to_workspaces[con.name] = workspaces
        return monitor_to_workspaces

    def send_i3_command(self, command: str) -> None:
        if self.dry_run:
            log_prefix = '[dry-run] would send'
        else:
            log_prefix = 'Sending'
        logger.info("%s i3 command: '%s'", log_prefix, command)
        if not self.dry_run:
            reply = self.i3_connection.command(command)[0]
            if not reply.success:
                logger.warning('i3 command error: %s', reply.error)

    def focus_workspace(self, name: str,
                        auto_back_and_forth: bool = True) -> None:
        options = ''
        if not auto_back_and_forth:
            options = '--no-auto-back-and-forth'
        self.send_i3_command('workspace {} "{}"'.format(options, name))

    def rename_workspace(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return
        self.send_i3_command('rename workspace "{}" to "{}"'.format(
            old_name, new_name))

    def get_unique_marked_workspace(self, mark) -> Optional[i3ipc.Con]:
        workspaces = self.get_tree().find_marked(mark)
        if not workspaces:
            logger.info('Didn\'t find workspaces with mark: %s', mark)
            return None
        if len(workspaces) > 1:
            logger.warning(
                'Multiple workspaces marked with %s, using first '
                'one', mark)
        return workspaces[0]
