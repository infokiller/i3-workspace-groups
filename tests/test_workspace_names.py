from i3wsgroups.workspace_names import *
from i3wsgroups.controller import *
from tests import test_util


def test_compute_global_number():
    assert compute_global_number(0, 0, 1) == 1
    assert compute_global_number(0, 1, 1) == 101
    assert compute_global_number(1, 1, 1) == 100101


def test_global_number_to_group_index():
    assert global_number_to_group_index(1) == 0
    assert global_number_to_group_index(2) == 0
    assert global_number_to_group_index(101) == 1
    assert global_number_to_group_index(102) == 1


def test_global_number_to_local_number():
    assert global_number_to_local_number(1) == 1
    assert global_number_to_local_number(2) == 2
    assert global_number_to_local_number(101) == 1
    assert global_number_to_local_number(10205) == 5


def test_compute_local_numbers1():
    monitor_workspaces = [
        test_util.create_workspace(
            1, WorkspaceGroupingMetadata(global_number=1, local_number=1))
    ]
    local_numbers = compute_local_numbers(monitor_workspaces,
                                          monitor_workspaces, False)
    assert local_numbers == [1]


def test_compute_local_numbers2():
    monitor_workspaces = [
        test_util.create_workspace(
            2, WorkspaceGroupingMetadata(global_number=1, local_number=2))
    ]
    local_numbers = compute_local_numbers(monitor_workspaces,
                                          monitor_workspaces, True)
    assert local_numbers == [1]


def test_compute_local_numbers3():
    monitor_workspaces = [
        test_util.create_workspace(
            1, WorkspaceGroupingMetadata(global_number=1, local_number=1)),
        test_util.create_workspace(
            2, WorkspaceGroupingMetadata(global_number=2, local_number=2))
    ]
    all_workspaces = monitor_workspaces + [
        test_util.create_workspace(
            3, WorkspaceGroupingMetadata(global_number=3, local_number=1))
    ]
    local_numbers = compute_local_numbers(monitor_workspaces, all_workspaces,
                                          True)
    assert local_numbers == [2, 3]

def test_compute_local_numbers4():
    monitor_workspaces = [
        test_util.create_workspace(
            1, WorkspaceGroupingMetadata(global_number=1, local_number=1)),
        test_util.create_workspace(
            2, WorkspaceGroupingMetadata(global_number=2, local_number=2))
    ]
    all_workspaces = monitor_workspaces + [
        test_util.create_workspace(
            3, WorkspaceGroupingMetadata(global_number=3, local_number=2))
    ]
    local_numbers = compute_local_numbers(monitor_workspaces, all_workspaces,
                                          False)
    assert local_numbers == [1, 3]
