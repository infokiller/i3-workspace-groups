#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import sys

import i3ipc

import i3_workspace_groups


def _create_args_parser():
    parser = argparse.ArgumentParser(description='Control i3 workspace groups.')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='If true, will not actually do any changes to i3 workspaces.')
    # The argparse argument group of the workspace group arguments.
    group_arg_group = parser.add_mutually_exclusive_group()
    group_arg_group.add_argument(
        '--group-active',
        action='store_true',
        default=None,
        help=
        'Use the active group for any commands that implicitly assume a group, '
        'such as workspace-next.')
    group_arg_group.add_argument(
        '--group-focused',
        action='store_true',
        default=None,
        help=
        'Use the focused group for any commands that implicitly assume a group, '
        'such as workspace-next.')
    group_arg_group.add_argument('--group-name')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True
    subparsers.add_parser(
        'list-groups', help='List the groups of the current workspaces.')
    subparsers.add_parser(
        'workspace-next',
        help='Focus on the next workspace in the focused group, similar to '
        'i3\'s "workspace next" command')
    subparsers.add_parser(
        'workspace-prev',
        help='Focus on the prev workspace in the focused group, similar to '
        'i3\'s "workspace prev" command')
    subparsers.add_parser(
        'move-to-next',
        help='Move the focused container to the prev workspace in the focused '
        'group, similar to i3\'s "move container to workspace next" command')
    subparsers.add_parser(
        'move-to-prev',
        help='Move the focused container to the prev workspace in the focused '
        'group, similar to i3\'s "move container to workspace prev" command')
    subparsers.add_parser(
        'workspace-number',
        help='Focus on the workspace with the provided number in the focused '
        'group, similar to i3\'s "workspace number" command').add_argument(
            'workspace_relative_number', type=int)
    subparsers.add_parser(
        'move-to-number',
        help='Move the focused container to the workspace with the provided '
        'number in the focused group, similar to i3\'s "move container to '
        'workspace" command').add_argument(
            'workspace_relative_number', type=int)
    subparsers.add_parser(
        'switch-active-group',
        help='Switches the active group to the one provided.').add_argument(
            'group')
    subparsers.add_parser(
        'assign-workspace-to-group',
        help='Assigns the focused workspace to the provided group.'
    ).add_argument('group')
    return parser


def _create_context_group_finder(args):
    if args.group_active:
        return i3_workspace_groups.ActiveGroupContext()
    elif args.group_focused:
        return i3_workspace_groups.FocusedGroupContext()
    elif args.group_name:
        return i3_workspace_groups.NamedGroupContext(args['group_name'])


def main():
    args = _create_args_parser().parse_args()
    group_context = _create_context_group_finder(args)
    controller = i3_workspace_groups.WorkspaceGroupsController(
        i3ipc.Connection(), group_context, args.dry_run)
    try:
        if args.command == 'list-groups':
            groups = controller.list_groups()
            print('\n'.join(groups))
        elif args.command == 'switch-active-group':
            controller.switch_active_group(args.group)
        elif args.command == 'assign-workspace-to-group':
            controller.move_workspace_to_group(args.group)
        elif args.command == 'workspace-number':
            controller.focus_workspace_number(args.workspace_relative_number)
        elif args.command == 'workspace-next':
            controller.focus_workspace_relative(+1)
        elif args.command == 'workspace-prev':
            controller.focus_workspace_relative(-1)
        elif args.command == 'move-to-number':
            controller.move_to_workspace_number(args.workspace_relative_number)
        elif args.command == 'move-to-next':
            controller.move_workspace_relative(+1)
        elif args.command == 'move-to-prev':
            controller.move_workspace_relative(-1)
    except i3_workspace_groups.WorkspaceGroupsError as e:
        sys.exit(e)


if __name__ == '__main__':
    main()
