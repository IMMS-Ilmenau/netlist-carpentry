from pathlib import Path
from typing import Union

from netlist_carpentry.api.write.py2v import P2VTransformer as P2V
from netlist_carpentry.core.circuit import Circuit


def write(circuit: Circuit, output_file_path: Union[str, Path], overwrite: bool = False) -> None:
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    if output_file_path.is_dir():
        output_file_path /= f'{circuit.name}.v'
    P2V().save_circuit2v(output_file_path.absolute(), circuit, overwrite)
