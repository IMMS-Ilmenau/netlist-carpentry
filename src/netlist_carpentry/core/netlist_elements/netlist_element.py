from __future__ import annotations

from typing import Callable, Dict, Literal, Set, Union

from pydantic import BaseModel
from typing_extensions import Self

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.netlist_elements.element_path import ElementPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT, MetadataMixin
from netlist_carpentry.core.protocols.netlist_elements import NetlistElementLike


class NetlistElement(BaseModel):
    """
    Represents a netlist element, such as an instance or a wire.

    Attributes:
        raw_path (str): The hierarchical path of the element in the design as a string, where '.' is the hierarchical separator.
    """

    raw_path: str
    """The hierarchical path of the element in the design as a plain string."""
    _locked: bool = False
    """Whether the element is structurally unchangeable (e.g. if set to True, connections cannot be changed). Defaults to False."""
    _listeners: Set[NetlistElementLike] = set()

    parameters: Dict[str, Union[str, int]] = {}
    """Attributes of a netlist element. Can be user-defined, or e. g. by Yosys (such as `width` for some instances)."""

    metadata: MetadataMixin = MetadataMixin()
    """
    Metadata of a netlist element.

    Can be user-defined, or e. g. by Yosys (such as `src` for the HDL source).
    Is also grouped by categories, i.e. all metadata from Yosys can be accessed via Module.metadata["yosys"],
    or via Module.metadata.yosys, which both return a dictionary of all metadata.
    Read the documentation of `MetaDataMixin` for more information.
    """

    def __eq__(self, value: object) -> bool:
        if isinstance(value, NetlistElement) and type(self) is type(value):
            return self.path == value.path and self.parameters == value.parameters and self.metadata == value.metadata
        return NotImplemented

    @property
    def path(self) -> ElementPath:
        """
        Returns the ElementPath of the netlist element.

        The ElementPath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            ElementPath: The hierarchical path of the netlist element.
        """
        return ElementPath(raw=self.raw_path)

    @property
    def name(self) -> str:
        """The name of the element."""
        return self.path.name

    @property
    def type(self) -> EType:
        """The type of the element, such as an instance, wire or port."""
        return EType.UNSPECIFIED

    @property
    def hierarchy_level(self) -> int:
        """
        The level of hierarchy of the element in the design.

        The hierarchy level is the number of separators in the element's raw path.
        For example, a top-level instance has a hierarchy level of 0, while a direct submodule instance has a hierarchy level of 1.

        Returns:
            int: The hierarchy level of the element.
        """
        return self.path.hierarchy_level

    @property
    def parent(self) -> NetlistElement:
        """
        The parent object of this object.

        -   For a port or wire segment, the parent is a port or a wire.
        -   For a port, the parent is either an instance (if it is an instance port) or a module.
        -   For a wire, the parent is a module.
        -   For an instance, the parent is either an instance again or a module.
        -   Modules do not have parents.
        """
        raise NotImplementedError(f'Not implemented for {self.type.name} objects by default! The problematic {self.type.value} is {self.raw_path}')

    @property
    def locked(self) -> bool:
        """
        True if this NetlistElement instance is locked (i.e. it is currently structurally unchangeable), False if it is mutable.

        Can be changed via `NetlistElement.change_mutability(bool)`.

        Immutability is used to prevent accidental changes to the design.
        """
        return self._locked

    @property
    def is_placeholder_instance(self) -> bool:
        """
        A placeholder represents an element that does not have a specific path.

        True if this NetlistElement instance represents a placeholder, False otherwise.
        """
        return self.path.is_empty

    @property
    def can_carry_signal(self) -> bool:
        """
        Whether this exact object is able to receive, pass or hold signal values.

        `True` for ports (as they drive or receive values) and wires (as they pass the signals
        from driver to load ports) as well as their respective segments.
        `False` for instances and modules.
        """
        return hasattr(self, 'signal')

    def set_name(self, new_name: str) -> None:
        """
        Sets the name of this object to the given value by updating its hierarchical path.

        To also update the path names of objects that are part of this object (e.g. segments),
        overwrite NetlistElement._set_name_recursively, which is called by this method.
        By doing so, the paths of all contained objects can be updated accordingly.

        Args:
            new_name (str): The new name to set to the object.
        """
        old_name = self.name
        if new_name != old_name:
            LOG.info(f'Changing instance name from object at {self.raw_path} from {self.name} to {new_name}!')
            new_raw_path = self.raw_path.split(self.path.sep)[:-1]
            new_raw_path.append(new_name)
            self.raw_path = self.path.sep.join(new_raw_path)
            self._set_name_recursively(old_name, new_name)

    def _set_name_recursively(self, old_name: str, new_name: str) -> None:
        """
        Hook method to replace all occurrences of `old_name` in all inner hierarchy paths with `new_name`.

        Can be used as a hook to update a certain value in the hierarchy paths of derivates from the NetlistElement class.
        Its main use is to synchronize contained elements after the name of a superordinate object is changed.
        This method is called by NetlistElement.set_name after the name of the object was updated accordingly.

        Implementation examples: `Module._set_name_recursively`, `Instance._set_name_recursively`,
        `Port._set_name_recursively` or `Wire._set_name_recursively`.

        Args:
            old_name (str): The old name to replace in the hierarchy paths of all subordinate objects.
            new_name (str): The new name to replace the old name with in the hierarchy paths of all subordinate objects.
        """
        pass

    def change_mutability(self, is_now_locked: bool) -> Self:
        """
        Change the mutability of this NetlistElement instance.

        Args:
            is_now_locked (bool): The new value for the element's mutability.
                True means, the element is now locked; False means, the element is mow mutable.

        Returns:
            NetlistElement: This instance with its mutability changed.
        """
        if is_now_locked != self.locked:
            LOG.debug(f'Changing mutability of {self.type.value} {self.name} to {is_now_locked}')
        self._locked = is_now_locked
        return self

    def add_listener(self, element: NetlistElementLike) -> None:
        """
        Add a listener to this element.

        Listeners are notified whenever the element changes (e.g. when a connection is added or removed, or a signal changes).
        The listener (another netlist element) is expected to have a method "on_notification" that takes one argument,
        which is the element sending the notification.
        The method should return True if the listener did something as a result of the notification, False otherwise.

        Args:
            element (NetlistElement): The element to add as a listener.
        """
        if element not in self._listeners:
            self._listeners.add(element)
        else:
            LOG.info(f'Did not add listener {element.raw_path} to {self.raw_path}: Listener already present!')

    def remove_listener(self, element: NetlistElementLike) -> None:
        """
        Remove a listener from this element.

        Listeners are notified whenever the element changes (e.g. when a connection is added or removed, or a signal changes).
        The listener (another netlist element) is expected to have a method "on_notification" that takes one argument,
        which is the element sending the notification.
        The method should return True if the listener did something as a result of the notification, False otherwise.

        Args:
            element (NetlistElement): The element to remove as a listener.

        Returns:
            bool: Whether the element was successfully removed as a listener.
        """
        if element in self._listeners:
            return self._listeners.remove(element)
        raise ObjectNotFoundError(f'Unable to remove listener {element.raw_path}: No such listener in {self.raw_path}!')

    def notify_listeners(self) -> bool:
        """
        Notify all listeners that this element has changed.

        Listeners are notified whenever the element changes (e.g. when a connection is added or removed, or a signal changes).
        The listener (another netlist element) is expected to have a method "on_notification" that takes one argument,
        which is the element sending the notification.
        The method should return True if the listener did something as a result of the notification, False otherwise.

        Returns:
            bool: Whether any listeners were notified.
        """
        for e in self._listeners:
            e.on_notification(self)
        return bool(self._listeners)

    def on_notification(self, element: NetlistElementLike) -> bool:
        """Called whenever an object changes, to which this object listens to.

        Args:
            element (NetlistElement): The object sending a notification to this object to do something.
                In general, "element" is another object requiring this object to update itself.

        Returns:
            bool: Whether anything was done subsequently to the notification.
        """
        return False

    def evaluate(self) -> None:
        """
        Evaluate the element depending on the incoming signals.

        This is used for instances, which have some sort of transfer function.
        The combination of input signals and the transfer function determine the output signal.
        For simple gate instances, such as AND and OR gates, this is trivial, as the transfer function is just a small truth table.
        Complex structures, like submodules, are comprised of other instances, which are evaluated recursively, down to the leaf instances,
        which in return are primitive gates.
        Thus, to evaluate a module, first all of its submodules and gates are evaluated, to calculate the output signals of the module.

        Raises:
            NotImplementedError: If this method is not implemented for the object's type.
        """
        raise NotImplementedError(f'Not implemented for {self.type.name} objects by default! The problematic {self.type.value} is {self.raw_path}')

    def normalize_metadata(
        self,
        include_empty: bool = False,
        sort_by: Literal['path', 'category'] = 'path',
        filter: Callable[[str, NESTED_DICT], bool] = lambda cat, md: True,
    ) -> METADATA_DICT:
        """
        Performs normalization of this element's metadata.

        This method simplifies the metadata of this object by re-formatting the metadata
        dictionary, mainly used when exporting the metadata.
        This is to ensure a coherent and unambiguous output by integrating the hierarchical path
        of this object (and all nested objects, if any).
        The dictionary can be sorted by paths (then the main dictionary key is the hierarchical path
        of the objects) or by category (in which case the main keys are the dictionary names).
        The dictionary can also be filtered by providing a callable that evaluates to a boolean
        value for which it may take metadata categories and the associated metadata dictionary, consisting of the
        metadata keys and associated metadata values.

        Args:
            include_empty (bool, optional): Whether to include objects without metadata into the normalized dictionary,
                in which case the value is just an empty dictionary. Defaults to False.
            sort_by (Literal["path", "category"], optional): Whether the hierarchical path or the metadata categories
                should be the main dictionary keys. Defaults to 'path'.
            filter (Callable[[str, NESTED_DICT], bool], optional): A filter function that takes two parameters, where
                the first represents the metadata category and the second represents the metadata dictionary.
                Defaults to `lambda cat, md: True`, which evaluates to True for all elements and thus does not filter
                anything.

        Returns:
            METADATA_DICT: A normalized metadata dictionary containing the metadata of this element and all nested objects.
        """

        def condition(cat: str, val: NESTED_DICT) -> bool:
            try:
                return (bool(val) or include_empty) and filter(cat, val)
            except AttributeError:
                return False

        if self.metadata.is_empty and not include_empty:
            return {}
        if sort_by == 'category':
            return {cat: {self.raw_path: val} for cat, val in self.metadata.items() if condition(cat, val)}
        return {self.raw_path: {cat: val for cat, val in self.metadata.items() if condition(cat, val)}}  # sort_by == 'path' or fallback

    def __hash__(self) -> int:
        return hash((self.name, self.type, self.raw_path))

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: {self.type.name} "{self.name}" with path {self.path.raw}'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name}: {self.type.name} at {self.path.raw})'
