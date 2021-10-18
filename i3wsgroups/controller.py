#!/usr/bin/env python3

import copy
from typing import List, Optional, Tuple

import i3ipc

from i3wsgroups import i3_proxy, icons, logger
from i3wsgroups import workspace_names as ws_names

# from i3wsgroups.ws_names import *

GroupToWorkspaces = ws_names.GroupToWorkspaces
OrderedWorkspaceGroups = List[Tuple[str, List[i3ipc.Con]]]

logger = logger.logger


class WorkspaceGroupsError(Exception):
    pass


class ActiveGroupContext:

    @staticmethod
    def get_group_name(_: i3ipc.Con,
                       group_to_workspaces: GroupToWorkspaces) -> str:
        # Return the first group which is defined as the active one.
        return next(iter(group_to_workspaces))


class FocusedGroupContext:

    @staticmethod
    def get_group_name(tree: i3ipc.Con, _: GroupToWorkspaces) -> str:
        focused_workspace = tree.find_focused().workspace()
        return ws_names.get_group(focused_workspace)


class NamedGroupContext:

    def __init__(self, group_name: str):
        self.group_name = group_name

    def get_group_name(self, _: i3ipc.Con, __: GroupToWorkspaces) -> str:
        return self.group_name


class WorkspaceGroupsController:

    def __init__(self, i3_proxy_: i3_proxy.I3Proxy, config):
        self.i3_proxy = i3_proxy_
        self.config = config
        self.icons_resolver = icons.IconsResolver(self.config['icons'])

    def get_tree(self, cached: bool = True) -> i3ipc.Con:
        return self.i3_proxy.get_tree(cached)

    def organize_workspace_groups(self,
                                  workspace_groups: OrderedWorkspaceGroups,
                                  monitor_name: Optional[str] = None) -> None:
        if monitor_name is None:
            monitor_name = self.i3_proxy.get_focused_monitor_name()
        monitor_index = self.i3_proxy.get_monitor_index(monitor_name)
        group_to_all_workspaces = ws_names.get_group_to_workspaces(
            self.get_tree().workspaces())
        for group_index, (group, workspaces) in enumerate(workspace_groups):
            logger.debug('Organizing workspace group: "%s" in monitor "%s"',
                         group, monitor_name)
            local_numbers = ws_names.compute_local_numbers(
                workspaces, group_to_all_workspaces.get(group, []),
                self.config['renumber_workspaces'])
            for workspace, local_number in zip(workspaces, local_numbers):
                ws_metadata = ws_names.parse_name(workspace.name)
                ws_metadata.group = group
                ws_metadata.local_number = local_number
                ws_metadata.global_number = ws_names.compute_global_number(
                    monitor_index, group_index, local_number)
                dynamic_name = ''
                # Add window icons if needed.
                if self.config['icons']['enable'] and (
                        self.config['icons']['enable_all_groups'] or
                        group_index == 0):
                    dynamic_name = self.icons_resolver.get_workspace_icons(
                        workspace)
                ws_metadata.dynamic_name = dynamic_name
                new_name = ws_names.create_name(ws_metadata)
                self.i3_proxy.rename_workspace(workspace.name, new_name)
                workspace.name = new_name

    def list_groups(self, monitor_only: bool = False) -> List[str]:
        workspaces = self.get_tree().workspaces()
        if monitor_only:
            workspaces = self.i3_proxy.get_monitor_workspaces()
        group_to_workspaces = ws_names.get_group_to_workspaces(workspaces)
        return list(group_to_workspaces.keys())

    def list_workspaces(self,
                        group_context,
                        focused_only: bool = False,
                        monitor_only: bool = False) -> List[i3ipc.Con]:
        workspaces = self.get_tree().workspaces()
        if monitor_only:
            workspaces = self.i3_proxy.get_monitor_workspaces()
        group_to_workspaces = ws_names.get_group_to_workspaces(workspaces)
        # If no context group specified, return workspaces from all groups.
        if not group_context:
            group_workspaces = sum(
                (list(workspaces)
                 for workspaces in group_to_workspaces.values()), [])
        else:
            group_name = group_context.get_group_name(self.get_tree(),
                                                      group_to_workspaces)
            group_workspaces = group_to_workspaces.get(group_name, [])
        if not focused_only:
            return group_workspaces
        focused_workspace = self.get_tree().find_focused().workspace()
        return [ws for ws in group_workspaces if ws.id == focused_workspace.id]

    def _find_free_local_number(self, target_group: str):
        group_to_all_workspaces = ws_names.get_group_to_workspaces(
            self.get_tree().workspaces())
        used_local_numbers = ws_names.get_used_local_numbers(
            group_to_all_workspaces.get(target_group, []))
        return next(
            iter(ws_names.get_lowest_free_local_numbers(1, used_local_numbers)))

    def _create_new_active_group_workspace_name(self, monitor_name: str,
                                                target_group: str) -> i3ipc.Con:
        local_number = self._find_free_local_number(target_group)
        global_number = ws_names.compute_global_number(
            monitor_index=self.i3_proxy.get_monitor_index(monitor_name),
            group_index=0,
            local_number=local_number)
        ws_metadata = ws_names.WorkspaceGroupingMetadata(
            group=target_group,
            global_number=global_number,
            local_number=local_number)
        return ws_names.create_name(ws_metadata)

    def switch_monitor_active_group(self, monitor_name: str,
                                    target_group: str) -> None:
        monitor_workspaces = self.i3_proxy.get_monitor_workspaces(monitor_name)
        group_to_monitor_workspaces = ws_names.get_group_to_workspaces(
            monitor_workspaces)
        reordered_group_to_workspaces = [
            (target_group, group_to_monitor_workspaces.get(target_group, []))
        ]
        for group, workspaces in group_to_monitor_workspaces.items():
            if group != target_group:
                reordered_group_to_workspaces.append((group, workspaces))
        self.organize_workspace_groups(reordered_group_to_workspaces,
                                       monitor_name)

    def switch_active_group(self, target_group: str,
                            focused_monitor_only: bool) -> None:
        focused_monitor_name = self.i3_proxy.get_focused_monitor_name()
        monitor_to_workspaces = self.i3_proxy.get_monitor_to_workspaces()
        for monitor, workspaces in monitor_to_workspaces.items():
            group_exists = (target_group
                            in ws_names.get_group_to_workspaces(workspaces))
            if monitor == focused_monitor_name:
                logger.debug('Switching active group in focused monitor "%s"',
                             monitor)
            elif not focused_monitor_only and group_exists:
                logger.debug(
                    'Non focused monitor %s has workspaces in the group "%s", '
                    'switching to it.', monitor, target_group)
            else:
                continue
            self.switch_monitor_active_group(monitor, target_group)
        # NOTE: We only switch focus to the new workspace after renaming all the
        # workspaces in all monitors and groups. Otherwise, if the previously
        # focused workspace was renamed, i3's `workspace back_and_forth` will
        # switch focus to a non-existant workspace name.
        focused_group = ws_names.get_group(
            self.get_tree().find_focused().workspace())
        # The target group is already focused, no need to do anything.
        if focused_group == target_group:
            return
        group_to_monitor_workspaces = ws_names.get_group_to_workspaces(
            monitor_to_workspaces[focused_monitor_name])
        if target_group in group_to_monitor_workspaces:
            workspace_name = group_to_monitor_workspaces[target_group][0].name
        # The focused monitor doesn't have any workspaces in the target group,
        # so create one.
        else:
            workspace_name = self._create_new_active_group_workspace_name(
                focused_monitor_name, target_group)
        self.i3_proxy.focus_workspace(workspace_name, auto_back_and_forth=False)

    def _create_workspace_name(
            self, metadata: ws_names.WorkspaceGroupingMetadata) -> str:
        focused_monitor_name = self.i3_proxy.get_focused_monitor_name()
        monitor_index = self.i3_proxy.get_monitor_index(focused_monitor_name)
        group_to_monitor_workspaces = ws_names.get_group_to_workspaces(
            self.i3_proxy.get_monitor_workspaces(focused_monitor_name))
        group_index = ws_names.get_group_index(metadata.group,
                                               group_to_monitor_workspaces)
        metadata = copy.deepcopy(metadata)
        local_number = metadata.local_number
        if local_number is None:
            local_number = 1
        metadata.global_number = ws_names.compute_global_number(
            monitor_index, group_index, (local_number))
        return ws_names.create_name(metadata)

    # If there's an existing workspace in the given group with the given local
    # number, return its (name, True). Otherwise, create a name and return
    # (name, False).
    def _get_workspace_by_local_number(self, group: str,
                                       local_number: int) -> Tuple[str, bool]:
        # i3 commands like `workspace number n` will focus on an existing
        # workspace in another monitor if possible. To preserve this behavior,
        # we check the group workspaces in all monitors.
        group_to_all_workspaces = ws_names.get_group_to_workspaces(
            self.get_tree().workspaces())
        # Every workspace must have a unique (group, local_number) pair. This
        # tracks whether we found a workspace that conflicts with the given
        # (group, local_number).
        for workspace in group_to_all_workspaces.get(group, []):
            if ws_names.get_local_workspace_number(workspace) == local_number:
                return workspace.name, True
        return self._create_workspace_name(
            ws_names.WorkspaceGroupingMetadata(
                group=group, local_number=local_number)), False

    def _get_group_from_context(self, group_context):
        group_context = group_context or ActiveGroupContext()
        focused_monitor_name = self.i3_proxy.get_focused_monitor_name()
        group_to_monitor_workspaces = ws_names.get_group_to_workspaces(
            self.i3_proxy.get_monitor_workspaces(focused_monitor_name))
        target_group = group_context.get_group_name(
            self.get_tree(), group_to_monitor_workspaces)
        logger.info('Context group: "%s"', target_group)
        return target_group

    def focus_workspace_number(self, group_context,
                               target_local_number: int) -> None:
        target_workspace_name, _ = self._get_workspace_by_local_number(
            group=self._get_group_from_context(group_context),
            local_number=target_local_number)
        logger.debug('Derived workspace name: "%s"', target_workspace_name)
        self.i3_proxy.focus_workspace(target_workspace_name)

    def move_to_workspace_number(self,
                                 group_context,
                                 target_local_number: int,
                                 no_auto_back_and_forth: bool = False) -> None:
        target_workspace_name, _ = self._get_workspace_by_local_number(
            group=self._get_group_from_context(group_context),
            local_number=target_local_number)
        flags = '--no-auto-back-and-forth' if no_auto_back_and_forth else ''
        self.i3_proxy.send_i3_command(
            f'move {flags} container to workspace "{target_workspace_name}"')

    def _relative_workspace_in_group(self,
                                     offset_from_current: int = 1) -> i3ipc.Con:
        focused_workspace = self.get_tree().find_focused().workspace()
        focused_group = ws_names.get_group(focused_workspace)
        group_workspaces_all_monitors = ws_names.get_group_to_workspaces(
            self.get_tree().workspaces())[focused_group]
        current_workspace_index = 0
        for (current_workspace_index,
             workspace) in enumerate(group_workspaces_all_monitors):
            if workspace.id == focused_workspace.id:
                break
        next_workspace_index = (current_workspace_index + offset_from_current
                               ) % len(group_workspaces_all_monitors)
        return group_workspaces_all_monitors[next_workspace_index]

    def focus_workspace_relative(self, offset_from_current: int) -> None:
        next_workspace = self._relative_workspace_in_group(offset_from_current)
        self.i3_proxy.focus_workspace(next_workspace.name,
                                      auto_back_and_forth=False)

    def move_workspace_relative(self, offset_from_current: int) -> None:
        next_workspace = self._relative_workspace_in_group(offset_from_current)
        self.i3_proxy.send_i3_command(
            f'move container to workspace "{next_workspace.name}"')

    def focus_new_workspace(self, group_context) -> None:
        target_group = self._get_group_from_context(group_context)
        local_number = self._find_free_local_number(target_group)
        self.focus_workspace_number(group_context, local_number)

    def move_to_new_workspace(self, group_context) -> None:
        target_group = self._get_group_from_context(group_context)
        local_number = self._find_free_local_number(target_group)
        self.move_to_workspace_number(group_context, local_number, False)

    def update_focused_workspace(
            self, metadata_updates: ws_names.WorkspaceGroupingMetadata) -> None:
        if metadata_updates.group is not None and (
                not ws_names.is_valid_group_name(metadata_updates.group)):
            raise WorkspaceGroupsError(
                f'Invalid group name provided: "{metadata_updates.group}"')
        focused_workspace = self.get_tree().find_focused().workspace()
        metadata = ws_names.parse_name(focused_workspace.name)
        for section in ['group', 'local_number', 'static_name']:
            value = getattr(metadata_updates, section)
            if value is not None:
                setattr(metadata, section, value)
        found_name, exists = self._get_workspace_by_local_number(
            metadata.group, metadata.local_number)
        if exists and focused_workspace.name != found_name:
            if not self.config['workspace_moves']['use_next_available_number']:
                raise WorkspaceGroupsError(
                    f'Workspace with local number "{metadata.local_number}" '
                    'already exists in group: "{metadata.group}": '
                    '"{found_name}"')
            group_to_all_workspaces = ws_names.get_group_to_workspaces(
                self.get_tree().workspaces())
            used_local_numbers = ws_names.get_used_local_numbers(
                group_to_all_workspaces[metadata.group])
            free_local_numbers = ws_names.get_lowest_free_local_numbers(
                1, used_local_numbers)
            metadata.local_number = next(iter(free_local_numbers))
        self.i3_proxy.rename_workspace(focused_workspace.name,
                                       self._create_workspace_name(metadata))
