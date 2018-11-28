#!/usr/bin/env python3

from typing import List, Dict, Optional
import collections
import logging
import re

import i3ipc

logger = logging.getLogger(__name__)

DEFAULT_GROUP_NAME = 'Ɗ'
GROUP_NAME_PATTERN = r'[^:\d][^:]*'
WORKSPACE_LOCAL_NAME_PATTERN = r'[^:]+'

MAX_WORKSPACES_PER_GROUP = 100

# We use the workspace names to "store" metadata about the workspace, such as
# the group it belongs to. Example workspace names (without quotes):
#  "1"
#  "1:mail"
#  "1:mygroup:mail"
#  "102:mygroup:mail:2"
# This is a list of regexes with capture groups that define how we encode and
# decode the metadata from the workspace names.
WORKSPACE_NAME_REGEXES = [
    # Non default group, group is inactive, has user configured name.
    # pylint: disable=line-too-long
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_name>{}):(?P<local_number>\d+)$'
    .format(GROUP_NAME_PATTERN, WORKSPACE_LOCAL_NAME_PATTERN),
    # Non default group, group is inactive, no user configured name.
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_number>\d+)$'.format(
        GROUP_NAME_PATTERN),
    # Non default group, group is active, has user configured name.
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_name>{})$'.format(
        GROUP_NAME_PATTERN, WORKSPACE_LOCAL_NAME_PATTERN),
    # Non default group, group is active, no user configured name.
    r'(?P<global_number>\d+):(?P<group>{})$'.format(GROUP_NAME_PATTERN),
    # Default group, group is inactive, has user configured name.
    r'(?P<global_number>\d+):(?P<local_name>{}):(?P<local_number>\d+)$'.format(
        WORKSPACE_LOCAL_NAME_PATTERN),
    # Default group, group is inactive, no user configured name.
    r'(?P<global_number>\d+):(?P<local_number>\d+)$',
    # Default group, group is active, has user configured name.
    r'(?P<global_number>\d+):(?P<local_name>{})$'.format(
        WORKSPACE_LOCAL_NAME_PATTERN),
    # Default group, group is active, no user configured name.
    r'(?P<global_number>\d+)$',
]
WORKSPACE_NAME_REGEXES = [re.compile(regex) for regex in WORKSPACE_NAME_REGEXES]

GroupToWorkspaces = Dict[str, List[i3ipc.Con]]


def sanitize_local_name(name: str) -> str:
    sanitized_name = name.replace(':', '%')
    assert re.match('^{}$'.format(WORKSPACE_LOCAL_NAME_PATTERN), sanitized_name)
    return sanitized_name


def parse_workspace_name(workspace_name: str) -> dict:
    result = {
        'global_number': None,
        'group': DEFAULT_GROUP_NAME,
        'local_number': None,
        'local_name': None,
    }
    match = False
    for regex in WORKSPACE_NAME_REGEXES:
        match = regex.match(workspace_name)
        if match:
            result.update(match.groupdict())
            match = True
            break
    if not match:
        result['local_name'] = sanitize_local_name(workspace_name)
        return result
    for int_field in ['global_number', 'local_number']:
        if result[int_field]:
            result[int_field] = int(result[int_field])
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


def max_local_workspace_number(workspaces: List[i3ipc.Con]):
    result = 0
    for workspace in workspaces:
        local_number = get_local_workspace_number(workspace)
        logger.debug('Workspace %s, local number %s', workspace.name,
                     local_number)
        if local_number is not None:
            result = max(result, local_number)
    return result


def create_workspace_name(global_number: int, group: str,
                          local_name: Optional[str],
                          local_number: Optional[int]) -> str:
    parts = [global_number]
    # If a workspace in the default group has a local name, we have to add the
    # group name, or otherwise it could be recognized as a workspace in another
    # group.
    # For example, let's assume there are two workspaces named "1:1" and
    # "2:ws". Is the second one in the group "ws" with no local name, or in the
    # default group with the local name "ws"?
    if group != DEFAULT_GROUP_NAME or local_name:
        parts.append(group)
    if local_name:
        parts.append(sanitize_local_name(local_name))
    if local_number is not None:
        parts.append(local_number)
    return ':'.join(str(p) for p in parts)


def compute_global_number(group_index: int, local_number: int) -> int:
    assert local_number < MAX_WORKSPACES_PER_GROUP
    return MAX_WORKSPACES_PER_GROUP * group_index + local_number


def global_number_to_group_index(global_number: int) -> int:
    return global_number // MAX_WORKSPACES_PER_GROUP


def global_number_to_local_number(global_number: int) -> int:
    return global_number % MAX_WORKSPACES_PER_GROUP


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
    return parsed_name1['local_name'] == parsed_name2['local_name']


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
                 dry_run: bool = True):
        self.i3_connection = i3_connection
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

    def _get_monitor_workspaces(
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

    def organize_workspace_groups(
            self, group_to_monitor_workspaces: GroupToWorkspaces) -> None:
        group_to_all_workspaces = get_group_to_workspaces(
            self.get_tree().workspaces())
        monitor_workspace_names = set()
        for workspaces in group_to_monitor_workspaces.values():
            for workspace in workspaces:
                monitor_workspace_names.add(workspace.name)
        for group_index, (group, workspaces) in enumerate(
                group_to_monitor_workspaces.items()):
            logger.debug('Organizing workspace group: %s', group)
            all_group_workspaces = group_to_all_workspaces.get(group, [])
            last_used_workspace_number = max_local_workspace_number(
                all_group_workspaces)
            local_numbers_used = set()
            for workspace in all_group_workspaces:
                if workspace.name in monitor_workspace_names:
                    continue
                local_number = parse_workspace_name(
                    workspace.name)['local_number']
                if local_number is not None:
                    local_numbers_used.add(local_number)
            for workspace in workspaces:
                parsed_name = parse_workspace_name(workspace.name)
                parsed_name['group'] = group
                local_number = parsed_name['local_number']
                if local_number is None or (local_number in local_numbers_used):
                    local_number = last_used_workspace_number + 1
                    parsed_name['local_number'] = local_number
                    last_used_workspace_number += 1
                local_numbers_used.add(local_number)
                parsed_name['global_number'] = compute_global_number(
                    group_index, local_number)
                new_name = create_workspace_name(**parsed_name)
                self.send_i3_command('rename workspace "{}" to "{}"'.format(
                    workspace.name, new_name))
                workspace.name = new_name

    def list_groups(self) -> List[str]:
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
        # If no context group specified, list all groups.
        if not self.group_context:
            return list(group_to_workspaces.keys())
        return [
            self.group_context.get_group_name(self.get_tree(),
                                              group_to_workspaces)
        ]

    def list_workspaces(self, focused_only: bool = False) -> List[i3ipc.Con]:
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
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
                local_name=None,
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
        if not re.match(GROUP_NAME_PATTERN, target_group):
            raise WorkspaceGroupsError(
                'Invalid group name provided: "{}". '
                'Group name must be in the form "{}"'.format(
                    target_group, GROUP_NAME_PATTERN))
        focused_workspace = self.get_tree().find_focused().workspace()
        if get_workspace_group(focused_workspace) == target_group:
            return
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
        for workspaces in group_to_workspaces.values():
            for to_remove in (
                    ws for ws in workspaces if ws.id == focused_workspace.id):
                workspaces.remove(to_remove)
        if target_group not in group_to_workspaces:
            group_to_workspaces[target_group] = []
        group_to_workspaces[target_group].append(focused_workspace)
        self.organize_workspace_groups(group_to_workspaces)

    def _get_workspace_name_from_context(self, target_local_number: int) -> str:
        group_context = self.group_context or FocusedGroupContext()
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
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
            local_name='',
            local_number=target_local_number)

    def focus_workspace_number(self, target_local_number: int) -> None:
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        self.send_i3_command('workspace "{}"'.format(target_workspace_name))

    def move_to_workspace_number(self, target_local_number: int) -> None:
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        self.send_i3_command(
            'move container to workspace "{}"'.format(target_workspace_name))

    def _relative_workspace_in_group(self,
                                     offset_from_current: int = 1) -> i3ipc.Con:
        group_context = self.group_context or FocusedGroupContext()
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
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
        self.send_i3_command('workspace --no-auto-back-and-forth "{}"'.format(
            next_workspace.name))

    def move_workspace_relative(self, offset_from_current: int) -> None:
        next_workspace = self._relative_workspace_in_group(offset_from_current)
        self.send_i3_command(
            'move --no-auto-back-and-forth container to workspace "{}"'.format(
                next_workspace.name))

    def rename_workspace(self, new_local_name: Optional[str]) -> None:
        group_to_workspaces = get_group_to_workspaces(
            self._get_monitor_workspaces())
        # Organize the workspace groups to ensure they are consistent and every
        # workspace has a global number.
        self.organize_workspace_groups(group_to_workspaces)
        focused_workspace = self.get_tree().find_focused().workspace()
        parsed_name = parse_workspace_name(focused_workspace.name)
        parsed_name['local_name'] = new_local_name
        new_global_name = create_workspace_name(**parsed_name)
        self.send_i3_command('rename workspace "{}" to "{}"'.format(
            focused_workspace.name, new_global_name))
