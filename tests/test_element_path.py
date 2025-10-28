import os

import pytest

from netlist_carpentry.core.netlist_elements.element_path import ElementPath, PortPath, PortSegmentPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType


@pytest.fixture
def general_path() -> ElementPath:
    return ElementPath(raw='a.b.c.d.test_path')


def test_element_path_init(general_path: ElementPath) -> None:
    assert isinstance(general_path, ElementPath)
    assert general_path.name == 'test_path'
    assert general_path.type is EType.UNSPECIFIED
    assert general_path.raw == 'a.b.c.d.test_path'


def test_element_path_equality(general_path: ElementPath) -> None:
    element_path1 = ElementPath(raw=general_path.raw)
    element_path2 = ElementPath(raw=general_path.raw)
    assert element_path1 == element_path2


def test_element_path_change_name(general_path: ElementPath) -> None:
    assert general_path.name == 'test_path'
    assert general_path.raw == 'a.b.c.d.test_path'
    general_path.name = 'foo'
    assert general_path.name == 'foo'
    assert general_path.raw == 'a.b.c.d.foo'


def test_element_path_parent(general_path: ElementPath) -> None:
    assert general_path.parent.raw == 'a.b.c.d'
    assert general_path.parent.parent.raw == 'a.b.c'

    ps_path = PortSegmentPath(raw='module.inst1.inst2.port.0')
    assert ps_path.raw == 'module.inst1.inst2.port.0'
    assert ps_path.type == EType.PORT_SEGMENT
    assert ps_path.parent.raw == 'module.inst1.inst2.port'
    assert ps_path.parent.type == EType.PORT
    assert ps_path.parent.parent.raw == 'module.inst1.inst2'
    assert ps_path.parent.parent.type == EType.INSTANCE
    assert ps_path.parent.parent.parent.raw == 'module.inst1'
    assert ps_path.parent.parent.parent.type == EType.INSTANCE
    assert ps_path.parent.parent.parent.parent.raw == 'module'
    assert ps_path.parent.parent.parent.parent.type == EType.MODULE
    with pytest.raises(IndexError):
        assert ps_path.parent.parent.parent.parent.parent


def test_element_path_hierarchy_level(general_path: ElementPath) -> None:
    assert general_path.hierarchy_level == 4

    assert ElementPath(raw='a').hierarchy_level == 0
    assert ElementPath(raw='a').name == 'a'

    assert ElementPath(raw='').hierarchy_level == -1


def test_is_empty(general_path: ElementPath) -> None:
    assert not general_path.is_empty

    assert ElementPath(raw='').is_empty


def test_type_mapping(general_path: ElementPath) -> None:
    assert ElementPath(raw='').type_mapping == []

    mapping = [('a', EType.MODULE), ('b', EType.INSTANCE), ('c', EType.INSTANCE), ('d', EType.INSTANCE), ('test_path', EType.UNSPECIFIED)]
    assert general_path.type_mapping == mapping

    p_path = PortPath(raw='a.b.c.d.port')
    mapping = [('a', EType.MODULE), ('b', EType.INSTANCE), ('c', EType.INSTANCE), ('d', EType.INSTANCE), ('port', EType.PORT)]
    assert p_path.type_mapping == mapping

    ps_path = PortSegmentPath(raw='a.b.c.d.port.42')
    mapping = [
        ('a', EType.MODULE),
        ('b', EType.INSTANCE),
        ('c', EType.INSTANCE),
        ('d', EType.INSTANCE),
        ('port', EType.PORT),
        ('42', EType.PORT_SEGMENT),
    ]
    assert ps_path.type_mapping == mapping

    ws_path = WireSegmentPath(raw='a.b.c.d.wire.42')
    mapping = [
        ('a', EType.MODULE),
        ('b', EType.INSTANCE),
        ('c', EType.INSTANCE),
        ('d', EType.INSTANCE),
        ('wire', EType.WIRE),
        ('42', EType.WIRE_SEGMENT),
    ]
    assert ws_path.type_mapping == mapping


def test_eq(general_path: ElementPath) -> None:
    other_path = general_path
    assert other_path == general_path
    other_path = ElementPath(raw='a.b.c.d.test_path')
    assert other_path == general_path
    other_path = ElementPath(raw='a/b/c/d/test_path', sep='/')
    assert other_path == general_path
    other_path = PortPath(raw='a.b.c.d.test_path')
    assert other_path != general_path
    assert other_path == 'a.b.c.d.test_path'  # Can also compare bare strings
    assert other_path != 'a.b.c.d.wrong_path'
    assert other_path != 3  # Returns false for bad types


def test_nth_parent(general_path: ElementPath) -> None:
    assert general_path.nth_parent(0).raw == 'a.b.c.d.test_path'
    assert general_path.nth_parent(1).raw == 'a.b.c.d'
    assert general_path.parent.parent.raw == 'a.b.c'

    ps_path = PortSegmentPath(raw='module.inst1.inst2.port.0')
    assert ps_path.nth_parent(0).raw == 'module.inst1.inst2.port.0'
    assert ps_path.nth_parent(0).type == EType.PORT_SEGMENT
    assert ps_path.nth_parent(1).raw == 'module.inst1.inst2.port'
    assert ps_path.nth_parent(1).type == EType.PORT
    assert ps_path.nth_parent(2).raw == 'module.inst1.inst2'
    assert ps_path.nth_parent(2).type == EType.INSTANCE
    assert ps_path.nth_parent(3).raw == 'module.inst1'
    assert ps_path.nth_parent(3).type == EType.INSTANCE
    assert ps_path.nth_parent(4).raw == 'module'
    assert ps_path.nth_parent(4).type == EType.MODULE
    with pytest.raises(IndexError):
        assert ps_path.nth_parent(5)


def test_has_parent(general_path: ElementPath) -> None:
    assert general_path.has_parent()
    assert general_path.has_parent(4)
    assert not general_path.has_parent(5)


def test_get(general_path: ElementPath) -> None:
    element = general_path.get(0)
    assert element == 'a'
    element = general_path.get(4)
    assert element == 'test_path'
    element = general_path.get(-1)
    assert element == 'test_path'
    element = general_path.get(-5)
    assert element == 'a'
    # Invalid indices -> no IndexError but empty string
    element = general_path.get(5)
    assert element == ''
    element = general_path.get(-6)
    assert element == ''


def test_subscript(general_path: ElementPath) -> None:
    element = general_path[0]
    assert element == 'a'
    element = general_path[4]
    assert element == 'test_path'
    element = general_path[-1]
    assert element == 'test_path'
    element = general_path[-5]
    assert element == 'a'
    with pytest.raises(IndexError):
        general_path[5]
    with pytest.raises(IndexError):
        general_path[-6]


def test_get_subseq(general_path: ElementPath) -> None:
    elements = general_path.get_subseq(0, 5)
    assert elements == ['a', 'b', 'c', 'd', 'test_path']
    elements = general_path.get_subseq(-5, None)
    assert elements == ['a', 'b', 'c', 'd', 'test_path']
    elements = general_path.get_subseq(-3, -3)
    assert elements == []
    elements = general_path.get_subseq(2, -1)
    assert elements == ['c', 'd']
    elements = general_path.get_subseq(-1, 1)
    assert elements == []
    elements = general_path.get_subseq(-420, 69)
    assert elements == ['a', 'b', 'c', 'd', 'test_path']


def test_len(general_path: ElementPath) -> None:
    assert len(general_path) == 5

    assert len(ElementPath(raw='')) == 0

    assert len(ElementPath(raw='test')) == 1


def test_replace(general_path: ElementPath) -> None:
    assert general_path.raw == 'a.b.c.d.test_path'
    replaced = general_path.replace('a', 'foo')
    assert replaced.raw == 'foo.b.c.d.test_path'
    assert general_path.raw == 'foo.b.c.d.test_path'

    replaced = general_path.replace('baz', 'foo')
    assert replaced.raw == 'foo.b.c.d.test_path'
    assert general_path.raw == 'foo.b.c.d.test_path'


def test_is_type(general_path: ElementPath) -> None:
    is_type = general_path.is_type(EType.UNSPECIFIED)
    assert is_type
    is_type = general_path.is_type(EType.MODULE)
    assert not is_type


def test_element_path_str(general_path: ElementPath) -> None:
    assert str(general_path) == 'ElementPath(a.b.c.d.test_path)'


def test_element_path_repr(general_path: ElementPath) -> None:
    assert repr(general_path) == 'ElementPath a.b.c.d.test_path'


def test_hash(general_path: ElementPath) -> None:
    p1 = ElementPath(raw='a.b.c.d')
    p2 = ElementPath(raw='a.b.c.d')

    assert hash(p1) == hash(p2)
    assert hash(p1) != hash(general_path)
    assert hash(p2) != hash(general_path)


def test_is_instance_port() -> None:
    mport = PortPath(raw='module.port')
    assert not mport.is_instance_port
    iport = PortPath(raw='module.inst.port')
    assert iport.is_instance_port

    mps = PortSegmentPath(raw='module.port.0')
    assert not mps.is_instance_port
    ips = PortSegmentPath(raw='module.inst.port.0')
    assert ips.is_instance_port


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
