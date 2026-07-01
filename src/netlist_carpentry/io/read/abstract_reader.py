"""Base module for reading circuit content from a text file."""

from pathlib import Path
from typing import Optional, Union

from netlist_carpentry.core.circuit import Circuit


class AbstractReader:
    """Abstract class for reading circuit content from a text file.

    An implementation example is given with the `netlist_carpentry.io.read.yosys.YosysNetlistReader` class,
    which reads Yosys-generated JSON netlists and transforms the read content into a `Circuit` object.
    """

    def __init__(self, path: Union[str, Path]):
        if isinstance(path, str):
            path = Path(path)
        self.path = path

    def read(self) -> object:
        """Reads a circuit design file and returns a dict-like data structure containing the raw circuit data.

        Not implemented in the base class `AbstractReader`, must be implemented in derived classes.
        See the implementation in the `netlist_carpentry.io.read.yosys.YosysNetlistReader` class for an example.

        Raises:
            NotImplementedError: Not implemented in the base class, must be implemented in derived classes.

        Returns:
            object: A dict-like data structure containing the raw circuit data. May be processed by the
                `transform_to_circuit()` method to retrieve a `Circuit` object.
        """
        raise NotImplementedError('Not implemented in abstract class!')

    def transform_to_circuit(self, name: Optional[str] = None) -> Circuit:
        """This method transforms the content read via the `read` function into a Circuit.

        Not implemented in the base class `AbstractReader`, must be implemented in derived classes.
        See the implementation in the `netlist_carpentry.io.read.yosys.YosysNetlistReader` class for an example.

        Args:
            name (Optional[str], optional): A circuit name. If None, a generic name is given. Defaults to None.

        Raises:
            NotImplementedError: Not implemented in the base class, must be implemented in derived classes.

        Returns:
            Circuit: The circuit with the elements as described in the read circuit design file.
        """
        raise NotImplementedError('Not implemented in abstract class!')
