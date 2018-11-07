#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import sys

import i3ipc

import i3_workspace_groups


def _create_args_parser():
    parser = argparse.ArgumentParser(description='Control i3 workspace groups.')
    parser.add_argument('--dry-run', action='store_true', default=False)
    # The argparse argument group of the workspace group arguments.
    group_arg_group = parser.add_mutually_exclusive_group()
    group_arg_group.add_argument(
        '--group-active', action='store_true', default=None)
    group_arg_group.add_argument(
        '--group-focused', action='store_true', default=None)
    group_arg_group.add_argument('--group-name')
    subparsers = parser.add_subparsers(dest='subparser_name')
    subparsers.add_parser('list-groups')
    subparsers.add_parser('workspace-next')
    subparsers.add_parser('workspace-prev')
    subparsers.add_parser('move-to-next')
    subparsers.add_parser('move-to-prev')
    subparsers.add_parser('workspace-number').add_argument(
        'workspace_relative_number', type=int)
    subparsers.add_parser('move-to-number').add_argument(
        'workspace_relative_number', type=int)
    subparsers.add_parser('switch-active-group').add_argument('group')
    subparsers.add_parser('move-workspace-to-group').add_argument('group')
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
        if args.subparser_name == 'list-groups':
            groups = controller.list_groups()
            print('\n'.join(groups))
        elif args.subparser_name == 'switch-active-group':
            controller.switch_active_group(args.group)
        elif args.subparser_name == 'move-workspace-to-group':
            controller.move_workspace_to_group(args.group)
        elif args.subparser_name == 'workspace-number':
            controller.focus_workspace_number(args.workspace_relative_number)
        elif args.subparser_name == 'workspace-next':
            controller.focus_workspace_relative(+1)
        elif args.subparser_name == 'workspace-prev':
            controller.focus_workspace_relative(-1)
        elif args.subparser_name == 'move-to-number':
            controller.move_to_workspace_number(args.workspace_relative_number)
        elif args.subparser_name == 'move-to-next':
            controller.move_workspace_relative(+1)
        elif args.subparser_name == 'move-to-prev':
            controller.move_workspace_relative(-1)
    except i3_workspace_groups.WorkspaceGroupsError as e:
        sys.exit(e)


if __name__ == '__main__':
    main()
