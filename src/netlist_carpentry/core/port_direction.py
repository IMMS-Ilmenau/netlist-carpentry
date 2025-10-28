from enum import Enum


class PortDirection(Enum):
    """
    Enum for the direction of a port in a digital circuit.

    A port is a connection point on a digital circuit that can be connected to another digital circuit.
    The direction of a port refers to the direction of data flow between the two connected circuits.

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
    def get(cls, value: str) -> 'PortDirection':
        """
        Retrieves a PortDirection enum member by its string value.

        If the provided string does not match any existing PortDirection values,
        it returns the UNKNOWN PortDirection instead of raising an exception.

        Args:
            value (str): The string value to look up in the PortDirection enum.

        Returns:
            PortDirection: The corresponding PortDirection enum member, or UNKNOWN if no match is found.

        Example:
            ```python
            >>> PortDirection.get('input')
            <PortDirection.IN: 'input'>
            >>> PortDirection.get('invalid_value')
            <PortDirection.UNKNOWN: 'unknown'>
            ```
        """
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN
