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


def get_workspace_group(workspace: i3ipc.Con):
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
        parts.append(local_name)
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


def get_group_to_workspaces(
        workspaces: List[i3ipc.Con]) -> Dict[str, List[i3ipc.Con]]:
    group_to_workspaces = collections.OrderedDict()
    for workspace in workspaces:
        parsed_name = parse_workspace_name(workspace.name)
        group = parsed_name['group']
        logger.debug('Workspace %s parsed as: %s', workspace.name, parsed_name)
        if group not in group_to_workspaces:
            group_to_workspaces[group] = []
        group_to_workspaces[group].append(workspace)
    return group_to_workspaces


class WorkspaceGroupsError(Exception):
    pass


class ActiveGroupContext:

    @staticmethod
    def get_group_name(tree: i3ipc.Con) -> str:
        group_to_workspaces = get_group_to_workspaces(tree.workspaces())
        # Return the first group which is defined as the active one.
        return next(iter(group_to_workspaces))

    def get_workspace(self, tree: i3ipc.Con) -> i3ipc.Con:
        active_group_name = self.get_group_name(tree)
        focused_workspace = tree.find_focused().workspace()
        if get_workspace_group(focused_workspace) == active_group_name:
            return focused_workspace
        group_to_workspaces = get_group_to_workspaces(tree.workspaces())
        active_group_workspaces = next(group_to_workspaces.items())[1]
        # Return the first group which is defined as the active one.
        return active_group_workspaces[0]


class FocusedGroupContext:

    @staticmethod
    def get_group_name(tree: i3ipc.Con) -> str:
        focused_workspace = tree.find_focused().workspace()
        return get_workspace_group(focused_workspace)

    @staticmethod
    def get_workspace(tree: i3ipc.Con) -> i3ipc.Con:
        return tree.find_focused().workspace()


class NamedGroupContext:

    def __init__(self, group_name: str):
        self.group_name = group_name

    def get_group_name(self, tree: i3ipc.Con) -> str:
        # Verify that the group exists
        group_to_workspaces = get_group_to_workspaces(tree.workspaces())
        if self.group_name not in group_to_workspaces:
            raise WorkspaceGroupsError(
                'Unknown group \'{}\', known groups: {}'.format(
                    self.group_name, group_to_workspaces.keys()))
        return self.group_name

    def get_workspace(self, tree: i3ipc.Con) -> i3ipc.Con:
        group_to_workspaces = get_group_to_workspaces(tree.workspaces())
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

    def get_tree(self, cached: bool = True) -> i3ipc.Con:
        if self.tree and cached:
            return self.tree
        self.tree = self.i3_connection.get_tree()
        return self.tree

    def get_ordered_group_to_workspaces(self) -> Dict[str, List[i3ipc.Con]]:
        outputs = self.i3_connection.get_outputs()
        primary_outputs = [o['name'] for o in outputs if o['primary']]
        if len(primary_outputs) != 1:
            logger.warning('Detected multiple primary outputs: %s',
                           primary_outputs)
        primary_output = primary_outputs[0] if primary_outputs else None
        workspaces_metadata = self.i3_connection.get_workspaces()
        workspace_to_output = {}
        for workspace_metadata in workspaces_metadata:
            workspace_to_output[workspace_metadata.name] = (
                workspace_metadata.output)
        primary_output_workspaces = []
        other_workspaces = []
        for workspace in self.get_tree().workspaces():
            if workspace_to_output[workspace.name] == primary_output:
                primary_output_workspaces.append(workspace)
            else:
                other_workspaces.append(workspace)
        ordered_workspaces = primary_output_workspaces + other_workspaces
        return get_group_to_workspaces(ordered_workspaces)

    def send_i3_command(self, command: str) -> None:
        if self.dry_run:
            log_prefix = '[dry-run] would send'
        else:
            log_prefix = 'Sending'
        logger.info("%s i3 command: '[%s]'", log_prefix, command)
        if not self.dry_run:
            self.i3_connection.command(command)

    def organize_workspace_groups(
            self, group_to_workspaces: Dict[str, List[i3ipc.Con]]) -> None:
        for i, (group, workspaces) in enumerate(group_to_workspaces.items()):
            logger.debug('Organizing workspace group: %s', group)
            last_used_workspace_number = max_local_workspace_number(workspaces)
            local_numbers_used = set()
            for workspace in workspaces:
                parsed_name = parse_workspace_name(workspace.name)
                local_number = parsed_name['local_number']
                if local_number is None or (local_number in local_numbers_used):
                    local_number = last_used_workspace_number + 1
                    last_used_workspace_number += 1
                local_numbers_used.add(local_number)
                global_number = compute_global_number(
                    group_index=i, local_number=local_number)
                new_name = create_workspace_name(global_number, group,
                                                 parsed_name['local_name'],
                                                 local_number)
                self.send_i3_command(u'rename workspace "{}" to "{}"'.format(
                    workspace.name, new_name))
                workspace.name = new_name

    def list_groups(self) -> List[str]:
        # If no context group specified, list all groups.
        if not self.group_context:
            return self.get_ordered_group_to_workspaces().keys()
        return [self.group_context.get_group_name(self.get_tree())]

    def list_workspaces(self) -> List[str]:
        # If no context group specified, list all groups.
        if not self.group_context:
            return self.get_ordered_group_to_workspaces().keys()
        return [self.group_context.get_group_name(self.get_tree())]

    def switch_active_group(self, target_group: str) -> None:
        group_to_workspaces = self.get_ordered_group_to_workspaces()
        if target_group not in group_to_workspaces:
            raise WorkspaceGroupsError(
                'Unknown target group \'{}\', known groups: {}'.format(
                    target_group, group_to_workspaces.keys()))
        reordered_group_to_workspaces = collections.OrderedDict()
        reordered_group_to_workspaces[target_group] = group_to_workspaces[
            target_group]
        for group, workspaces in group_to_workspaces.items():
            if group == target_group:
                continue
            reordered_group_to_workspaces[group] = workspaces
        self.organize_workspace_groups(reordered_group_to_workspaces)
        focused_workspace = self.get_tree().find_focused().workspace()
        focused_group = get_workspace_group(focused_workspace)
        if focused_group != target_group:
            first_workspace_name = reordered_group_to_workspaces[target_group][
                0].name
            self.send_i3_command('workspace "{}"'.format(first_workspace_name))

    def move_workspace_to_group(self, target_group: str) -> None:
        if not re.match(GROUP_NAME_PATTERN, target_group):
            raise WorkspaceGroupsError(
                'Invalid group name provided: "{}". '
                'Group name must be in the form "{}"'.format(
                    target_group, GROUP_NAME_PATTERN))
        current_workspace = self.get_tree().find_focused().workspace()
        if get_workspace_group(current_workspace) == target_group:
            return
        new_group_to_workspaces = collections.OrderedDict()
        for group, workspaces in self.get_ordered_group_to_workspaces().items():
            new_workspaces = []
            for workspace in workspaces:
                if workspace.id != current_workspace.id:
                    new_workspaces.append(workspace)
            if new_workspaces:
                new_group_to_workspaces[group] = new_workspaces
            else:
                logger.debug('No remaining workspaces in group %s', group)
        if target_group not in new_group_to_workspaces:
            new_group_to_workspaces[target_group] = []
        new_group_to_workspaces[target_group].append(current_workspace)
        self.organize_workspace_groups(new_group_to_workspaces)

    def _get_workspace_name_from_context(self, target_local_number: int) -> str:
        group_context = self.group_context or FocusedGroupContext()
        context_group = group_context.get_group_name(self.get_tree())
        logger.info('Context group: "%s"', context_group)
        group_to_workspaces = self.get_ordered_group_to_workspaces()
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
        group = group_context.get_group_name(self.get_tree())
        current_workspace = group_context.get_workspace(self.get_tree())
        logger.info('Context group: "%s", workspace: "%s"', group,
                    current_workspace.name)
        group_workspaces = get_group_to_workspaces(
            self.get_tree().workspaces())[group]
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
