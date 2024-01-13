import pytest

from i3wsgroups import config


# yapf: disable
@pytest.mark.parametrize('merge_from,merge_into,result', [
    ({}, {}, {}),
    ({'a': 0}, {}, {'a': 0}),
    ({'a': 0}, {'a': 1}, {'a': 1}),
    ({'a': []}, {}, {}),
    ({'a': 0}, {'b': 0}, {'a': 0, 'b': 0}),
    ({'a': {'aa': 0, 'ab': 0}}, {}, {'a': {'aa': 0, 'ab': 0}}),
])
# yapf: enable
def test_merge(merge_from, merge_into, result):
    config.merge_config(merge_from, merge_into)
    assert merge_into == result
