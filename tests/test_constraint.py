import os

import pytest

from netlist_carpentry import CFG
from netlist_carpentry.core.graph.constraint import Constraint
from netlist_carpentry.core.graph.pattern import Pattern


@pytest.fixture
def or_pattern():
    CFG.simplify_escaped_identifiers = True
    find_pattern_file = 'tests/files/or_pattern_find.json'
    replace_pattern_file = 'tests/files/or_pattern_replace.json'
    return Pattern.build_from_yosys_netlists(find_pattern_file, replace_pattern_file)


def test_constraint_basics():
    c = Constraint()
    assert isinstance(c, Constraint)

    with pytest.raises(NotImplementedError):
        c.check(None, None)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
