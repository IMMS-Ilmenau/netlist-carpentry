from enum import Enum
from typing import Optional, Union


class EType(Enum):
    """An enumeration representing the possible types of netlist elements."""

    UNSPECIFIED = 'unspecified'
    """An unspecified element type. This is the default type for newly created elements."""
    MODULE = 'module'
    """A module element type. This is a top-level element that can contain other elements."""
    INSTANCE = 'instance'
    """An instance element type. This could be an instance of a complex module or a primitive gate."""
    PORT = 'port'
    """A port element type. This is an input or output of a module or an instance."""
    PORT_SEGMENT = 'port_segment'
    """A port segment element type. This is a part of a port, if the port consists of multiple bits."""
    WIRE = 'wire'
    """A wire element type. This is a connection between two ports."""
    WIRE_SEGMENT = 'wire_segment'
    """A wire segment element type. This is a part of a wire, if the wire consists of multiple bits."""

    @property
    def can_carry_signal(self) -> bool:
        """
        Whether elements of this type can carry signals.

        Only Ports (or their segments) and Wires (or their segments) can carry signals.
        Thus, this property is only `True` for these types.
        This property is `False` for Modules, Instances or elements with unspecified type.
        """
        return self in [EType.PORT, EType.PORT_SEGMENT, EType.WIRE, EType.WIRE_SEGMENT]

    @property
    def is_segment(self) -> bool:
        """
        Whether this element type represents a segment of another element.

        This property is `True` for PortSegments and WireSegments, and `False` for all other types.
        """
        return self in [EType.PORT_SEGMENT, EType.WIRE_SEGMENT]


def get_class(element: Union[str, Enum]) -> Optional[type]:
    """
    Get the class associated with the given element type.

    Args:
        element: The type of element for which to get the class. This can be either an
            `ElementsEnum` instance or a string representing the element type.

    Returns:
        The class associated with the given element type, or `None` if the element type
        is not recognized.

    Raises:
        ValueError: If the given element type is not recognized.
    """
    from netlist_carpentry.core.netlist_elements.instance import Instance
    from netlist_carpentry.core.netlist_elements.module import Module
    from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
    from netlist_carpentry.core.netlist_elements.port import Port
    from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
    from netlist_carpentry.core.netlist_elements.wire import Wire
    from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment

    # Map each element type to its corresponding class
    ELEMENT_CLASS_MAP = {
        EType.UNSPECIFIED: NetlistElement,
        EType.MODULE: Module,
        EType.INSTANCE: Instance,
        EType.PORT: Port,
        EType.PORT_SEGMENT: PortSegment,
        EType.WIRE: Wire,
        EType.WIRE_SEGMENT: WireSegment,
    }

    # If the element type is given as a string, convert it to an ElementsEnum instance
    if isinstance(element, str):
        try:
            element = EType(element)
        except ValueError:
            raise ValueError(f'Invalid element type: {element}')

    # Return the class corresponding to the given element type
    return ELEMENT_CLASS_MAP.get(EType(element))
