"""Module for simple access of read methods to transform circuits from a text file into Python objects."""

import subprocess
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import Sequence, Union

from netlist_carpentry import LOG, Circuit
from netlist_carpentry.io.read.yosys_netlist import YosysNetlistReader
from netlist_carpentry.scripts.script_builder import build_and_execute


def read_json(json_path: Union[str, Path], circuit_name: str = '') -> Circuit:
    """
    Reads a JSON file and converts it to a Circuit object using the YosysNetlistReader.

    Args:
        json_path (Union[str, Path]): The path to the JSON file.
        circuit_name (str, optional): The name of the circuit to be created. If not provided, the default name will be used.

    Returns:
        Circuit: A Circuit object representing the circuit defined in the JSON file.
    """
    return YosysNetlistReader(json_path).transform_to_circuit(circuit_name)


def read(
    verilog_paths: Union[str, Path, Sequence[Union[str, Path]]],
    top: str = '',
    circuit_name: str = '',
    verbose: bool = False,
    out: Union[str, Path] = '',
) -> Circuit:
    """
    Reads a Verilog file and converts it to a Circuit object using the YosysNetlistReader.

    The Verilog file is first converted to a JSON file using Yosys (via the generate_json_netlist function),
    which is then read by the read_json function.
    The Circuit represented by the provided Verilog file is returned as a result.

    Args:
        verilog_paths (Union[str, Path]): The path to the Verilog file. Alternatively, a list of paths.
        top (str, optional): The name of the top-level module in the Verilog file. If not provided, no top module
            is set, which means that the circuit will not have a specified hierarchy until set manually via Circuit.set_top().
        circuit_name (str, optional): The name of the circuit to be created. If not provided, the default name will be used.
        verbose (bool, optional): Whether to show output from the Yosys tool. Defaults to False.
        out (Union[str, Path]): A path to a directory, where the generated JSON file will be located. Defaults to '', in which case
            the generated JSON netlist is saved in a temporary directory.

    Returns:
        Circuit: A Circuit object representing the circuit defined in the Verilog file.
    """
    if isinstance(verilog_paths, (str, Path)):
        paths = [Path(verilog_paths).resolve()]
    else:
        paths = [Path(p).resolve() for p in verilog_paths]

    if not paths:
        raise ValueError('No verilog paths provided!')
    with TemporaryDirectory() as tmpdirname:
        out_path = Path(out) if out else Path(tmpdirname)
        script_path = out_path / 'gen_json.sh'
        json_path = out_path / f'{paths[0].stem}.json'
        LOG.info(f'Generating Yosys netlist from {len(paths)} files...')
        start = time()
        gen_process = build_and_execute(script_path, paths, json_path, verbose=verbose, top=top)
        LOG.info(f'Generated Yosys netlist from {len(paths)} files in {round(time() - start, 2)}s!')
        if gen_process.stderr:
            for err in gen_process.stderr.decode().splitlines():
                LOG.error(err)
        if gen_process.returncode != 0:
            stdout = gen_process.stdout.decode() if gen_process.stdout else ''
            raise RuntimeError(f'Failed to generate JSON netlist:\n{stdout}\n{gen_process.stderr.decode()}')
        return read_json(json_path, circuit_name)


def generate_json_netlist(
    input_file_path: Union[str, Path],
    output_file_path: Union[str, Path],
    top_module_name: str = '',
    verbose: bool = False,
    yosys_script_path: Union[str, Path] = '',
) -> subprocess.CompletedProcess[bytes]:
    """Generate a JSON netlist from the given input file using Yosys.

    Args:
        input_file_path (Union[str, Path]): Path to the input Verilog file.
        output_file_path (Union[str, Path]): Path where the output JSON netlist should be saved.
        top_module_name (str, optional): The name of the top module. Defaults to ''.
        verbose (bool, optional): Whether to print Yosys log to the console. Defaults to False.
        yosys_script_path (Union[str, Path], optional): Path to a custom Yosys synthesis script.
            If empty, an appropriate script is generated with common synthesis settings. Defaults to ''.

    Returns:
        subprocess.CompletedProcess[bytes]: The return object of the subprocess that executed Yosys.
    """
    from netlist_carpentry import NC_SCRIPTS_DIR

    pmux2mux_path = Path(NC_SCRIPTS_DIR + '/hdl/pmux2mux.v')
    if isinstance(input_file_path, str):
        input_file_path = Path(input_file_path)
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    output_dir = output_file_path.parent
    output_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile('w', delete_on_close=False) as tmp:  # type: ignore[call-overload, misc]
        path = Path(tmp.name) if not yosys_script_path else Path(yosys_script_path)  # type: ignore[misc]
        tmp.close()  # type: ignore[misc]
        return build_and_execute(path, [input_file_path], output_file_path, verbose=verbose, top=top_module_name, techmap_paths=[pmux2mux_path])  # type: ignore[misc]
