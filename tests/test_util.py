import unittest.mock as mock

import i3ipc

from i3wsgroups import i3_workspace_groups


def create_workspace(workspace_id: int,
                     ws_metadata: i3_workspace_groups.WorkspaceGroupingMetadata
                    ) -> i3ipc.Con:
    workspace = mock.create_autospec(i3ipc.Con)
    workspace.id = workspace_id
    workspace.name = i3_workspace_groups.create_workspace_name(ws_metadata)
    return workspace
