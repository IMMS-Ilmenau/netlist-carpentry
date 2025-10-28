import copy
import os
from typing import Dict

import pytest

from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.netlist_elements.element_path import ElementPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement


@pytest.fixture
def netlist_element() -> NetlistElement:
    return NetlistElement(raw_path='a.b.c.d.test_name')


def test_netlist_element_constructor(netlist_element: NetlistElement) -> None:
    element_path = ElementPath(raw='a.b.c.d.test_name')
    assert netlist_element.name == 'test_name'
    assert netlist_element.type is EType.UNSPECIFIED
    assert netlist_element.path == element_path
    assert not netlist_element.locked
    assert len(netlist_element.metadata) == 0
    assert not netlist_element.can_carry_signal


def test_netlist_element_constructor_locked(netlist_element: NetlistElement) -> None:
    netlist_element.change_mutability(True)
    assert netlist_element.name == 'test_name'
    assert netlist_element.type is EType.UNSPECIFIED
    assert netlist_element.locked


def test_eq(netlist_element: NetlistElement) -> None:
    n2 = NetlistElement(raw_path=netlist_element.raw_path)
    assert netlist_element == n2

    n3 = NetlistElement(raw_path='wrong_path')
    assert netlist_element != n3

    n4 = 'wrong_type'
    assert netlist_element != n4
    assert netlist_element.__eq__(n4) == NotImplemented


def test_set_name(netlist_element: NetlistElement) -> None:
    assert netlist_element.name == 'test_name'
    netlist_element.set_name('foo')
    assert netlist_element.name == 'foo'


def test_hierarchy_level(netlist_element: NetlistElement) -> None:
    assert netlist_element.hierarchy_level == 4


def test_parent(netlist_element: NetlistElement) -> None:
    with pytest.raises(NotImplementedError):
        netlist_element.parent


def test_change_mutability(netlist_element: NetlistElement) -> None:
    locked = netlist_element.locked
    netlist_element.change_mutability(not locked)
    assert locked != netlist_element.locked

    netlist_element.change_mutability(True)
    assert netlist_element.locked is True
    netlist_element.change_mutability(True)
    assert netlist_element.locked is True


def test_is_placeholder_instance(netlist_element: NetlistElement) -> None:
    assert not netlist_element.is_placeholder_instance

    assert NetlistElement(raw_path='').is_placeholder_instance


def test_add_listener(netlist_element: NetlistElement) -> None:
    from utils import standard_instance_with_ports

    assert netlist_element._listeners == {0} - {0}  # Funny eyes <=> empty set
    inst = standard_instance_with_ports()
    netlist_element.add_listener(inst)
    assert netlist_element._listeners == {inst}

    netlist_element.add_listener(inst)
    assert netlist_element._listeners == {inst}


def test_remove_listener(netlist_element: NetlistElement) -> None:
    from utils import standard_instance_with_ports

    inst = standard_instance_with_ports()
    netlist_element.add_listener(inst)
    assert netlist_element._listeners == {inst}

    netlist_element.remove_listener(inst)
    assert netlist_element._listeners == {0} - {0}  # Funny eyes <=> empty set

    with pytest.raises(ObjectNotFoundError):
        netlist_element.remove_listener(inst)
    assert netlist_element._listeners == {0} - {0}  # Funny eyes <=> empty set


def test_notify_listeners(netlist_element: NetlistElement) -> None:
    from utils import standard_instance_with_ports

    any_notified = netlist_element.notify_listeners()
    assert not any_notified
    inst = standard_instance_with_ports()
    netlist_element.add_listener(inst)
    assert netlist_element._listeners == {inst}
    any_notified = netlist_element.notify_listeners()
    assert any_notified


def test_receive_notification(netlist_element: NetlistElement) -> None:
    anything_done = netlist_element.on_notification(NetlistElement(raw_path='a.b.other_object'))
    assert not anything_done


def test_evaluate(netlist_element: NetlistElement) -> None:
    with pytest.raises(NotImplementedError):
        netlist_element.evaluate()


def test_normalize_metadata(netlist_element: NetlistElement) -> None:
    target_dict: Dict[str, object] = {}
    found_dict = netlist_element.normalize_metadata()
    assert target_dict == found_dict

    target_dict = {'a.b.c.d.test_name': {}}
    found_dict = netlist_element.normalize_metadata(include_empty=True)
    assert target_dict == found_dict

    netlist_element.metadata.add_category('cat')
    target_dict = {'a.b.c.d.test_name': {'cat': {}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True)
    assert target_dict == found_dict

    target_dict = {}
    found_dict = netlist_element.normalize_metadata()
    assert target_dict == found_dict

    target_dict = {'cat': {'a.b.c.d.test_name': {}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True, sort_by='category')
    assert target_dict == found_dict

    target_dict = {}
    found_dict = netlist_element.normalize_metadata(sort_by='category')
    assert target_dict == found_dict

    netlist_element.metadata.set('foo', 'bar')
    target_dict = {'cat': {'a.b.c.d.test_name': {}}, 'general': {'a.b.c.d.test_name': {'foo': 'bar'}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True, sort_by='category')
    assert target_dict == found_dict

    target_dict = {'general': {'a.b.c.d.test_name': {'foo': 'bar'}}}
    found_dict = netlist_element.normalize_metadata(sort_by='category')
    assert target_dict == found_dict

    netlist_element.metadata.set('foo', 'bar')
    target_dict = {'a.b.c.d.test_name': {'general': {'foo': 'bar'}, 'cat': {}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True)
    assert target_dict == found_dict

    target_dict = {'a.b.c.d.test_name': {'general': {'foo': 'bar'}}}
    found_dict = netlist_element.normalize_metadata()
    assert target_dict == found_dict

    netlist_element.metadata.set('foo', 'baz', 'cat')
    target_dict = {'cat': {'a.b.c.d.test_name': {'foo': 'baz'}}, 'general': {'a.b.c.d.test_name': {'foo': 'bar'}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True, sort_by='category')
    assert target_dict == found_dict

    target_dict = {'cat': {'a.b.c.d.test_name': {'foo': 'baz'}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True, sort_by='category', filter=lambda cat, md: cat == 'cat')
    assert target_dict == found_dict

    netlist_element.metadata.add_category('cat2')
    target_dict = {'cat': {'a.b.c.d.test_name': {'foo': 'baz'}}}
    found_dict = netlist_element.normalize_metadata(sort_by='category', filter=lambda cat, md: 'cat' in cat)
    assert target_dict == found_dict

    netlist_element.metadata.add_category('cat2')
    target_dict = {'cat': {'a.b.c.d.test_name': {'foo': 'baz'}}, 'cat2': {'a.b.c.d.test_name': {}}}
    found_dict = netlist_element.normalize_metadata(include_empty=True, sort_by='category', filter=lambda cat, md: 'cat' in cat)
    assert target_dict == found_dict


def test_hash(netlist_element: NetlistElement) -> None:
    h1 = hash(netlist_element)
    h2 = hash(copy.deepcopy(netlist_element))

    assert h1 == h2

    n2 = NetlistElement(raw_path='a.b.c.d.e')

    assert hash(n2) != hash(netlist_element)


def test_str(netlist_element: NetlistElement) -> None:
    assert str(netlist_element) == 'NetlistElement: UNSPECIFIED "test_name" with path a.b.c.d.test_name'


def test_repr(netlist_element: NetlistElement) -> None:
    assert repr(netlist_element) == 'NetlistElement(test_name: UNSPECIFIED at a.b.c.d.test_name)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
