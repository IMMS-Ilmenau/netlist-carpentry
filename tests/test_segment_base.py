import os

import pytest

from netlist_carpentry.core.netlist_elements.segment_base import _Segment


@pytest.fixture()
def segment_base() -> _Segment:
    return _Segment(raw_path='a.b.c.3')


def test_segment_base(segment_base: _Segment) -> None:
    assert segment_base.index == 3

    with pytest.raises(ValueError):
        _Segment(raw_path='a.b.c')


def test_set_signal(segment_base: _Segment) -> None:
    with pytest.raises(NotImplementedError):
        segment_base.set_signal(1)


def test_set_name(segment_base: _Segment) -> None:
    assert segment_base.name == '3'
    segment_base.set_name('2')
    assert segment_base.name == '2'
    segment_base.set_name('foo')  # Only numbers allowed
    assert segment_base.name == '2'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
