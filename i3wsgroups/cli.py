from __future__ import annotations

import argparse

from i3wsgroups import config


class ExitCalledError(Exception):

    def __init__(self, status: int, message: str):
        super().__init__(status, message)
        self.status = status
        self.message = message


# argparse calls sys.exit on errors, without even passing the error message to
# the exception. This wrapper class avoids this behavior. Python 3.9 has built
# in support for this behavior:
# https://docs.python.org/3/library/argparse.html#exit-on-error
# Additionally, we don't want the help flag to exit, so we handle that as well.
class ArgumentParserNoExit(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def exit(self, status=0, message=None):
        raise ExitCalledError(status, message)


def add_common_args(parser: argparse.ArgumentParser):
    parser.add_argument('--dry-run',
                        action='store_true',
                        default=False,
                        help='If true, only log what changed would be done.')
    parser.add_argument('--log-level',
                        choices=('debug', 'info', 'warning', 'error',
                                 'critical'),
                        default='warning',
                        help='Logging level for stderr and syslog.')


def add_workspace_naming_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '--window-icons',
        action='store_true',
        default=None,
        help='If true, add the icons of the open windows to the workspace '
        'names when organizing or renaming workspaces.')
    parser.add_argument(
        '--window-icons-all-groups',
        action='store_true',
        default=None,
        help='If true, add the icons of the open windows to workspaces in all '
        'groups, and not just the active group. Also implies --window-icons.')
    parser.add_argument(
        '--renumber-workspaces',
        action='store_true',
        default=None,
        help='If true, renumber workspaces in every group so that they are in '
        'numerical order, similar to tmux\'s renumber-windows option.')


def get_config_with_overrides(args: argparse.Namespace):
    config_dict = config.get_config_with_defaults()
    if args.renumber_workspaces is not None:
        config_dict['renumber_workspaces'] = args.renumber_workspaces
    if hasattr(args,
               'use_next_available_number') and args.use_next_available_number:
        config_dict['workspace_moves']['use_next_available_number'] = (
            args.use_next_available_number)
    if args.window_icons is not None:
        config_dict['icons']['enable'] = args.window_icons
    if args.window_icons_all_groups is not None:
        config_dict['icons']['enable_all_groups'] = args.window_icons_all_groups
    return config_dict
