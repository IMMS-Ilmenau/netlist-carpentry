"""Module to generate a JSON netlist from given input files."""

import subprocess
import tempfile
from pathlib import Path
from typing import Union

from netlist_carpentry import NC_SCRIPTS_DIR
from netlist_carpentry.scripts.script_builder import build_and_execute


def generate_json_netlist(
    input_file_path: Union[str, Path],
    output_file_path: Union[str, Path],
    top_module_name: str = '',
    verbose: bool = False,
    yosys_script_path: Union[str, Path] = '',
) -> subprocess.CompletedProcess[bytes]:
    pmux2mux_path = Path(NC_SCRIPTS_DIR + '/hdl/pmux2mux.v')
    if isinstance(input_file_path, str):
        input_file_path = Path(input_file_path)
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    output_dir = output_file_path.parent
    output_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile('w', delete_on_close=False) as tmp:
        path = Path(tmp.name) if not yosys_script_path else Path(yosys_script_path)
        tmp.close()
        return build_and_execute(path, [input_file_path], output_file_path, verbose=verbose, top=top_module_name, techmap_paths=[pmux2mux_path])
