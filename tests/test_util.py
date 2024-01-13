from __future__ import annotations

import unittest.mock

import i3ipc

from i3wsgroups import workspace_names


def create_workspace(workspace_id: int,
                     ws_metadata: workspace_names.WorkspaceGroupingMetadata) -> i3ipc.Con:
    workspace = unittest.mock.create_autospec(i3ipc.Con)
    workspace.id = workspace_id
    if ws_metadata.group is None:
        ws_metadata.group = ''
    workspace.name = workspace_names.create_name(ws_metadata)
    return workspace
