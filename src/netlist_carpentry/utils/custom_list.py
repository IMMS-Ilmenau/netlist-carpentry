from typing import Generator, Iterable, List, TypeVar, Union

from netlist_carpentry.core.exceptions import IdentifierConflictError, ObjectLockedError, ObjectNotFoundError

V = TypeVar('V')
NestedList = List[Union[V, 'NestedList[V]']]


class CustomList(List[V]):
    def flatten(self) -> List[V]:
        """
        This function flattens (expands) the current list.

        Returns:
            Self: A flat list containing all elements from the input list, including those in sublists.
        """

        def _flatten(items: Iterable[Union[V, Iterable[V]]]) -> Generator[V, None, None]:
            for x in items:
                if isinstance(x, list) and not isinstance(x, (str, bytes)):
                    yield from _flatten(x)
                else:
                    yield x

        self[:] = _flatten(self)  # replace contents in place
        return self

    def add(self, object: V, locked: bool = False, allow_duplicates: bool = False) -> V:
        """
        Adds an object to a list, if no equal object is already present.

        Args:
            object (object): The object to be added.
            locked (bool, optional): Whether the target list can be modified. Useful to prevent changes e.g. in modules marked as locked. Defaults to False.
            allow_duplicates (bool, optional): Whether the target list may contain duplicates, i.e. multiple equal values. Defaults to False.
                If True, this method behaves similar to `list.append`.

        Returns:
            V: The object that was successfully added.

        Raises:
            IdentifierConflictError: If such an object already exists in this list.
            ObjectLockedError: If "locked" is set to `True`, i.e. the list cannot be modified currently.
        """
        if locked:
            raise ObjectLockedError(f'Unable to add object {object} to the target list: Object is marked as locked!')
        if object not in self or allow_duplicates:
            super().append(object)
            return object
        raise IdentifierConflictError(f'An object {object} already exists in this list!' + 'Set allow_duplicates to True, if this is intended.')

    def remove(self, object: V, locked: bool = False) -> None:
        """
        Removes an element from a list if it exists in the list.

        Args:
            object (object): The element to be removed.
            locked (bool, optional): Whether the target list can be modified. Useful to prevent changes e.g. in modules marked as locked. Defaults to False.

        Raises:
            ObjectNotFoundError: If no such object exists in this list.
            ObjectLockedError: If "locked" is set to `True`, i.e. the list cannot be modified currently.
        """
        if locked:
            raise ObjectLockedError(f'Unable to remove object {object} from the target list: Object is marked as locked!')
        if object not in self:
            raise ObjectNotFoundError(f'No object {object} exists in this list!')
        super().remove(object)
