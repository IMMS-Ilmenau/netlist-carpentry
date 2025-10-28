from typing import Dict, List, TypeVar, Union

from netlist_carpentry.core.exceptions import IdentifierConflictError, ObjectLockedError, ObjectNotFoundError

K = TypeVar('K', int, str)
V = TypeVar('V')
GENERIC_VAL = Union[V, List[V], Dict[K, V]]
GENERIC_DICT = Dict[Union[str, int], GENERIC_VAL[str, int]]


class CustomDict(Dict[K, V]):
    def append_or_create(self, key: K, element: V) -> None:
        """
        Appends an element to a list in the dictionary or creates a new list if the key does not exist.

        Args:
            key (K): The key under which elements will be appended or created.
            element (V): The element to append or create in the dictionary.

        Raises:
            ValueError: If the provided key already exists but its associated value is not a list.
        """
        if key not in self:
            self[key] = [element]  # type: ignore[assignment]
        else:
            dict_entry = self[key]
            if isinstance(dict_entry, list):
                dict_entry.append(element)
            else:
                raise ValueError(f'Key {key} already exists but is not a list.')

    def update_or_create(self, key: K, element: Dict[K, V]) -> None:
        """
        Updates an existing dictionary inside this dictionary or creates a new one if the key does not exist.

        Args:
            key (K): The key under which dictionaries will be updated or created.
            element (dict): The dictionary to update or create inside this dictionary.

        """
        if key in self:
            sub_dict = self[key]
            if isinstance(sub_dict, dict):
                sub_dict.update(element)
            else:
                raise ValueError(f'Key {key} already exists but is not a dictionary.')
        else:
            self[key] = element  # type: ignore[assignment]

    def add(self, key: K, element: V, locked: bool = False) -> V:
        """
        Adds an element to this dictionary if the key does not already exist.

        Args:
            key (K): The key under which the element should be stored.
            element (V): The element to be added.
            locked (bool, optional): Whether the target dictionary can be modified.
                Useful to prevent changes e.g. in modules marked as locked. Defaults to False.

        Returns:
            V: The element that was successfully added.

        Raises:
            IdentifierConflictError: If an object with the same key already exists.
            ObjectLockedError: If "locked" is set to `True`, i.e. the dict cannot be modified currently.
        """
        if locked:
            raise ObjectLockedError(f'Unable to add element {element} with key {key} to the target dictionary: Object is marked as locked!')
        if key not in self:
            self[key] = element
            return element
        raise IdentifierConflictError(f'An object {key} already exists!')

    def remove(self, key: K, locked: bool = False) -> None:
        """
        Removes an entry from this dictionary if the key exists.

        Args:
            key (K): The key of the entry to be removed.
            locked (bool, optional): Whether the target dictionary can be modified.
                Useful to prevent changes e.g. in modules marked as locked. Defaults to False.

        Raises:
            ObjectNotFoundError: If no object with the given key exists.
            ObjectLockedError: If "locked" is set to `True`, i.e. the dict cannot be modified currently.
        """
        if locked:
            raise ObjectLockedError(f'Unable to remove an element with key {key} from the target dictionary: Object is marked as locked!')
        if key not in self:
            raise ObjectNotFoundError(f'No object with key {key} exists!')
        self.pop(key)
