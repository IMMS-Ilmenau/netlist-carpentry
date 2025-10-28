# mypy: disable-error-code="unreachable"
import os

import pytest

from netlist_carpentry.core.netlist_elements.mixins.metadata import MetadataMixin


def test_metadata_mixin_basics() -> None:
    metadata = MetadataMixin()
    metadata['some_category'] = {'key': 'value'}
    assert metadata['some_category'] == {'key': 'value'}
    assert metadata['some_category']['key'] == 'value'

    assert metadata.some_category == {'key': 'value'}
    assert metadata.some_category['key'] == 'value'
    assert metadata.some_category.get('key') == 'value'
    assert metadata.some_category.get('key2') is None

    with pytest.raises(ValueError):
        metadata['some_category'] = 'LOL'

    with pytest.raises(AttributeError):
        metadata.cat2


def test_is_empty() -> None:
    metadata = MetadataMixin()
    assert metadata.is_empty
    metadata.add_category('cat')
    assert metadata.is_empty
    metadata.add('foo', 'bar', 'cat')
    assert not metadata.is_empty
    metadata.add('foo', 'bar')
    assert not metadata.is_empty


def test_has_category() -> None:
    metadata = MetadataMixin()
    assert not metadata.has_category('some_category')
    metadata.add_category('some_category')
    assert metadata.has_category('some_category')


def test_add_category() -> None:
    md = MetadataMixin()
    is_added = md.add_category('some_category')
    assert is_added
    assert 'some_category' in md
    assert md['some_category'] == {}

    is_added = md.add_category('some_category')
    assert not is_added


def test_add() -> None:
    md = MetadataMixin()
    is_added = md.add('key', 'val')
    assert is_added
    assert 'general' in md
    assert md['general'] == {'key': 'val'}
    assert md['general']['key'] == 'val'

    is_added = md.add('key', 'val', 'some_category')
    assert is_added
    assert 'some_category' in md
    assert md['some_category'] == {'key': 'val'}
    assert md['some_category']['key'] == 'val'

    is_added = md.add('key', 'val', 'some_category')
    assert not is_added

    is_added = md.add('key', 'val2', 'some_category')
    assert not is_added
    assert md['some_category']['key'] == 'val'


def test_set() -> None:
    md = MetadataMixin()
    md.set('key', 'val')
    assert 'general' in md
    assert md['general'] == {'key': 'val'}
    assert md['general']['key'] == 'val'

    md.set('key', 'val', 'some_category')
    assert 'some_category' in md
    assert md['some_category'] == {'key': 'val'}
    assert md['some_category']['key'] == 'val'

    md.set('key', 'val2', 'some_category')
    assert 'some_category' in md
    assert md['some_category'] == {'key': 'val2'}
    assert md['some_category']['key'] == 'val2'


def test_get() -> None:
    md = MetadataMixin()
    md.set('key', 'val')
    md.set('key2', 'val2', 'cat')

    assert md.get('key') == 'val'
    assert md.get('key2') is None
    assert md.get('key2', 'diff') == 'diff'
    assert md.get('key', category='cat') is None
    assert md.get('key', category='cat', default='diff') == 'diff'
    assert md.get('key2', category='cat') == 'val2'
    assert md.get('key3', category='cat3') is None
    assert md.get('key3', category='cat3', default='diff') == 'diff'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
