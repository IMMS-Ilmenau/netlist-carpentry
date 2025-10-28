from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import Sequence, Union

from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.scripts.script_builder import build_and_execute
from netlist_carpentry.utils.log import LOG


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

    This function also supports setting Verilog parameters using Mako for template processing.
    Accordingly, this function generates an intermediate (rendered) version of the given Verilog file, which is
    then used as source to generate the JSON netlist from.
    This is only relevant, if a module from the file has parameters, which can be set dynamically using the `parameters` parameter.
    Otherwise (if no module has parameters, or they are not specified in Mako syntax), the rendered version is equal to the provided file.
    See the description of the `parameters` parameter for more information.

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
    paths[0].parent.mkdir(parents=True, exist_ok=True)
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
