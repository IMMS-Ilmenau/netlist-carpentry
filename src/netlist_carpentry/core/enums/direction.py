"""Enum for the direction of a port in a digital circuit (input, output, inout, unknown)."""

from enum import Enum


class Direction(Enum):
    """
    Enum for the direction of a port (or a directed element in general) in a digital circuit.

    A port is a connection point in a circuit that can be connected to another element within the circuit.
    The direction of a port refers to the direction of data flow between the two connected elements.

    The direction of a port can be either input, output, or both input and output
    (inout).
    """

    IN = 'input'
    """This port direction refers to an input port."""
    OUT = 'output'
    """This port direction refers to an output port."""
    IN_OUT = 'inout'
    """This port direction refers to a port that can be used as both an input and an output port."""
    UNKNOWN = 'unknown'
    """This port direction refers to a port that has an unknown direction or unset."""

    @property
    def is_input(self) -> bool:
        """Returns True if this port direction is input or inout."""
        return self.value == 'input' or self.value == 'inout'

    @property
    def is_output(self) -> bool:
        """Returns True if this port direction is output or inout."""
        return self.value == 'output' or self.value == 'inout'

    @property
    def is_defined(self) -> bool:
        """Returns True if this port direction is input, output or inout; and False if it is unknown or no direction is specified."""
        return self.is_input or self.is_output

    def __str__(self) -> str:
        return self.value

    @classmethod
    def get(cls, value: str) -> 'Direction':
        """
        Retrieves a Direction enum member by its string value.

        If the provided string does not match any existing Direction values,
        it returns the UNKNOWN Direction instead of raising an exception.

        Args:
            value (str): The string value to look up in the Direction enum.

        Returns:
            Direction: The corresponding Direction enum member, or UNKNOWN if no match is found.

        Example:
            ```python
            >>> Direction.get('input')
            <Direction.IN: 'input'>
            >>> Direction.get('invalid_value')
            <Direction.UNKNOWN: 'unknown'>
            ```
        """
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN
