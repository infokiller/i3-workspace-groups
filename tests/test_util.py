import unittest.mock as mock

import i3ipc

from i3wsgroups import workspace_names


def create_workspace(workspace_id: int,
                     ws_metadata: workspace_names.WorkspaceGroupingMetadata
                    ) -> i3ipc.Con:
    workspace = mock.create_autospec(i3ipc.Con)
    workspace.id = workspace_id
    workspace.name = workspace_names.create_name(ws_metadata)
    return workspace
