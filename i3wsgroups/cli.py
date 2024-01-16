#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import os.path
import pprint
import sys

import i3ipc

from i3wsgroups import cli_util
from i3wsgroups import controller as i3_groups_controller
from i3wsgroups import i3_proxy
from i3wsgroups import log_util
from i3wsgroups import workspace_names

_LIST_WORKSPACES_FIELDS = workspace_names.WORKSPACE_NAME_SECTIONS + [
    'window_icons', 'global_name', 'monitor', 'focused'
]
_LIST_WORKSPACES_FIELDS_HELP = ('Comma separated list of fields to output. '
                                f'Options: {", ".join(_LIST_WORKSPACES_FIELDS)}')

init_logger = log_util.init_logger
logger = log_util.logger


def _add_group_args(parser: argparse.ArgumentParser) -> None:
    # The argparse argument group of the workspace group arguments.
    group_arg_group = parser.add_mutually_exclusive_group()
    group_arg_group.add_argument('--group-active',
                                 action='store_true',
                                 default=None,
                                 help='Use the active group for commands that implicitly assume a '
                                 'group, such as workspace-next.')
    group_arg_group.add_argument('--group-focused',
                                 action='store_true',
                                 default=None,
                                 help='Use the focused group for commands that implicitly assume a '
                                 'group, such as workspace-next.')
    group_arg_group.add_argument('--group-name')


def _add_list_workspaces_args(parser: argparse.ArgumentParser) -> None:
    _add_group_args(parser)
    parser.add_argument('--fields',
                        default=','.join(_LIST_WORKSPACES_FIELDS),
                        help=_LIST_WORKSPACES_FIELDS_HELP)
    parser.add_argument('--focused-only',
                        action='store_true',
                        help='List only the focused workspace in the given group context.')
    parser.add_argument('--focused-monitor-only',
                        action='store_true',
                        help='List only workspaces on the current monitor.')


def _add_rename_workspace_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--name',
                        help='New name to set for the workspace.\n'
                        'Note that this is not the same as the workspace number.\n'
                        'If not provided, keeps the existing name.')
    parser.add_argument('--number',
                        type=int,
                        help='New number to set for the workspace.\n'
                        'Note that this is not the same as the workspace name.\n'
                        'If not provided, keeps the existing number.')
    parser.add_argument('--group',
                        help='Group to assign to the focused workspace. If not provided, keeps '
                        'the existing group assignment.')


def _create_args_parser() -> cli_util.ArgumentParserNoExit:
    parser = cli_util.ArgumentParserNoExit(description='Control i3 workspace groups.')
    cli_util.add_common_args(parser)
    cli_util.add_workspace_naming_args(parser)
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    polybar_hook_parser = subparsers.add_parser(
        'polybar-hook', help='Return text for displaying to polybar i3-mod module')
    polybar_hook_parser.add_argument('--line-color', type=str, default="#ff9900")
    polybar_hook_parser.add_argument('--monitor', type=str)

    list_groups_parser = subparsers.add_parser('list-groups',
                                               help='List the groups of the current workspaces.')
    list_groups_parser.add_argument('--focused-monitor-only',
                                    action='store_true',
                                    help='List only workspaces in the current monitor.')
    list_workspaces_parser = subparsers.add_parser('list-workspaces',
                                                   help='List workspaces and their group.')
    _add_list_workspaces_args(list_workspaces_parser)
    workspace_number_parser = subparsers.add_parser(
        'workspace-number',
        help='Focus on the workspace with the provided number in the focused '
        'group, similar to i3\'s "workspace number" command')
    workspace_number_parser.add_argument('--no-auto-back-and-forth', action='store_true')
    workspace_number_parser.add_argument('workspace_relative_number', type=int)
    _add_group_args(workspace_number_parser)
    subparsers.add_parser('workspace-next',
                          help='Focus on the next workspace in the focused group, similar to '
                          'i3\'s "workspace next" command')
    subparsers.add_parser('workspace-prev',
                          help='Focus on the prev workspace in the focused group, similar to '
                          'i3\'s "workspace prev" command')
    workspace_new_parser = subparsers.add_parser(
        'workspace-new',
        help='Create a new workspace in the focused group with the lowest '
        'available number.')
    _add_group_args(workspace_new_parser)
    move_to_number_parser = subparsers.add_parser(
        'move-to-number',
        help='Move the focused container to the workspace with the provided '
        'number in the focused group, similar to i3\'s "move container to '
        'workspace" command')
    move_to_number_parser.add_argument('--no-auto-back-and-forth', action='store_true')
    move_to_number_parser.add_argument('workspace_relative_number', type=int)
    _add_group_args(move_to_number_parser)
    subparsers.add_parser('move-to-next',
                          help='Move the focused container to the next workspace in the focused '
                          'group, similar to i3\'s "move container to workspace next" command')
    subparsers.add_parser('move-to-prev',
                          help='Move the focused container to the previous workspace in the '
                          'focused group, similar to i3\'s "move container to workspace prev" '
                          'command')
    move_to_new_parser = subparsers.add_parser(
        'move-to-new',
        help='Move the focused container to a new workspace in the focused '
        'group with the lowest available number.')
    _add_group_args(move_to_new_parser)
    switch_active_group_parser = subparsers.add_parser(
        'switch-active-group', help='Switch the active group to the one provided.')
    switch_active_group_parser.add_argument('--focused-monitor-only', action='store_true')
    switch_active_group_parser.add_argument('group')
    rename_workspace_parser = subparsers.add_parser(
        'rename-workspace', help='Rename and optionally change the group of the focused workspace')
    _add_rename_workspace_args(rename_workspace_parser)
    assign_workspace_subparser = subparsers.add_parser(
        'assign-workspace-to-group', help='Assign the focused workspace to the provided group.')
    assign_workspace_subparser.add_argument(
        '--use-next-available-number',
        action='store_true',
        help='If a workspace is moved to another group which already has a '
        'workspace with the same number, use the next available number instead '
        ' of failing.')
    assign_workspace_subparser.add_argument('group')
    server_subparser = subparsers.add_parser('server')
    server_subparser.add_argument(
        '--server-addr',
        default=os.path.expandvars('${XDG_RUNTIME_DIR}/i3-workspace-groups-' +
                                   os.environ['DISPLAY'].replace(':', '')),
        help='Path for the unix domain socket used by the server')
    # Deprecated commands, will be removed in a future release.
    subparsers.add_parser('workspace-back-and-forth',
                          help='[DEPRECATED] Focus on the last focused workspace, similar to '
                          'i3\'s "workspace back_and_forth" command.')
    subparsers.add_parser('move-to-back-and-forth',
                          help='[DEPRECATED] Move the focused container to the last focused '
                          'workspace, similar to i3\'s "move container to back_and_forth" command')
    return parser


def _create_group_context(args):
    # args.group_name is empty if it refers to the default group
    if args.group_name is not None:
        return i3_groups_controller.NamedGroupContext(args.group_name)
    if args.group_active:
        return i3_groups_controller.ActiveGroupContext()
    if args.group_focused:
        return i3_groups_controller.FocusedGroupContext()
    return None


def _get_workspace_field(controller, workspace, field):
    if field == 'global_name':
        return workspace.name
    if field == 'focused':
        return 1 if workspace.find_focused() is not None else 0
    if field == 'monitor':
        con = workspace
        while con.type != 'output':
            con = con.parent
        return con.name
    if field == 'window_icons':
        return controller.icons_resolver.get_workspace_icons(workspace)
    parsed_name = workspace_names.parse_name(workspace.name)
    value = getattr(parsed_name, field)
    if value is None:
        return ''
    return value


def _print_workspaces(controller, args):
    fields = args.fields.split(',')
    for field in fields:
        if field not in _LIST_WORKSPACES_FIELDS:
            sys.exit(f'Invalid field: "{field}". Valid fields: '
                     f'{_LIST_WORKSPACES_FIELDS}')
    table = []
    for workspace in controller.list_workspaces(_create_group_context(args), args.focused_only,
                                                args.focused_monitor_only):
        row = []
        for field in fields:
            row.append(_get_workspace_field(controller, workspace, field))
        table.append(row)
    return '\n'.join('\t'.join(str(e) for e in row) for row in table)


# pylint: disable-next=too-many-statements
def serve(i3_connection, server_addr):
    # Add the imports here to avoid having a negative effect on clients not
    # using the server.
    # pylint: disable-next=import-outside-toplevel
    # import shlex
    # pylint: disable-next=import-outside-toplevel
    import socket

    # Make sure the socket does not already exist
    # TODO: lock the socket to avoid multiple servers trying to use the same
    # one.
    try:
        os.unlink(server_addr)
    except OSError:
        if os.path.exists(server_addr):
            raise
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(server_addr)
    sock.listen(1)
    while True:
        parser = _create_args_parser()
        logger.debug('Waiting for a connection')
        connection, addr = sock.accept()
        logger.debug(f'Connection from: {addr}')
        data = connection.recv(10000)
        if len(data) == 10000:
            logger.warning('Skipping unusually long command')
            continue
        try:
            client_argv = [s.decode('utf-8') for s in data.split(b'\n')]
        except UnicodeError:
            logger.warning('Failed decoding command args as utf-8')
            continue
        logger.info(f'Argv from client: {client_argv}')
        try:
            client_args = parser.parse_args(client_argv)
            if client_args.command == 'server':
                logger.warning('Ignoring nested server command')
                continue
            output = run_command(i3_connection, client_args)
            connection.sendall(output.encode('utf-8'))
        # argparse can raise SystemExit, but we use a wrapper over
        # ArgumentParser to avoid it.
        except argparse.ArgumentError as e:
            msg = f'error: failed parsing command: {e}'
            logger.warning(msg)
            connection.sendall(msg.encode('utf-8'))
            continue
        except cli_util.ExitCalledError as e:
            msg = e.message or ''
            if e.status == 0 and not msg:
                msg = e.parser.format_help()
            elif e.status != 0:
                msg = f'error: {msg}'
            logger.warning(msg)
            try:
                connection.sendall(msg.encode('utf-8'))
            except BrokenPipeError:
                # The client may have disconnected, so ignore the error.
                logger.warning('Failed sending error message to client')
            continue
        finally:
            # Clean up the connection
            connection.close()


def get_monitor_active_group(controller, groups_to_workspaces, monitor):
    active_group = ''
    min_global = float('inf')
    for (group, workspaces) in groups_to_workspaces.items():
        for ws in workspaces:
            if not monitor or _get_workspace_field(controller, ws, 'monitor') == monitor:
                global_number = _get_workspace_field(controller, ws, 'global_number')
                if global_number and global_number < min_global:
                    active_group = group
                    min_global = global_number
    return active_group


def _print_polybar_hook(controller, args):
    # Grab information about the i3 workspace states
    workspaces = controller.get_tree().workspaces()
    group_to_workspaces = workspace_names.get_group_to_workspaces(workspaces)
    active_group = get_monitor_active_group(controller, group_to_workspaces, args.monitor)

    # Lambdas for formatting polybar text with overline and underline
    def polybar_overline_format(text, color):
        return f'%{{o{color}}}%{{+o}}{text}%{{-o}}' if color else text

    def polybar_underline_format(text, color):
        return f'%{{u{color}}}%{{+u}}{text}%{{-u}}' if color else text

    formatted_group_info = []

    for group in sorted(group_to_workspaces.keys()):
        workspaces = group_to_workspaces[group]

        # Build parsed_names_dict to include the local numbers of the workspaces
        # relevant to this monitor and group
        parsed_names_dict = {}
        for ws in workspaces:
            # When monitor is specified, only include workspaces
            # on that monitor. Otherwise, include all workspaces.
            if not args.monitor or _get_workspace_field(controller, ws, 'monitor') == args.monitor:
                local_number = _get_workspace_field(controller, ws, 'local_number')
                focused = _get_workspace_field(controller, ws, 'focused')
                parsed_names_dict[local_number] = {'focused': focused}

        if parsed_names_dict:
            parsed_names = ''.join([
                polybar_underline_format(
                    f" {local_number} ",
                    args.line_color if parsed_names_dict[local_number]['focused'] else None)
                for local_number in sorted(parsed_names_dict.keys())
            ])

            formatted_group = polybar_overline_format(
                f"{group}:", args.line_color if active_group == group else None)

            formatted_group_info.append(f'{formatted_group}{parsed_names}')

    # Print each of the formatted group infos
    # separated by pipes.
    # The result looks something like:
    # Work: 1  2  |  Play: 3  5
    # Where "Work" and "Play" are the group names
    # and "1", "2", "3", and "5" are the local numbers.
    print(' |  '.join(formatted_group_info))


# pylint: disable=too-many-branches
# pylint: disable-next=no-else-return
def run_command(i3_connection, args):
    config = cli_util.get_config_with_overrides(args)
    logger.debug('Using merged config:\n%s', pprint.pformat(config))
    controller = i3_groups_controller.WorkspaceGroupsController(
        i3_proxy.I3Proxy(i3_connection, args.dry_run), config)
    if args.command == 'list-groups':
        return '\n'.join(controller.list_groups(args.focused_monitor_only))
    if args.command == 'polybar-hook':
        _print_polybar_hook(controller, args)
    if args.command == 'list-workspaces':
        return _print_workspaces(controller, args)
    if args.command == 'workspace-number':
        controller.focus_workspace_number(_create_group_context(args),
                                          args.workspace_relative_number)
    elif args.command == 'workspace-next':
        controller.focus_workspace_relative(+1)
    elif args.command == 'workspace-prev':
        controller.focus_workspace_relative(-1)
    elif args.command == 'workspace-new':
        controller.focus_new_workspace(_create_group_context(args))
    elif args.command == 'move-to-number':
        controller.move_to_workspace_number(_create_group_context(args),
                                            args.workspace_relative_number,
                                            args.no_auto_back_and_forth)
    elif args.command == 'move-to-next':
        controller.move_workspace_relative(+1)
    elif args.command == 'move-to-prev':
        controller.move_workspace_relative(-1)
    elif args.command == 'move-to-new':
        controller.move_to_new_workspace(_create_group_context(args))
    elif args.command == 'switch-active-group':
        controller.switch_active_group(args.group, args.focused_monitor_only)
    elif args.command == 'rename-workspace':
        metadata_updates = workspace_names.WorkspaceGroupingMetadata(group=args.group,
                                                                     static_name=args.name,
                                                                     local_number=args.number)
        controller.update_focused_workspace(metadata_updates)
    elif args.command == 'assign-workspace-to-group':
        metadata_updates = workspace_names.WorkspaceGroupingMetadata(group=args.group)
        controller.update_focused_workspace(metadata_updates)
    elif args.command == 'server':
        serve(i3_connection, args.server_addr)
    # Deprecated commands, will be removed in a future release.
    elif args.command == 'workspace-back-and-forth':
        logger.warning('workspace-back-and-forth is deprecated, please '
                       'migrate to the native i3 "workspace back_and_forth" command')
        controller.i3_proxy.send_i3_command('workspace back_and_forth')
    elif args.command == 'move-to-back-and-forth':
        logger.warning('move-to-back-and-forth is deprecated, please '
                       'migrate to the native i3 "workspace back_and_forth" command')
        controller.i3_proxy.send_i3_command('move workspace back_and_forth')
    return ''


def main():
    try:
        args = _create_args_parser().parse_args()
    except cli_util.ExitCalledError as e:
        if e.message:
            sys.stderr.write(f'{e.message}\n')
        sys.exit(e.status)
    init_logger(os.path.basename(__file__))
    logger.setLevel(getattr(logging, args.log_level.upper(), 'WARNING'))
    i3_connection = i3ipc.Connection()
    try:
        output = run_command(i3_connection, args)
        if output:
            print(output)
    except i3_groups_controller.WorkspaceGroupsError as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
