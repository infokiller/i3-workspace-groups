#!/usr/bin/env python3

import collections
import logging
import logging.handlers
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

LAST_WORKSPACE_MARK = '_i3_groups_last_focused'
# We need to keep this as well so that we can set the last workspace when
# subscribing to the workspace focus event of i3, which only triggers after the
# workspace was focused.
CURRENT_WORKSPACE_MARK = '_i3_groups_current_focused'

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


# pylint: disable=too-few-public-methods
class WorkspaceDisplayMetadata:

    def __init__(self, workspace_name: str, monitor_name: str,
                 is_focused: bool):
        self.workspace_name: str = workspace_name
        self.monitor_name: str = monitor_name
        self.is_focused: bool = is_focused

    def __str__(self):
        return str(self.__dict__)


# pylint: disable=too-few-public-methods
class WorkspaceGroupingMetadata:

    # pylint: disable=too-many-arguments
    def __init__(self,
                 global_number: Optional[int] = None,
                 group: str = '',
                 static_name: str = '',
                 dynamic_name: str = '',
                 local_number: Optional[int] = None):
        self.global_number: Optional[int] = global_number
        self.group: str = group
        self.static_name: str = static_name
        self.dynamic_name: str = dynamic_name
        self.local_number: Optional[int] = local_number

    def __str__(self):
        return str(self.__dict__)


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


def is_valid_group_name(name: str) -> bool:
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


def parse_workspace_name(workspace_name: str) -> WorkspaceGroupingMetadata:
    result = WorkspaceGroupingMetadata()
    if not is_recognized_name_format(workspace_name):
        result.static_name = sanitize_section_value(workspace_name)
        return result
    sections = workspace_name.split(SECTIONS_DELIM)
    result.global_number = parse_global_number_section(sections[0])
    if sections[1]:
        result.group = maybe_remove_suffix_colons(sections[1])
    result.static_name = maybe_remove_prefix_colons(sections[2])
    result.dynamic_name = maybe_remove_prefix_colons(sections[3])
    if not sections[4]:
        return result
    # Don't fail on local number parsing errors, just ignore it.
    try:
        result.local_number = int(maybe_remove_prefix_colons(sections[4]))
    except ValueError:
        pass
    return result


def get_local_workspace_number(workspace: i3ipc.Con) -> Optional[int]:
    ws_metadata = parse_workspace_name(workspace.name)
    local_number = ws_metadata.local_number
    if local_number is None and ws_metadata.global_number is not None:
        local_number = global_number_to_local_number(ws_metadata.global_number)
    return local_number


def get_workspace_group(workspace: i3ipc.Con) -> str:
    return parse_workspace_name(workspace.name).group


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
        local_number = parse_workspace_name(workspace.name).local_number
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
        ws_metadata = parse_workspace_name(workspace.name)
        local_number = ws_metadata.local_number
        if local_number is None or (
                local_number in other_monitors_local_numbers):
            local_number = last_used_workspace_number + 1
            last_used_workspace_number += 1
        local_numbers.append(local_number)
    return local_numbers


def create_workspace_name(ws_metadata: WorkspaceGroupingMetadata) -> str:
    sections = ['{}:'.format(ws_metadata.global_number), ws_metadata.group]
    need_prefix_colons = bool(ws_metadata.group)
    for section in ['static_name', 'dynamic_name', 'local_number']:
        value = getattr(ws_metadata, section)
        if not value:
            value = ''
        elif need_prefix_colons:
            value = ':{}'.format(value)
        else:
            need_prefix_colons = True
        sections.append(str(value))
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
        ws_metadata = parse_workspace_name(workspace.name)
        group = ws_metadata.group
        logger.debug('Workspace %s parsed as: %s', workspace.name, ws_metadata)
        if group not in group_to_workspaces:
            group_to_workspaces[group] = []
        group_to_workspaces[group].append(workspace)
    return group_to_workspaces


def is_reordered_workspace(name1, name2):
    ws1_metadata = parse_workspace_name(name1)
    ws2_metadata = parse_workspace_name(name2)
    if ws1_metadata.group != ws2_metadata.group:
        return False
    if ws1_metadata.local_number:
        return ws1_metadata.local_number == ws2_metadata.local_number
    return ws1_metadata.static_name == ws2_metadata.static_name


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


# pylint: disable=too-many-instance-attributes
class WorkspaceGroupsController:

    # pylint: disable=too-many-arguments
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

    def get_workspaces_display_metadata(
            self, cached: bool = True) -> List[i3ipc.WorkspaceReply]:
        if self.workspaces_metadata and cached:
            return self.workspaces_metadata
        self.workspaces_metadata = []
        for workspace in self.i3_connection.get_workspaces():
            self.workspaces_metadata.append(
                WorkspaceDisplayMetadata(workspace.name, workspace.output,
                                         workspace.focused))
        return self.workspaces_metadata

    def _get_focused_monitor_name(self) -> str:
        focused_monitors = set()
        for ws_display_metadata in self.get_workspaces_display_metadata():
            if ws_display_metadata.is_focused:
                focused_monitors.add(ws_display_metadata.monitor_name)
        if not focused_monitors:
            raise WorkspaceGroupsError('No focused workspaces')
        if len(focused_monitors) > 1:
            logger.warning('Focused workspaces detected in multiple monitors')
        logger.debug('Focused monitors: %s', focused_monitors)
        return next(iter(focused_monitors))

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
        for ws_display_metadata in self.get_workspaces_display_metadata():
            ws_name = ws_display_metadata.workspace_name
            if ws_name == _SCRATCHPAD_WORKSPACE_NAME:
                continue
            if ws_name not in name_to_workspace:
                logger.warning('Unknown workspace detected: %s', ws_name)
            workspace = name_to_workspace[ws_name]
            monitor_to_workspaces[ws_display_metadata.monitor_name].append(
                workspace)
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
        self.send_i3_command(
            'workspace --no-auto-back-and-forth  "{}"'.format(name))
        updated_tree = self.get_tree(cached=False)
        focused_workspace = updated_tree.find_focused().workspace()
        self.set_focused_workspace(focused_workspace)

    def set_focused_workspace(self, workspace):
        current_workspace = self.get_unique_marked_workspace(
            CURRENT_WORKSPACE_MARK)
        if current_workspace:
            if current_workspace.id == workspace.id:
                logger.info('Current workspace already set, not resetting it.')
                return
            self.send_i3_command('[con_id={}] mark --add "{}"'.format(
                current_workspace.id, LAST_WORKSPACE_MARK))
        self.send_i3_command('[con_id={}] mark --add "{}"'.format(
            workspace.id, CURRENT_WORKSPACE_MARK))

    def get_unique_marked_workspace(self, mark) -> Optional[i3ipc.Con]:
        workspaces = self.get_tree().find_marked(mark)
        if not workspaces:
            logger.info('Didn\'t find workspaces with mark: %s', mark)
            return None
        if len(workspaces) > 1:
            logger.warning(
                'Multiple workspaces marked with %s, using first '
                'one', mark)
        return workspaces[0]

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
                ws_metadata = parse_workspace_name(workspace.name)
                ws_metadata.group = group
                ws_metadata.local_number = local_number
                ws_metadata.global_number = compute_global_number(
                    group_index, local_number)
                dynamic_name = ''
                # Add window icons to the active group if needed.
                if self.add_window_icons_all_groups or (self.add_window_icons
                                                        and group_index == 0):
                    dynamic_name = icons.get_workspace_icons_representation(
                        workspace)
                ws_metadata.dynamic_name = dynamic_name
                new_name = create_workspace_name(ws_metadata)
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
                        workspace.name).global_number
                    if global_number:
                        max_global_number = max(max_global_number,
                                                global_number)
            ws_metadata = WorkspaceGroupingMetadata(
                group=target_group,
                global_number=max_global_number + 1,
                local_number=1)
            new_workspace_name = create_workspace_name(ws_metadata)
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
        ws_metadata = WorkspaceGroupingMetadata(
            group=context_group, local_number=target_local_number)
        ws_metadata.global_number = compute_global_number(
            group_index, target_local_number)
        return create_workspace_name(ws_metadata)

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
        last_workspace = self.get_unique_marked_workspace(LAST_WORKSPACE_MARK)
        if not last_workspace:
            logger.info('Falling back to i3\'s built in workspace '
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
        last_workspace = self.get_unique_marked_workspace(LAST_WORKSPACE_MARK)
        if not last_workspace:
            logger.info('Falling back to i3\'s built in move workspace '
                        'back_and_forth')
            self.send_i3_command('move workspace back_and_forth')
            return
        self.send_i3_command(
            'move --no-auto-back-and-forth container to workspace "{}"'.format(
                last_workspace.name))

    def rename_focused_workspace(self, new_static_name: str) -> None:
        group_to_workspaces = get_group_to_workspaces(
            self.get_monitor_workspaces())
        # Organize the workspace groups to ensure they are consistent and every
        # workspace has a global number.
        self.organize_workspace_groups(group_to_workspaces)
        focused_workspace = self.get_tree().find_focused().workspace()
        ws_metadata = parse_workspace_name(focused_workspace.name)
        ws_metadata.static_name = new_static_name
        new_global_name = create_workspace_name(ws_metadata)
        self.send_i3_command('rename workspace "{}" to "{}"'.format(
            focused_workspace.name, new_global_name))
