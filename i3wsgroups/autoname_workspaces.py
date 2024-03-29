#!/usr/bin/env python3
# pylint: disable=invalid-name
# Inspired by:
# https://github.com/maximbaz/dotfiles/blob/master/bin/i3-autoname-workspaces

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os.path
import pprint

import i3ipc
import i3ipc.events

from i3wsgroups import cli_util
from i3wsgroups import controller
from i3wsgroups import i3_proxy
from i3wsgroups import log_util
from i3wsgroups import workspace_names

init_logger = log_util.init_logger
logger = log_util.logger


class WorkspaceAutonamer:

    def __init__(self, config, dry_run: bool = True):
        self.dry_run = dry_run
        self.config = config

    def create_controller(self,
                          i3_connection: i3ipc.Connection) -> controller.WorkspaceGroupsController:
        return controller.WorkspaceGroupsController(i3_proxy.I3Proxy(i3_connection, self.dry_run),
                                                    self.config)

    def update_workspace_names(self, i3_connection: i3ipc.Connection) -> None:
        groups_controller = self.create_controller(i3_connection)
        group_to_workspaces = workspace_names.get_group_to_workspaces(
            groups_controller.i3_proxy.get_monitor_workspaces())
        groups_controller.organize_workspace_groups(list(group_to_workspaces.items()))

    def window_event_handler(self, i3_connection: i3ipc.Connection,
                             event: i3ipc.events.IpcBaseEvent) -> None:
        assert isinstance(event, i3ipc.WindowEvent)
        logger.debug('Got window event with change: %s', event.change)
        if event.change in ['new', 'close', 'move']:
            self.update_workspace_names(i3_connection)

    def workspace_event_handler(self, i3_connection: i3ipc.Connection,
                                event: i3ipc.events.IpcBaseEvent):
        assert isinstance(event, i3ipc.WorkspaceEvent)
        logger.debug('Got workspace event with change: %s', event.change)
        # We must update the workspace names on a focus event because the
        # workspace focus change may be due to navigating away from an empty
        # workspace that was the only one in the active group. In that case, the
        # next group becomes active, so the icons should be restored to the
        # workspace names.
        if event.change == 'focus':
            self.update_workspace_names(i3_connection)


def main():
    parser = argparse.ArgumentParser(
        description='Runs in the background and automatically renames i3 '
        'workspaces according to the running apps.')
    cli_util.add_common_args(parser)
    cli_util.add_workspace_naming_args(parser)
    args = parser.parse_args()
    init_logger(os.path.basename(__file__))
    logger.setLevel(getattr(logging, args.log_level.upper(), 'WARNING'))

    config = cli_util.get_config_with_overrides(args)
    logger.debug('Using merged config:\n%s', pprint.pformat(config))

    autonamer = WorkspaceAutonamer(config, args.dry_run)
    i3_connection = i3ipc.Connection()
    autonamer.update_workspace_names(i3_connection)
    i3_connection.on(i3ipc.Event.WINDOW, autonamer.window_event_handler)
    i3_connection.on(i3ipc.Event.WORKSPACE_FOCUS, autonamer.workspace_event_handler)
    i3_connection.main()


if __name__ == '__main__':
    main()
