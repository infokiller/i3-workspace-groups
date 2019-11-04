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
import collections
from typing import Dict, List, Optional, Set

import i3ipc

from i3wsgroups import logger

logger = logger.logger

WORKSPACE_NAME_SECTIONS = [
    'global_number',
    'group',
    'static_name',
    'dynamic_name',
    'local_number',
]
# Unicode zero width char.
SECTIONS_DELIM = '\u200b'

_MAX_GROUPS_PER_MONITOR = 1000
_MAX_WORKSPACES_PER_GROUP = 100

_SCRATCHPAD_WORKSPACE_NAME = '__i3_scratch'

GroupToWorkspaces = Dict[str, List[i3ipc.Con]]


class WorkspaceDisplayMetadata:

    def __init__(self, workspace_name: str, monitor_name: str,
                 is_focused: bool):
        self.workspace_name: str = workspace_name
        self.monitor_name: str = monitor_name
        self.is_focused: bool = is_focused

    def __str__(self):
        return str(self.__dict__)


class WorkspaceGroupingMetadata:

    # pylint: disable=too-many-arguments
    def __init__(self,
                 global_number: Optional[int] = None,
                 group: Optional[str] = None,
                 static_name: Optional[str] = None,
                 dynamic_name: Optional[str] = None,
                 local_number: Optional[int] = None):
        self.global_number: Optional[int] = global_number
        self.group: Optional[str] = group
        self.static_name: Optional[str] = static_name
        self.dynamic_name: Optional[str] = dynamic_name
        self.local_number: Optional[int] = local_number

    def __str__(self):
        return str(self.__dict__)


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


def parse_global_number_section(global_number_section: Optional[str]
                               ) -> Optional[int]:
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


def parse_name(workspace_name: str) -> WorkspaceGroupingMetadata:
    result = WorkspaceGroupingMetadata(group='')
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
    ws_metadata = parse_name(workspace.name)
    local_number = ws_metadata.local_number
    if local_number is None and ws_metadata.global_number is not None:
        local_number = global_number_to_local_number(ws_metadata.global_number)
    return local_number


def get_group(workspace: i3ipc.Con) -> str:
    return parse_name(workspace.name).group


def get_used_local_numbers(workspaces: List[i3ipc.Con]) -> Set[int]:
    used_local_numbers = set()
    for workspace in workspaces:
        local_number = parse_name(workspace.name).local_number
        if local_number is not None:
            used_local_numbers.add(local_number)
    return used_local_numbers


def get_lowest_free_local_numbers(num: int,
                                  used_local_numbers: Set[int]) -> List[int]:
    local_numbers = []
    for local_number in range(1, _MAX_WORKSPACES_PER_GROUP):
        if len(local_numbers) == num:
            break
        if local_number in used_local_numbers:
            continue
        local_numbers.append(local_number)
    assert len(local_numbers) == num
    return local_numbers


def compute_local_numbers(monitor_workspaces: List[i3ipc.Con],
                          all_workspaces: List[i3ipc.Con],
                          renumber_workspaces: bool) -> List[int]:
    monitor_workspace_ids = {ws.id for ws in monitor_workspaces}
    other_monitors_workspaces = [
        ws for ws in all_workspaces if ws.id not in monitor_workspace_ids
    ]
    used_local_numbers = get_used_local_numbers(other_monitors_workspaces)
    logger.debug('Local numbers used by group in other monitors: %s',
                 used_local_numbers)
    if renumber_workspaces:
        return get_lowest_free_local_numbers(len(monitor_workspaces),
                                             used_local_numbers)
    if used_local_numbers:
        last_used_local_number = max(used_local_numbers)
    else:
        last_used_local_number = 0
    local_numbers = []
    for workspace in monitor_workspaces:
        ws_metadata = parse_name(workspace.name)
        local_number = ws_metadata.local_number
        if local_number is None or (local_number in used_local_numbers):
            local_number = last_used_local_number + 1
            last_used_local_number += 1
        local_numbers.append(local_number)
    return local_numbers


def create_name(ws_metadata: WorkspaceGroupingMetadata) -> str:
    assert ws_metadata.global_number is not None
    assert ws_metadata.group is not None
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


def compute_global_number(monitor_index: int, group_index: int,
                          local_number: int) -> int:
    assert local_number < _MAX_WORKSPACES_PER_GROUP
    monitor_starting_number = monitor_index * (_MAX_GROUPS_PER_MONITOR *
                                               _MAX_WORKSPACES_PER_GROUP)
    group_starting_number = _MAX_WORKSPACES_PER_GROUP * group_index
    return monitor_starting_number + group_starting_number + local_number


def global_number_to_group_index(global_number: int) -> int:
    return global_number % (_MAX_GROUPS_PER_MONITOR * _MAX_WORKSPACES_PER_GROUP
                           ) // _MAX_WORKSPACES_PER_GROUP


def global_number_to_local_number(global_number: int) -> int:
    return global_number % _MAX_WORKSPACES_PER_GROUP


def get_group_to_workspaces(workspaces: List[i3ipc.Con]) -> GroupToWorkspaces:
    group_to_workspaces = collections.OrderedDict()
    for workspace in workspaces:
        ws_metadata = parse_name(workspace.name)
        group = ws_metadata.group
        logger.debug('Workspace %s parsed as: %s', workspace.name, ws_metadata)
        if group not in group_to_workspaces:
            group_to_workspaces[group] = []
        group_to_workspaces[group].append(workspace)
    return group_to_workspaces


def _is_reordered_workspace(name1, name2):
    ws1_metadata = parse_name(name1)
    ws2_metadata = parse_name(name2)
    if ws1_metadata.group != ws2_metadata.group:
        return False
    if ws1_metadata.local_number:
        return ws1_metadata.local_number == ws2_metadata.local_number
    return ws1_metadata.static_name == ws2_metadata.static_name


def get_group_index(target_group: str, group_to_workspaces: GroupToWorkspaces):
    # If there are existing workspaces in the group, use them to derive the
    # group index. Otherwise, use the smallest available group index.
    # Note that we can't derive the group index from its relative position
    # in the group list, because there may have been a group that was
    # implicitly removed because it had a single empty workspace and the
    # user focused on another workspace.
    group_to_index = {}
    for group, workspaces in group_to_workspaces.items():
        for workspace in workspaces:
            parsed_name = parse_name(workspace.name)
            if parsed_name.global_number is not None:
                group_to_index[group] = global_number_to_group_index(
                    parsed_name.global_number)
                break
    if target_group in group_to_index:
        return group_to_index[target_group]
    if group_to_index:
        return max(group_to_index.values()) + 1
    return 0
