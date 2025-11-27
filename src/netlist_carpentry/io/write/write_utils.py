"""Module for simple access of write methods to transform circuits from the internal representation into a Verilog text file."""

from pathlib import Path
from typing import Union

from netlist_carpentry import Circuit
from netlist_carpentry.io.write.py2v import P2VTransformer as P2V


def write(circuit: Circuit, output_file_path: Union[str, Path], overwrite: bool = False) -> None:
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    P2V().save_circuit2v(output_file_path.absolute(), circuit, overwrite)
