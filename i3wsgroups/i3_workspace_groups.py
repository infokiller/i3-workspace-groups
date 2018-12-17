#!/usr/bin/env python3

import collections
import logging
import os
from typing import Dict, List, Optional

import i3ipc

from i3wsgroups import icons

WORKSPACE_NAME_SECTIONS = [
    'global_number',
    'group',
    'static_name',
    'dynamic_name',
    'local_number',
]
# Unicode zero width char.
SECTIONS_DELIM = '\u200b'

_LOG_FMT = '%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'

_MAX_WORKSPACES_PER_GROUP = 100

_SCRATCHPAD_WORKSPACE_NAME = '__i3_scratch'

_LAST_WORKSPACE_MARK = '_i3_groups_last_focused'

# We use the workspace names to "store" metadata about the workspace, such as
# the group it belongs to.
# Workspace name format:
#
# global_number:%%[group]%%[static_name]%%[dynamic_name]%%[local_number]
#
# Where:
# - %% represents a Unicode zero width space.
#   For info about zero width spaces see:
#   https://www.wikiwand.com/en/Zero-width_space
# - global_number is managed by this script and is required to order the
#   workspaces in i3 correctly, but can be hidden using i3 config.
# - static_name is an optional static local name of the workspace. It can be
#   changed by the user and will be maintained till the next time it's changed
#   or the workspace is closed.
# - dynamic_name is an optional dynamic local name of the workspace. If it's
#   enabled, it's managed by another script that dynamically populates it with
#   icons of the current windows in the workspace (implemented using unicode
#   glyhps).
#
# A colon is also used to separate the sections visually. Therefore, sections
# should not have colons at their beginning or end.
#
# Example of how workspace names are presented in i3bar:
#  "1"
#  "1:mail"
#  "1:mygroup:mail"
#  "102:mygroup:mail:2"

GroupToWorkspaces = Dict[str, List[i3ipc.Con]]

logger = logging.getLogger(__name__)


def init_logger(name: str) -> None:
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    stdout_handler = logging.StreamHandler()
    stdout_formatter = logging.Formatter(_LOG_FMT)
    stdout_handler.setFormatter(stdout_formatter)
    syslog_formatter = logging.Formatter('{}: {}'.format(name, _LOG_FMT))
    syslog_formatter.ident = name
    syslog_handler.setFormatter(syslog_formatter)
    logger.addHandler(syslog_handler)
    logger.addHandler(stdout_handler)


def maybe_remove_prefix_colons(section: str) -> str:
    if section and section[0] == ':':
        return section[1:]
    return section


def maybe_remove_suffix_colons(section: str) -> str:
    if section and section[-1] == ':':
        return section[:-1]
    return section


def sanitize_section_value(name: str) -> str:
    sanitized_name = name.replace(SECTIONS_DELIM, '%')
    assert SECTIONS_DELIM not in sanitized_name
    return maybe_remove_prefix_colons(sanitized_name)


def is_valid_group_name(name: str) -> str:
    return SECTIONS_DELIM not in name


def parse_global_number_section(
        global_number_section: Optional[str]) -> Optional[int]:
    if not global_number_section:
        return None
    return int(maybe_remove_suffix_colons(global_number_section))


def is_recognized_name_format(workspace_name: str) -> bool:
    sections = workspace_name.split(SECTIONS_DELIM)
    if len(sections) != len(WORKSPACE_NAME_SECTIONS):
        return False
    if sections[0]:
        try:
            parse_global_number_section(sections[0])
        except ValueError:
            return False
    return True


def parse_workspace_name(workspace_name: str) -> dict:
    result = {
        'global_number': None,
        'group': '',
        'static_name': '',
        'dynamic_name': '',
        'local_number': None,
    }
    if not is_recognized_name_format(workspace_name):
        result['static_name'] = sanitize_section_value(workspace_name)
        return result
    sections = workspace_name.split(SECTIONS_DELIM)
    result['global_number'] = parse_global_number_section(sections[0])
    if sections[1]:
        result['group'] = maybe_remove_suffix_colons(sections[1])
    result['static_name'] = maybe_remove_prefix_colons(sections[2])
    result['dynamic_name'] = maybe_remove_prefix_colons(sections[3])
    if not sections[4]:
        return result
    # Don't fail on local number parsing errors, just ignore it.
    try:
        result['local_number'] = int(maybe_remove_prefix_colons(sections[4]))
    except ValueError:
        pass
    return result


def get_local_workspace_number(workspace: i3ipc.Con) -> int:
    parsing_result = parse_workspace_name(workspace.name)
    local_number = parsing_result['local_number']
    if local_number is None and parsing_result['global_number'] is not None:
        local_number = global_number_to_local_number(
            parsing_result['global_number'])
    return local_number


def get_workspace_group(workspace: i3ipc.Con) -> str:
    return parse_workspace_name(workspace.name)['group']


def compute_local_numbers(monitor_workspaces: List[i3ipc.Con],
                          all_workspaces: List[i3ipc.Con],
                          renumber_workspaces: bool) -> List[int]:
    monitor_workspace_names = set()
    for workspace in monitor_workspaces:
        monitor_workspace_names.add(workspace.name)
    other_monitors_local_numbers = set()
    for workspace in all_workspaces:
        if workspace.name in monitor_workspace_names:
            continue
        local_number = parse_workspace_name(workspace.name)['local_number']
        if local_number is not None:
            other_monitors_local_numbers.add(local_number)
    logger.debug('Local numbers used by group in other monitors: %s',
                 other_monitors_local_numbers)
    local_numbers = []
    if renumber_workspaces:
        for local_number in range(1, 10**5):
            if len(local_numbers) == len(monitor_workspaces):
                break
            if local_number in other_monitors_local_numbers:
                continue
            local_numbers.append(local_number)
        assert len(local_numbers) == len(monitor_workspaces)
        return local_numbers
    if other_monitors_local_numbers:
        last_used_workspace_number = max(other_monitors_local_numbers)
    else:
        last_used_workspace_number = 0
    for workspace in monitor_workspaces:
        parsed_name = parse_workspace_name(workspace.name)
        local_number = parsed_name['local_number']
        if local_number is None or (
                local_number in other_monitors_local_numbers):
            local_number = last_used_workspace_number + 1
            last_used_workspace_number += 1
        local_numbers.append(local_number)
    return local_numbers


def create_workspace_name(
        global_number: int, group: str, static_name: Optional[str],
        dynamic_name: Optional[str], local_number: Optional[int]) -> str:
    sections = ['{}:'.format(global_number), group]
    need_prefix_colons = bool(group)
    for section in [static_name, dynamic_name, local_number]:
        if not section:
            section = ''
        elif need_prefix_colons:
            section = ':{}'.format(section)
        else:
            need_prefix_colons = True
        sections.append(str(section))
    return SECTIONS_DELIM.join(sections)


def compute_global_number(group_index: int, local_number: int) -> int:
    assert local_number < _MAX_WORKSPACES_PER_GROUP
    return _MAX_WORKSPACES_PER_GROUP * group_index + local_number


def global_number_to_group_index(global_number: int) -> int:
    return global_number // _MAX_WORKSPACES_PER_GROUP


def global_number_to_local_number(global_number: int) -> int:
    return global_number % _MAX_WORKSPACES_PER_GROUP


def get_group_to_workspaces(workspaces: List[i3ipc.Con]) -> GroupToWorkspaces:
    group_to_workspaces = collections.OrderedDict()
    for workspace in workspaces:
        parsed_name = parse_workspace_name(workspace.name)
        group = parsed_name['group']
        logger.debug('Workspace %s parsed as: %s', workspace.name, parsed_name)
        if group not in group_to_workspaces:
            group_to_workspaces[group] = []
        group_to_workspaces[group].append(workspace)
    return group_to_workspaces


def is_reordered_workspace(name1, name2):
    parsed_name1 = parse_workspace_name(name1)
    parsed_name2 = parse_workspace_name(name2)
    if parsed_name1['group'] != parsed_name2['group']:
        return False
    if parsed_name1['local_number']:
        return parsed_name1['local_number'] == parsed_name2['local_number']
    return parsed_name1['static_name'] == parsed_name2['static_name']


class WorkspaceGroupsError(Exception):
    pass


class ActiveGroupContext:

    def __init__(self, i3_connection: i3ipc.Connection):
        self.i3_connection = i3_connection

    @staticmethod
    def get_group_name(_: i3ipc.Con,
                       group_to_workspaces: GroupToWorkspaces) -> str:
        # Return the first group which is defined as the active one.
        return next(iter(group_to_workspaces))

    def get_workspace(self, tree: i3ipc.Con,
                      group_to_workspaces: GroupToWorkspaces) -> i3ipc.Con:
        active_group_name = self.get_group_name(tree, group_to_workspaces)
        focused_workspace = tree.find_focused().workspace()
        if get_workspace_group(focused_workspace) == active_group_name:
            return focused_workspace
        group_to_workspaces = get_group_to_workspaces(tree.workspaces())
        active_group_workspaces = next(iter(group_to_workspaces.items()))[1]
        # Return the first group which is defined as the active one.
        return active_group_workspaces[0]


class FocusedGroupContext:

    @staticmethod
    def get_group_name(tree: i3ipc.Con, _: GroupToWorkspaces) -> str:
        focused_workspace = tree.find_focused().workspace()
        return get_workspace_group(focused_workspace)

    @staticmethod
    def get_workspace(tree: i3ipc.Con, _: GroupToWorkspaces) -> i3ipc.Con:
        return tree.find_focused().workspace()


class NamedGroupContext:

    def __init__(self, group_name: str):
        self.group_name = group_name

    def get_group_name(self, _: i3ipc.Con,
                       group_to_workspaces: GroupToWorkspaces) -> str:
        if self.group_name not in group_to_workspaces:
            raise WorkspaceGroupsError(
                'Unknown group \'{}\', known groups: {}'.format(
                    self.group_name, group_to_workspaces.keys()))
        return self.group_name

    def get_workspace(self, _: i3ipc.Con,
                      group_to_workspaces: GroupToWorkspaces) -> i3ipc.Con:
        return group_to_workspaces[self.group_name][0]


class WorkspaceGroupsController:

    def __init__(self,
                 i3_connection: i3ipc.Connection,
                 group_context,
                 add_window_icons: bool = False,
                 add_window_icons_all_groups: bool = False,
                 renumber_workspaces: bool = False,
                 dry_run: bool = True):
        self.i3_connection = i3_connection
        self.group_context = group_context
        self.add_window_icons = add_window_icons
        self.add_window_icons_all_groups = add_window_icons_all_groups
        self.renumber_workspaces = renumber_workspaces
        self.group_context = group_context
        self.dry_run = dry_run
        # i3 tree is cached for performance. Timing the i3ipc get_tree function
        # using `%timeit` in ipython shows about 1-2ms in my high performance
        # desktop. For lower performance machines, multiple calls to get_tree
        # may be noticable, so this is cached.
        # Other operations like get_workspaces and get_outputs were about 50µs
        # using the same method, which is more negligible.
        self.tree = None
        self.workspaces_metadata = None

    def get_tree(self, cached: bool = True) -> i3ipc.Con:
        if self.tree and cached:
            return self.tree
        self.tree = self.i3_connection.get_tree()
        return self.tree

    def get_workspaces_metadata(
            self, cached: bool = True) -> List[i3ipc.WorkspaceReply]:
        if self.workspaces_metadata and cached:
            return self.workspaces_metadata
        self.workspaces_metadata = self.i3_connection.get_workspaces()
        return self.workspaces_metadata

    def _get_focused_monitor_name(self):
        focused_outputs = set()
        for workspace_metadata in self.get_workspaces_metadata():
            if workspace_metadata.focused:
                focused_outputs.add(workspace_metadata.output)
        if not focused_outputs:
            raise WorkspaceGroupsError('No focused workspaces')
        if len(focused_outputs) > 1:
            logger.warning('Focused workspaces detected in multiple outputs')
        logger.debug('Focused outputs: %s', focused_outputs)
        return next(iter(focused_outputs))

    def get_monitor_workspaces(
            self, monitor_name: Optional[str] = None) -> List[i3ipc.Con]:
        if not monitor_name:
            monitor_name = self._get_focused_monitor_name()
        return self._get_monitor_to_workspaces()[monitor_name]

    def _get_monitor_to_workspaces(self) -> Dict[str, List[i3ipc.Con]]:
        name_to_workspace = {}
        for workspace in self.get_tree().workspaces():
            name_to_workspace[workspace.name] = workspace
        monitor_to_workspaces = collections.defaultdict(list)
        for workspace_metadata in self.get_workspaces_metadata():
            if workspace_metadata.name == _SCRATCHPAD_WORKSPACE_NAME:
                continue
            if workspace_metadata.name not in name_to_workspace:
                logger.warning('Unknown workspace detected: %s',
                               workspace_metadata.name)
            workspace = name_to_workspace[workspace_metadata.name]
            monitor_to_workspaces[workspace_metadata.output].append(workspace)
        return monitor_to_workspaces

    def send_i3_command(self, command: str) -> None:
        if self.dry_run:
            log_prefix = '[dry-run] would send'
        else:
            log_prefix = 'Sending'
        logger.info("%s i3 command: '%s'", log_prefix, command)
        if not self.dry_run:
            reply = self.i3_connection.command(command)
            if not reply[0]['success']:
                logger.warning('i3 command error: %s', reply)

    def focus_workspace(self, name: str) -> None:
        focused_workspace = self.get_tree().find_focused().workspace()
        self.send_i3_command('[con_id={}] mark "{}"'.format(
            focused_workspace.id, _LAST_WORKSPACE_MARK))
        self.send_i3_command(
            'workspace --no-auto-back-and-forth  "{}"'.format(name))

    def get_last_focused_workspace(self) -> Optional[i3ipc.Con]:
        last_workspaces = self.get_tree().find_marked(_LAST_WORKSPACE_MARK)
        if not last_workspaces:
            logger.warning('Could not get last workspace from mark')
            self.send_i3_command('workspace back_and_forth')
            return None
        if len(last_workspaces) > 1:
            logger.warning('Multiple workspaces marked as the last one, using'
                           'first one')
        return last_workspaces[0]

    def organize_workspace_groups(
            self, group_to_monitor_workspaces: GroupToWorkspaces) -> None:
        group_to_all_workspaces = get_group_to_workspaces(
            self.get_tree().workspaces())
        for group_index, (group, workspaces) in enumerate(
                group_to_monitor_workspaces.items()):
            logger.debug('Organizing workspace group: %s', group)
            local_numbers = compute_local_numbers(
                workspaces, group_to_all_workspaces.get(group, []),
                self.renumber_workspaces)
            for workspace, local_number in zip(workspaces, local_numbers):
                parsed_name = parse_workspace_name(workspace.name)
                parsed_name['group'] = group
                parsed_name['local_number'] = local_number
                parsed_name['global_number'] = compute_global_number(
                    group_index, local_number)
                dynamic_name = ''
                # Add window icons to the active group if needed.
                if self.add_window_icons_all_groups or (self.add_window_icons
                                                        and group_index == 0):
                    dynamic_name = icons.get_workspace_icons_representation(
                        workspace)
                parsed_name['dynamic_name'] = dynamic_name
                new_name = create_workspace_name(**parsed_name)
                self.send_i3_command('rename workspace "{}" to "{}"'.format(
                    workspace.name, new_name))
                workspace.name = new_name

    def list_groups(self) -> List[str]:
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        # If no context group specified, list all groups.
        if not self.group_context:
            return list(group_to_workspaces.keys())
        return [
            self.group_context.get_group_name(self.get_tree(),
                                              group_to_workspaces)
        ]

    def list_workspaces(self, focused_only: bool = False) -> List[i3ipc.Con]:
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        # If no context group specified, return workspaces from all groups.
        if not self.group_context:
            group_workspaces = sum(
                (list(workspaces)
                 for workspaces in group_to_workspaces.values()), [])
        else:
            group_name = self.group_context.get_group_name(
                self.get_tree(), group_to_workspaces)
            group_workspaces = group_to_workspaces[group_name]
        if not focused_only:
            return group_workspaces
        focused_workspace = self.get_tree().find_focused().workspace()
        return [ws for ws in group_workspaces if ws.id == focused_workspace.id]

    # pylint: disable=too-many-locals
    def switch_monitor_active_group(self,
                                    group_to_workspaces: GroupToWorkspaces,
                                    target_group: str) -> None:
        # Store the name of the originally focused workspace which is needed if
        # the group is new (see below).
        focused_workspace = self.get_tree().find_focused().workspace()
        is_group_new = False
        if target_group not in group_to_workspaces:
            is_group_new = True
            logger.debug(
                'Requested active group doesn\'t exist, will create it.')
            max_global_number = 0
            for workspaces in group_to_workspaces.values():
                for workspace in workspaces:
                    global_number = parse_workspace_name(
                        workspace.name)['global_number']
                    if global_number:
                        max_global_number = max(max_global_number,
                                                global_number)
            new_workspace_name = create_workspace_name(
                max_global_number + 1,
                target_group,
                static_name=None,
                dynamic_name=None,
                local_number=1)
            self.send_i3_command('workspace "{}"'.format(new_workspace_name))
            for workspace in self.get_tree(cached=False):
                if workspace.name == new_workspace_name:
                    group_to_workspaces[target_group] = [workspace]
                    break
        reordered_group_to_workspaces = collections.OrderedDict()
        reordered_group_to_workspaces[target_group] = group_to_workspaces[
            target_group]
        for group, workspaces in group_to_workspaces.items():
            if group == target_group:
                continue
            reordered_group_to_workspaces[group] = workspaces
        self.organize_workspace_groups(reordered_group_to_workspaces)
        # Switch to the originally focused workspace that may have a new name
        # following the workspace organization. Without doing this, if the user
        # switches to the previously focused workspace ("workspace
        # back_and_forth" command), i3 will switch to the previous name of the
        # originally focused workspace, which will create a new empty workspace.
        focused_group = get_workspace_group(focused_workspace)
        if is_group_new:
            matching_workspaces = []
            for workspace in reordered_group_to_workspaces[focused_group]:
                if is_reordered_workspace(focused_workspace.name,
                                          workspace.name):
                    matching_workspaces.append(workspace)
            assert len(matching_workspaces) == 1
            self.send_i3_command('workspace "{}"'.format(
                matching_workspaces[0].name))
        if focused_group != target_group:
            first_workspace_name = reordered_group_to_workspaces[target_group][
                0].name
            self.send_i3_command('workspace "{}"'.format(first_workspace_name))

    def switch_active_group(self, target_group: str,
                            focused_monitor_only: bool) -> None:
        monitor_to_workspaces = self._get_monitor_to_workspaces()
        focused_monitor_name = self._get_focused_monitor_name()
        self.switch_monitor_active_group(
            get_group_to_workspaces(
                monitor_to_workspaces[focused_monitor_name]), target_group)
        if focused_monitor_only:
            return
        for monitor, workspaces in monitor_to_workspaces.items():
            if monitor == focused_monitor_name:
                continue
            group_to_workspaces = get_group_to_workspaces(workspaces)
            if target_group not in group_to_workspaces:
                continue
            logger.debug(
                'Non focused monitor %s has workspaces in the group "%s", '
                'switching to it.', monitor, target_group)
            self.switch_monitor_active_group(
                get_group_to_workspaces(workspaces), target_group)

    def assign_workspace_to_group(self, target_group: str) -> None:
        if not is_valid_group_name(target_group):
            raise WorkspaceGroupsError(
                'Invalid group name provided: "{}"'.format(target_group))
        focused_workspace = self.get_tree().find_focused().workspace()
        if get_workspace_group(focused_workspace) == target_group:
            return
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        for workspaces in group_to_workspaces.values():
            for to_remove in (
                    ws for ws in workspaces if ws.id == focused_workspace.id):
                workspaces.remove(to_remove)
        if target_group not in group_to_workspaces:
            group_to_workspaces[target_group] = []
        group_to_workspaces[target_group].append(focused_workspace)
        self.organize_workspace_groups(group_to_workspaces)

    def _get_workspace_name_from_context(self, target_local_number: int) -> str:
        group_context = self.group_context or ActiveGroupContext(
            self.i3_connection)
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        context_group = group_context.get_group_name(self.get_tree(),
                                                     group_to_workspaces)
        logger.info('Context group: "%s"', context_group)
        assert context_group in group_to_workspaces
        # Organize the workspaces so that we can make more assumptions about the
        # input. For example, we are guaranteed that we can generate a workspace
        # name from the local number and the group, and it will match an
        # existing workspace if and only if there's another workspace with that
        # local number in the group..
        self.organize_workspace_groups(group_to_workspaces)
        # If an existing workspace matches the requested target_local_number,
        # use it. Otherwise, create a new workspace name.
        for workspace in group_to_workspaces[context_group]:
            if get_local_workspace_number(workspace) == target_local_number:
                return workspace.name
        group_index = list(group_to_workspaces.keys()).index(context_group)
        global_number = compute_global_number(group_index, target_local_number)
        return create_workspace_name(
            global_number,
            context_group,
            static_name='',
            dynamic_name='',
            local_number=target_local_number)

    def focus_workspace_number(self, target_local_number: int) -> None:
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        self.focus_workspace(target_workspace_name)

    def move_to_workspace_number(self, target_local_number: int) -> None:
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        self.send_i3_command(
            'move container to workspace "{}"'.format(target_workspace_name))

    def _relative_workspace_in_group(self,
                                     offset_from_current: int = 1) -> i3ipc.Con:
        group_context = self.group_context or ActiveGroupContext(
            self.i3_connection)
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        group = group_context.get_group_name(self.get_tree(),
                                             group_to_workspaces)
        current_workspace = group_context.get_workspace(self.get_tree(),
                                                        group_to_workspaces)
        logger.info('Context group: "%s", workspace: "%s"', group,
                    current_workspace.name)
        group_workspaces = group_to_workspaces[group]
        current_workspace_index = 0
        for (current_workspace_index, workspace) in enumerate(group_workspaces):
            if workspace.id == current_workspace.id:
                break
        next_workspace_index = (current_workspace_index +
                                offset_from_current) % len(group_workspaces)
        return group_workspaces[next_workspace_index]

    def focus_workspace_relative(self, offset_from_current: int) -> None:
        next_workspace = self._relative_workspace_in_group(offset_from_current)
        self.focus_workspace(next_workspace.name)

    def focus_workspace_back_and_forth(self) -> None:
        last_workspace = self.get_last_focused_workspace()
        if not last_workspace:
            logger.warning('Falling back to i3\'s built in workspace '
                           'back_and_forth')
            self.send_i3_command('workspace back_and_forth')
            return
        self.focus_workspace(last_workspace.name)

    def move_workspace_relative(self, offset_from_current: int) -> None:
        next_workspace = self._relative_workspace_in_group(offset_from_current)
        self.send_i3_command(
            'move --no-auto-back-and-forth container to workspace "{}"'.format(
                next_workspace.name))

    def move_workspace_back_and_forth(self) -> None:
        last_workspace = self.get_last_focused_workspace()
        if not last_workspace:
            logger.warning('Falling back to i3\'s built in move workspace '
                           'back_and_forth')
            self.send_i3_command('move workspace back_and_forth')
            return
        self.send_i3_command(
            'move --no-auto-back-and-forth container to workspace "{}"'.format(
                last_workspace.name))

    def rename_focused_workspace(self, new_static_name: Optional[str]) -> None:
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        # Organize the workspace groups to ensure they are consistent and every
        # workspace has a global number.
        self.organize_workspace_groups(group_to_workspaces)
        focused_workspace = self.get_tree().find_focused().workspace()
        parsed_name = parse_workspace_name(focused_workspace.name)
        parsed_name['static_name'] = new_static_name
        new_global_name = create_workspace_name(**parsed_name)
        self.send_i3_command('rename workspace "{}" to "{}"'.format(
            focused_workspace.name, new_global_name))
