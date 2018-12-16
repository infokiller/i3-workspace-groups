import argparse


def add_common_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='If true, will not actually do any changes to i3 workspaces.')
    parser.add_argument(
        '--log-level',
        choices=('debug', 'info', 'warning', 'error', 'critical'),
        default='warning',
        help='Logging level for stderr and syslog.')


def add_workspace_naming_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        '--window-icons-all-groups',
        action='store_true',
        default=False,
        help='If true, will add the icons of the open windows to workspaces'
        ' in all groups, and not just the active group. Also implies '
        '--window-icons.')
    parser.add_argument(
        '--renumber-workspaces',
        action='store_true',
        default=False,
        help='If true, will renumber workspaces in every groups so that they '
        'are in numerical order, similar to tmux\'s renumber-windows option.')
