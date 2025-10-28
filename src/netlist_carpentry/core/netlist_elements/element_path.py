from typing import List, Optional, Union

from pydantic import BaseModel, NonNegativeInt
from typing_extensions import Self

from netlist_carpentry.core.netlist_elements.element_type import EType


class ElementPath(BaseModel):
    """
    Represents a path to a specific element in a netlist.

    Attributes:
        type (ElementsEnum): The type of the element.
        raw (str): The raw path string representing the element location.
        separator (str): The separator used in the path. Defaults to '.'.

    Example 1:
        ```python
        >>> element_path = PortPath(raw="top_module.sub_module.port1")
        >>> print(element_path)
        "PortPath(top_module.sub_module.port1)"
        ```

    Example 2:
        ```python
        >>> element_path = InstancePath(raw="top_module/sub_module/instance1", separator='/')
        >>> print(element_path)
        "InstancePath(top_module/sub_module/instance1)"
        ```
    """

    raw: str
    """The raw path string representing the element location."""
    sep: str = '.'
    """The separator used in the path. Defaults to '.'."""

    @property
    def type(self) -> EType:
        """The type of the element."""
        return EType.UNSPECIFIED

    @property
    def parts(self) -> List[str]:
        """
        Splits the raw path into a list of components via the specified separator.


        Returns:
            List[str]: A list of strings representing the split path components.
        """
        return list(filter(None, self.raw.split(self.sep)))

    @property
    def type_mapping(self) -> List[tuple[str, EType]]:
        """
        Calculates a mapping of path components to element types.

        This is a heuristic approach, assuming the first element is a module name
        and the last element is of the type of this path. Intermediate elements
        are mapped to instances (since they are most probably module instances)
        and/or to their superordinate types (e.g. the second-to-last element is
        presumably a port, if the last element in the path is a port segment).

        Returns:
            List[tuple[str, EType]]: A list of tuples, where each tuple contains
            a path component and its presumably corresponding element type.
        """
        # Heuristic: 1st element is a module name, every following element is an instance
        # Last element is of the type path.type
        # In case last element is a segment (port or wire segment),
        # the second-to-last element is of the superordinate type (port or wire)
        mapping = [(p, EType.INSTANCE) for p in self.parts]
        if mapping:
            mapping[0] = (mapping[0][0], EType.MODULE)
            mapping[-1] = (mapping[-1][0], self.type)
            if self.type == EType.PORT_SEGMENT:
                mapping[-2] = (mapping[-2][0], EType.PORT)
            if self.type == EType.WIRE_SEGMENT:
                mapping[-2] = (mapping[-2][0], EType.WIRE)

        return mapping

    @property
    def name(self) -> str:
        """The name of the element, i.e. the key of this element path."""
        return self.get(-1)

    @name.setter
    def name(self, new_name: str) -> None:
        new_raw_path = self.parts[:-1]
        new_raw_path.append(new_name)
        self.raw = self.sep.join(new_raw_path)

    @property
    def parent(self) -> 'ElementPath':
        """
        Retrieves the parent element path of this element.

        The parent is determined by removing the last component from the path.
        The type of the parent is inferred from the type mapping, specifically
        using the second-to-last element's mapped type.

        Returns:
            ElementPath: A new instance of the appropriate ElementPath subclass
                representing the parent element.

        Raises:
            IndexError: If this path does not have a parent (i.e., it has only one component or is empty).
        """
        if len(self.parts) <= 1:
            raise IndexError(f'Path {self.raw} does not have a parent!')
        p = self.sep.join(self.parts[:-1])
        parent_type = self.type_mapping[-2][1]
        parent_path_object = TYPES2PATHS[parent_type]
        return parent_path_object(raw=p)

    @property
    def hierarchy_level(self) -> int:
        """
        The hierarchy level of the element, i.e. the number of times the separator appears in the path.

        For empty paths, the hierarchy level is -1.

        Example 1:
            ```python
            >>> element_path = PortPath(raw="top_module.sub_module.port1")
            >>> print(element_path.hierarchy_level)
            2
            ```

        Example 2:
            ```python
            >>> element_path = InstancePath(raw="top_module/instance1", separator='/')
            >>> print(element_path.hierarchy_level)
            1
            ```

        Example 3:
            ```python
            >>> element_path = ElementPath(raw="")
            >>> print(element_path.hierarchy_level)
            -1
            ```
        """
        return len(self) - 1

    @property
    def is_empty(self) -> bool:
        """Whether this path consists of no characters and thus represents an empty string."""
        return self.raw == ''

    def __getitem__(self, index: int) -> str:
        return self.parts[index]

    def __len__(self) -> int:
        return len(self.parts)

    def __eq__(self, value: object) -> bool:
        if isinstance(value, ElementPath):
            return self.raw.split(self.sep) == value.raw.split(value.sep) and self.type == value.type
        if isinstance(value, str):
            return self.raw == value
        return False

    def nth_parent(self, index: NonNegativeInt) -> 'ElementPath':
        """
        Retrieves the nth parent of this element path.

        The 0th parent is the element itself.
        For example, if this path represents "module.instance.port",
        then:
        - nth_parent(0) returns the same path ("module.instance.port")
        - nth_parent(1) returns the parent path ("module.instance")
        - nth_parent(2) returns the grandparent path ("module")

        Args:
            index (NonNegativeInt): The level of the parent to retrieve.
                0 means self, 1 means immediate parent, etc.

        Returns:
            ElementPath: A new instance of the appropriate ElementPath subclass
                representing the nth parent element.

        Raises:
            IndexError: If the requested parent level exceeds the hierarchy depth.
        """
        if index == 0:
            return self
        else:
            return self.parent.nth_parent(index - 1)

    def has_parent(self, index: NonNegativeInt = 1) -> bool:
        """
        Whether the nth parent of this element path exists.

        The 0th parent is the element itself.
        For example, if this path represents "module.instance.port",
        then:
        - has_parent(0) will always return True
        - has_parent(1) returns True as well ("module.instance")
        - has_parent(2) returns True as well ("module")
        - has_parent(3) returns False (no hierarchy left)

        Args:
            index (NonNegativeInt): The level of the parent to check.
                0 means self, 1 means immediate parent, etc.

        Returns:
            bool: True if the parent exists, False otherwise
        """
        try:
            self.nth_parent(index)
        except Exception:
            return False
        return True

    def get(self, index: int) -> str:
        """
        Returns the element at the specified index in the path.

        For an Elementpath `some_path`, `some_path.get(i)` is similar to `some_path[i]`, except `some_path[i]` raises
        an `IndexError` exception for invalid indices, where `some_path.get(i)` returns an empty string.

        Negative indices count from the end, with -1 being the last element (i.e. the target of this path).
        For wire or port segments, -1 is the segment itself, -2 is the wire or port the segment belongs to,
        and -3 is the instance or module to which the wire or port belongs.

        Positive indices count from the start of the path, with 0 being the name of a module (e.g. the top-level module).
        Index 1 is thus an instance, port or wire within the top-level module.
        In case, the object at index 1 is an instance, index 2 could then be a port, wire or another instance.
        The latter two however are only available if the instance represents a submodule and not a primitive structure.

        Example 1:
            ```python
            >>> element_path = PortPath(raw="top_module.sub_module.port1")
            >>> print(element_path.get(-1))
            port1
            ```

        Example 2:
            ```python
            >>> element_path = InstancePath(raw="top_module/instance1", separator='/')
            >>> print(element_path.get(0))
            top_module
            ```

        Example 3:
            ```python
            >>> element_path = InstancePath(raw="top_module/instance1", separator='/')
            >>> print(element_path.get(-69420))
            ""
            ```
        """
        try:
            return self[index]
        except IndexError:
            return ''

    def get_subseq(self, lower_idx: Optional[int], upper_idx: Optional[int]) -> List[str]:
        """
        Returns a sublist of elements from the raw path.

        This is useful when you need to extract a subset of elements from the full path,
        such as getting all instances or modules up to a certain level, or extracting a specific
        segment from a wire or port path.

        Args:
            lower_idx (Optional[int]): The starting index (inclusive) for slicing the list.
                If None, this conforms to an unset lower bound, i.e. `[ : ...`.
            upper_idx (Optional[int]): The ending index (exclusive) for slicing the list.
                If None, this conforms to an unset upper bound, i.e. `... : ]`.

        Returns:
            list: A list of strings representing the subsequence of elements in the raw path.

        """
        return self.parts[lower_idx:upper_idx]

    def replace(self, old: str, new: str) -> Self:
        elements = self.raw.split(self.sep)
        if old in elements:
            elements[elements.index(old)] = new
            self.raw = self.sep.join(elements)
        return self

    def is_type(self, type: EType) -> bool:
        """Returns whether the type of this path matches the given element type.

        If this path is an InstancePath and the given type is `EType.INSTANCE`, returns True.
        Returns False for all other types.
        Works analogously for all other types, depending on the given type and the value of
        `ElementPath.type`.

        Args:
            type (EType): The type to compare the type of this ElementPath with.

        Returns:
            bool: Whether the given type matches the actual type of this path.
        """
        return type is self.type

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.raw})'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__} {self.raw}'

    def __hash__(self) -> int:
        return hash((self.type, self.raw))


class ModulePath(ElementPath):
    """Represents a path to a module."""

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.MODULE` for instances of ModulePath."""
        return EType.MODULE


class InstancePath(ElementPath):
    """Represents a hierarchical path to an instance."""

    @property
    def parent(self) -> Union[ModulePath, 'InstancePath']:
        return super().parent  # type: ignore[return-value]

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.INSTANCE` for instances of InstancePath."""
        return EType.INSTANCE


class PortPath(ElementPath):
    """Represents a hierarchical path to a port."""

    @property
    def parent(self) -> Union[ModulePath, InstancePath]:
        return super().parent  # type: ignore[return-value]

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.PORT` for instances of PortPath."""
        return EType.PORT

    @property
    def is_instance_port(self) -> bool:
        """
        Whether this port path points to an instance port (then True) or a module port (then False).

        Checks whether the parent path of this path is an instance path (in which case this port is
        an instance port) or not (in which case it is a module port).
        """
        return isinstance(self.parent, InstancePath)


class PortSegmentPath(ElementPath):
    """Represents a hierarchical path to a port segment."""

    @property
    def parent(self) -> PortPath:
        return super().parent  # type: ignore[return-value]

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.PORT_SEGMENT` for instances of PortSegmentPath."""
        return EType.PORT_SEGMENT

    @property
    def is_instance_port(self) -> bool:
        """
        Whether this port segment path points to an instance port segment (then True) or a module port segment (then False).

        Checks whether the parent path of this path is an instance port path (in which case this port segment belongs to
        an instance port) or not (in which case it belongs to a module port).
        """
        return self.parent.is_instance_port


class WirePath(ElementPath):
    """Represents a hierarchical path to a wire."""

    @property
    def parent(self) -> ModulePath:
        return super().parent  # type: ignore[return-value]

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.WIRE` for instances of WirePath."""
        return EType.WIRE


class WireSegmentPath(ElementPath):
    """Represents a hierarchical path to a wire segment."""

    @property
    def parent(self) -> WirePath:
        return super().parent  # type: ignore[return-value]

    @property
    def type(self) -> EType:
        """The type of the element, which is `EType.WIRE_SEGMENT` for instances of WireSegmentPath."""
        return EType.WIRE_SEGMENT


T_PATH_TYPES = Union[ElementPath, InstancePath, PortPath, PortSegmentPath, WirePath, WireSegmentPath]
TYPES2PATHS: dict[EType, type[ElementPath]] = {
    EType.MODULE: ModulePath,
    EType.INSTANCE: InstancePath,
    EType.PORT: PortPath,
    EType.PORT_SEGMENT: PortSegmentPath,
    EType.WIRE: WirePath,
    EType.WIRE_SEGMENT: WireSegmentPath,
}
