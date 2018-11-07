#!/usr/bin/env python3
import collections
import logging
import logging.handlers
import os
import re
import sys

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
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_name>{}):(?P<local_number>\d+)$'
    .format(GROUP_NAME_PATTERN, WORKSPACE_LOCAL_NAME_PATTERN),
    # Non default group, group is inactive, no user configured name.
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_number>\d+)$'
    .format(GROUP_NAME_PATTERN),
    # Non default group, group is active, has user configured name.
    r'(?P<global_number>\d+):(?P<group>{}):(?P<local_name>{})$'.format(
        GROUP_NAME_PATTERN, WORKSPACE_LOCAL_NAME_PATTERN),
    # Non default group, group is active, no user configured name.
    r'(?P<global_number>\d+):(?P<group>{})$'.format(GROUP_NAME_PATTERN),
    # Default group, group is inactive, has user configured name.
    r'(?P<global_number>\d+):(?P<local_name>{}):(?P<local_number>\d+)$'
    .format(WORKSPACE_LOCAL_NAME_PATTERN),
    # Default group, group is inactive, no user configured name.
    r'(?P<global_number>\d+):(?P<local_number>\d+)$',
    # Default group, group is active, has user configured name.
    r'(?P<global_number>\d+):(?P<local_name>{})$'
    .format(WORKSPACE_LOCAL_NAME_PATTERN),
    # Default group, group is active, no user configured name.
    r'(?P<global_number>\d+)$',
]
WORKSPACE_NAME_REGEXES = [re.compile(regex) for regex in WORKSPACE_NAME_REGEXES]


def _init_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    stdout_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    syslog_handler.setFormatter(formatter)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    logger.addHandler(stdout_handler)
    logger.info('Starting script %s', __file__)
    return logger


_logger = _init_logger()


def sanitize_local_name(name):
    sanitized_name = name.replace(':', '%')
    assert re.match('^{}$'.format(WORKSPACE_LOCAL_NAME_PATTERN), sanitized_name)
    return sanitized_name


def parse_workspace_name(workspace_name):
    result = {
        'global_number': None,
        'group': DEFAULT_GROUP_NAME,
        'local_number': None,
        'local_name': None,
    }
    match = False
    for regex in WORKSPACE_NAME_REGEXES:
        m = regex.match(workspace_name)
        if m:
            result.update(m.groupdict())
            match = True
            break
    if not match:
        result['local_name'] = sanitize_local_name(workspace_name)
        return result
    for int_field in ['global_number', 'local_number']:
        if result[int_field]:
            result[int_field] = int(result[int_field])
    return result


def get_local_workspace_number(workspace):
    parsing_result = parse_workspace_name(workspace.name)
    local_number = parsing_result['local_number']
    if local_number is None and parsing_result['global_number'] is not None:
        local_number = global_number_to_local_number(
            parsing_result['global_number'])
    return local_number


def get_workspace_group(workspace):
    return parse_workspace_name(workspace.name)['group']


def max_local_workspace_number(workspaces):
    result = 0
    for workspace in workspaces:
        local_number = get_local_workspace_number(workspace)
        _logger.info('Workspace %s, local number %s', workspace.name,
                     local_number)
        if local_number is not None:
            result = max(result, local_number)
    return result


def create_workspace_name(global_number, group, local_name, local_number):
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


def compute_global_number(group_index, local_number):
    assert local_number < MAX_WORKSPACES_PER_GROUP
    return MAX_WORKSPACES_PER_GROUP * group_index + local_number


def global_number_to_group_index(global_number):
    return global_number // MAX_WORKSPACES_PER_GROUP


def global_number_to_local_number(global_number):
    return global_number % MAX_WORKSPACES_PER_GROUP


def get_group_to_workspaces(tree):
    group_to_workspaces = collections.OrderedDict()
    for workspace in tree.workspaces():
        parsed_name = parse_workspace_name(workspace.name)
        group = parsed_name['group']
        _logger.info('Workspace %s parsed as: %s', workspace.name, parsed_name)
        if group not in group_to_workspaces:
            group_to_workspaces[group] = []
        group_to_workspaces[group].append(workspace)
    return group_to_workspaces


class WorkspaceGroupsError(Exception):
    pass


class ActiveGroupContext(object):

    def get_group_name(self, tree):
        group_to_workspaces = get_group_to_workspaces(tree)
        # Return the first group which is defined as the active one.
        return next(iter(group_to_workspaces))

    def get_workspace(self, tree):
        active_group_name = self.get_group_name()
        focused_workspace = tree.find_focused().workspace()
        if get_workspace_group(focused_workspace) == active_group_name:
            return focused_workspace
        group_to_workspaces = get_group_to_workspaces(tree)
        active_group_workspaces = next(group_to_workspaces.items())[1]
        # Return the first group which is defined as the active one.
        return active_group_workspaces[0]


class FocusedGroupContext(object):

    def get_group_name(self, tree):
        focused_workspace = tree.find_focused().workspace()
        return get_workspace_group(focused_workspace)

    def get_workspace(self, tree):
        return tree.find_focused().workspace()


class NamedGroupContext(object):

    def __init__(self, group_name):
        self.group_name = group_name

    def get_group_name(self, tree):
        # Verify that the group exists
        group_to_workspaces = get_group_to_workspaces(tree)
        if self.group_name not in group_to_workspaces:
            raise WorkspaceGroupsError(
                'Unknown group \'{}\', known groups: {}'.format(
                    self.group_name, group_to_workspaces.keys()))
        return self.group_name

    def get_workspace(self, tree):
        group_to_workspaces = get_group_to_workspaces(tree)
        return group_to_workspace[self.group_name][0]


class WorkspaceGroupsController(object):

    def __init__(self, i3_connection, group_context, dry_run=True):
        self.i3_connection = i3_connection
        self.group_context = group_context
        self.dry_run = dry_run
        # i3 tree is cached for performance.
        self.tree = None

    def get_tree(self, cached=True):
        if self.tree and cached:
            return self.tree
        self.tree = self.i3_connection.get_tree()
        return self.tree

    def send_i3_command(self, command):
        if self.dry_run:
            log_prefix = '[dry-run] would send'
        else:
            log_prefix = 'Sending'
        _logger.info("%s i3 command: '[%s]'", log_prefix, command)
        if not self.dry_run:
            self.i3_connection.command(command)

    def organize_workspace_groups(self, groups_workspaces):
        for group_index, (group, workspaces) in enumerate(groups_workspaces):
            _logger.info('Organizing workspace group: %s', group)
            last_used_workspace_number = max_local_workspace_number(workspaces)
            local_numbers_used = set()
            for workspace in workspaces:
                parsed_name = parse_workspace_name(workspace.name)
                local_number = parsed_name['local_number']
                if local_number is None or (local_number in local_numbers_used):
                    local_number = last_used_workspace_number + 1
                    last_used_workspace_number += 1
                local_numbers_used.add(local_number)
                global_number = compute_global_number(group_index, local_number)
                new_name = create_workspace_name(global_number, group,
                                                 parsed_name['local_name'],
                                                 local_number)
                self.send_i3_command(u'rename workspace "{}" to "{}"'.format(
                    workspace.name, new_name))
                workspace.name = new_name

    def list_groups(self):
        # If no context group specified, list all groups.
        if not self.group_context:
            return get_group_to_workspaces(self.get_tree()).keys()
        return [self.group_context.get_group_name(self.get_tree())]

    def switch_active_group(self, target_group):
        group_to_workspaces = get_group_to_workspaces(self.get_tree())
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
        self.organize_workspace_groups(reordered_group_to_workspaces.items())
        focused_workspace = self.get_tree().find_focused().workspace()
        focused_group = get_workspace_group(focused_workspace)
        if focused_group != target_group:
            first_workspace_name = reordered_group_to_workspaces[target_group][
                0].name
            self.send_i3_command('workspace "{}"'.format(first_workspace_name))

    def move_workspace_to_group(self, target_group):
        if not re.match(GROUP_NAME_PATTERN, target_group):
            raise WorkspaceGroupsError(
                'Invalid group name provided: "{}". '
                'Group name must be in the form "{}"'.format(
                    target_group, GROUP_NAME_PATTERN))
        current_workspace = self.get_tree().find_focused().workspace()
        if get_workspace_group(current_workspace) == target_group:
            return
        new_group_to_workspaces = collections.OrderedDict()
        for group, workspaces in get_group_to_workspaces(
                self.get_tree()).items():
            new_workspaces = []
            for ws in workspaces:
                if ws.id != current_workspace.id:
                    new_workspaces.append(ws)
            if new_workspaces:
                new_group_to_workspaces[group] = new_workspaces
            else:
                _logger.info('No remaining workspaces in group %s', group)
        if target_group not in new_group_to_workspaces:
            new_group_to_workspaces[target_group] = []
        new_group_to_workspaces[target_group].append(current_workspace)
        self.organize_workspace_groups(new_group_to_workspaces.items())

    def _get_workspace_name_from_context(self, target_local_number):
        group_context = self.group_context or FocusedGroupContext()
        context_group = group_context.get_group_name(self.get_tree())
        _logger.info('Context group: "{}"'.format(context_group))
        group_to_workspaces = get_group_to_workspaces(self.get_tree())
        assert context_group in group_to_workspaces
        # Organize the workspaces so that we can make more assumptions about the
        # input. For example, we are guaranteed that we can generate a workspace
        # name from the local number and the group, and it will match an
        # existing workspace if and only if there's another workspace with that
        # local number in the group..
        self.organize_workspace_groups(group_to_workspaces.items())
        # If an existing workspace matches the requested target_local_number,
        # use it. Otherwise, create a new workspace name.
        for workspace in group_to_workspaces[context_group]:
            if get_local_workspace_number(workspace) == target_local_number:
                return workspace.name
        group_index = group_to_workspaces.keys().index(context_group)
        global_number = compute_global_number(group_index, target_local_number)
        return create_workspace_name(
            global_number,
            context_group,
            local_name=None,
            local_number=target_local_number)

    def focus_workspace_number(self, target_local_number):
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        _logger.info('Focusing on workspace: %s', target_workspace_name)
        self.send_i3_command('workspace "{}"'.format(target_workspace_name))

    def move_to_workspace_number(self, target_local_number):
        target_workspace_name = self._get_workspace_name_from_context(
            target_local_number)
        _logger.info('Moving  workspace: %s', target_workspace_name)
        self.send_i3_command(
            'move container to workspace "{}"'.format(target_workspace_name))

    def _relative_workspace_in_group(self, offset_from_current=1):
        group_context = self.group_context or FocusedGroupContext()
        group = group_context.get_group_name(self.get_tree())
        current_workspace = group_context.get_workspace(self.get_tree())
        _logger.info('Context group: "{}", workspace: "{}"'.format(
            group, current_workspace.name))
        group_workspaces = get_group_to_workspaces(self.get_tree())[group]
        for (i, workspace) in enumerate(group_workspaces):
            if workspace.id == current_workspace.id:
                break
        next_workspace_index = (i + offset_from_current) % len(group_workspaces)
        is_current_workspace = (next_workspace_index == i)
        return (group_workspaces[next_workspace_index], is_current_workspace)

    def focus_workspace_relative(self, offset_from_current):
        next_workspace, is_current_workspace = self._relative_workspace_in_group(
            offset_from_current)
        # Because of the `workspace_auto_back_and_forth` setting, we must not
        # execute the focus command if the target workspace is the same as the
        # current one, since then the focus will actually change to the
        # last focused workspace.
        if is_current_workspace:
            _logger.info(
                'Next workspace is the same as current one, not doing anything')
            return
        _logger.info('Focusing on workspace: %s', next_workspace.name)
        self.send_i3_command('workspace "{}"'.format(next_workspace.name))

    def move_workspace_relative(self, offset_from_current):
        next_workspace, is_current_workspace = self._relative_workspace_in_group(
            offset_from_current)
        # Because of the `workspace_auto_back_and_forth` setting, we must not
        # execute the move command if the target workspace is the same as the
        # current one, since then the container will actually move to the
        # last focused workspace.
        if is_current_workspace:
            _logger.info(
                'Next workspace is the same as current one, not doing anything')
            return
        _logger.info('Moving focused container to workspace: %s',
                     next_workspace.name)
        self.send_i3_command('move container to workspace "{}"'.format(
            next_workspace.name))
