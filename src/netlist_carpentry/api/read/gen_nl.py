import subprocess
from pathlib import Path
from typing import Union

from netlist_carpentry import NC_SCRIPTS_DIR


def generate_json_netlist(
    input_file_path: Union[str, Path],
    output_file_path: Union[str, Path],
    top_module_name: str = '',
    verbose: bool = False,
    yosys_script_path: Union[str, Path] = '',
) -> subprocess.CompletedProcess[bytes]:
    stdout = None if verbose else subprocess.PIPE
    if yosys_script_path != '':
        return subprocess.run(yosys_script_path, stdout=stdout, stderr=subprocess.PIPE)
    pmux2mux_path = NC_SCRIPTS_DIR + '/hdl/pmux2mux.v'
    if isinstance(input_file_path, str):
        input_file_path = Path(input_file_path)
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    input_dir = input_file_path.parent
    hdl_file_name = input_file_path.name
    output_dir = output_file_path.parent
    output_dir.mkdir(exist_ok=True)
    yosys_script_path = Path(f'{NC_SCRIPTS_DIR}/verilogToJsonSimple.sh')
    cmd = [yosys_script_path, input_dir, hdl_file_name, output_file_path, pmux2mux_path, top_module_name]
    return subprocess.run(cmd, stdout=stdout, stderr=subprocess.PIPE)
