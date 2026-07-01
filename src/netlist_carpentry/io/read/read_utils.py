"""Module for simple access of read methods to transform circuits from a text file into Python objects."""

import subprocess
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import List, Optional, Union, overload

import netlist_carpentry.scripts.script_caller as sc
from netlist_carpentry import LOG, Circuit
from netlist_carpentry.core.exceptions import YosysError
from netlist_carpentry.io.read.yosys import ReadConfig
from netlist_carpentry.io.read.yosys.netlist_reader import YosysNetlistReader


def read_json(json_path: Union[str, Path], circuit_name: Optional[str] = None) -> Circuit:
    """
    Reads a JSON file and converts it to a Circuit object using the YosysNetlistReader.

    Args:
        json_path (Union[str, Path]): The path to the JSON file.
        circuit_name (Optional[str], optional): The name of the circuit to be created. Defaults to None, in which case the default name will be used.

    Returns:
        Circuit: A Circuit object representing the circuit defined in the JSON file.
    """
    return YosysNetlistReader(json_path).transform_to_circuit(circuit_name)


def read_via_cfg(cfg: ReadConfig, circuit_name: Optional[str] = None, verbose: bool = False) -> Circuit:
    """Reads a Verilog file and converts it to a Circuit object based on the given config.

    The config is used to create the Yosys script that generates the JSON netlist, which is then read
    by the `read_json` method, which produces a circuit object based on the content of the netlist.

    Args:
        cfg (ReadConfig): The Yosys config which contains the properties and passes that will be used when creating the JSON netlist.
        circuit_name (Optional[str], optional): The chosen name for this circuit. Defaults to None, in which case the circuit receives a generic name.
        verbose (bool, optional): Whether to show Yosys output. If True, all Yosys output is shown. Defaults to False.

    Raises:
        YosysError: Whenever Yosys fails to generate a JSON netlist. Also shows what exactly went wrong.

    Returns:
        Circuit: The circuit object represented in the JSON netlist that was generated via the given Yosys config.
    """
    with TemporaryDirectory() as tmpdir:
        if cfg.json_path is None:
            cfg.json_path = Path(tmpdir) / 'tmp.json'
        LOG.debug(f'Generating Yosys netlist from {len(cfg.files)} files...')
        start = time()
        gen_process = sc.call(cfg.shell_script(), verbose)
        errors = gen_process.stderr if gen_process.stderr is not None else ''
        if errors:
            LOG.error(str(errors))
        if int(gen_process.returncode) != 0:
            stdout = gen_process.stdout if gen_process.stdout else ''
            raise YosysError(f'Failed to generate JSON netlist:\n{stdout}\n{errors}')
        LOG.debug(f'Generated Yosys netlist from {len(cfg.files)} files in {round(time() - start, 2)}s!')
        return read_json(cfg.json_path, circuit_name)


def read(
    cfg_or_files: Union[ReadConfig, str, Path, List[Union[str, Path]]],
    top: Optional[str] = None,
    circuit_name: Optional[str] = None,
    verbose: bool = False,
    *,
    out: Union[str, Path, None] = None,
    source_paths: Optional[List[str]] = None,
    no_hierarchy: bool = False,
) -> Circuit:
    """
    Reads a Verilog file and converts it to a Circuit object.

    Under the hood, the Verilog file is first converted to a JSON file using Yosys, for which the config
    is built using `read_via_cfg` for the given parameters. The config is then used to create and run Yosys
    to create a JSON netlist, which is then read by the `read_json` function.
    The Circuit represented by the provided Verilog file is returned as a result.

    Args:
        cfg_or_files (Union[ReadConfig, str, Path, List[Union[str, Path]]], optional): The ReadConfig object containing
            data and settings required to read the circuit. Alternatively, a path to an RTL file (or a list of paths)
            can be provided, from which the circuit will then be built.
        top (str, optional): The name of the top-level module in the Verilog file. If not provided, no top module
            is set, which means that the circuit will not have a specified hierarchy until set manually via Circuit.set_top().
        circuit_name (str, optional): The name of the circuit to be created. If not provided, the default name will be used.
        verbose (bool, optional): Whether to show output from the Yosys tool. Defaults to False.
        out (Union[str, Path]): A path to a directory, where the generated JSON file will be located. Defaults to '', in which case
            the generated JSON netlist is saved in a temporary directory.
        source_paths (Optional[List[str]], optional): A list of paths to files to source before running Yosys.
            Can be used to enable plugins or activate environments, e.g. the OSS CAD SUITE.
            Defaults to None, in which case no additional files are sourced.
        no_hierarchy (bool, optional): Whether to resolve the hierarchy of the given circuit or not.
            If True, the yosys "hierarchy" path is skipped. Defaults to False.

    Returns:
        Circuit: A Circuit object representing the circuit defined in the Verilog file.
    """
    if isinstance(cfg_or_files, ReadConfig):
        if any([top, out, source_paths, no_hierarchy]):
            raise ValueError(
                'If a ReadConfig is given to `read()`, all other reading-related arguments must remain unset (top, out, source_paths, no_hierarchy)!'
            )
    else:
        if isinstance(cfg_or_files, (str, Path)):
            paths = [Path(cfg_or_files).resolve()]
        else:
            paths = [Path(p).resolve() for p in cfg_or_files]

        if not paths:
            raise ValueError('No verilog paths provided!')
        output = Path(out) if out else None
        if output is not None and output.is_dir():
            output /= paths[0].stem + '.json'
        envs = [Path(p) for p in source_paths] if source_paths else None
        cfg_or_files = ReadConfig(files=paths, output=output, top=top, no_hierarchy=no_hierarchy, environments=envs)
    return read_via_cfg(cfg_or_files, circuit_name, verbose)


@overload
def generate_json(
    cfg_or_files: List[Path], yosys_script_path: Optional[Path] = None, verbose: bool = False, overwrite: bool = False
) -> subprocess.CompletedProcess[str]: ...
@overload
def generate_json(
    cfg_or_files: ReadConfig, yosys_script_path: Optional[Path] = None, verbose: bool = False, overwrite: bool = False
) -> subprocess.CompletedProcess[str]: ...
def generate_json(
    cfg_or_files: Union[ReadConfig, List[Path]], yosys_script_path: Optional[Path] = None, verbose: bool = False, overwrite: bool = False
) -> subprocess.CompletedProcess[str]:
    if isinstance(cfg_or_files, list):
        if not cfg_or_files:
            raise YosysError('Cannot create JSON netlist: The given file list is empty!')
        cfg_or_files = ReadConfig(files=cfg_or_files)
    if not cfg_or_files.json_path:
        cfg_or_files.json_path = cfg_or_files.files[0].parent / (cfg_or_files.files[0].stem + '.json')
    if cfg_or_files.json_path.exists() and not overwrite:
        raise FileExistsError(f'Cannot create JSON netlist: A file {cfg_or_files.json_path!r} already exists!')
    LOG.info(f'Generating JSON netlist at {cfg_or_files.json_path!r}...')
    return sc.call(cfg_or_files.shell_script(yosys_script_path), verbose)


def generate_json_netlist(
    input_file_path: Union[str, Path],
    output_file_path: Union[str, Path],
    top_module_name: str = '',
    verbose: bool = False,
    yosys_script_path: Union[str, Path] = '',
    no_hierarchy: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Generate a JSON netlist from the given input file using Yosys.

    Args:
        input_file_path (Union[str, Path]): Path to the input Verilog file.
        output_file_path (Union[str, Path]): Path where the output JSON netlist should be saved.
        top_module_name (str, optional): The name of the top module. Defaults to ''.
        verbose (bool, optional): Whether to print Yosys log to the console. Defaults to False.
        yosys_script_path (Union[str, Path], optional): Path to a custom Yosys synthesis script.
            If empty, an appropriate script is generated with common synthesis settings. Defaults to ''.
        no_hierarchy (bool, optional): Whether to resolve the hierarchy of the given circuit or not.
            If True, the yosys "hierarchy" path is skipped. Defaults to False.

    Returns:
        subprocess.CompletedProcess[str]: The return object of the subprocess that executed Yosys.
    """
    warnings.warn(
        "'generate_json_netlist()' is deprecated and will be removed in v1.0.0. Call `generate_json` with a `ReadConfig` object with the corresponding data (or simply with the RTL files) instead!",
        DeprecationWarning,
        stacklevel=2,
    )
    if isinstance(input_file_path, str):
        input_file_path = Path(input_file_path)
    if isinstance(output_file_path, str):
        output_file_path = Path(output_file_path)
    output_dir = output_file_path.parent
    output_dir.mkdir(exist_ok=True)
    top = top_module_name or None
    rc = ReadConfig(files=[input_file_path], output=output_file_path, top=top, no_hierarchy=no_hierarchy)
    return generate_json(rc, Path(yosys_script_path) if yosys_script_path else None, verbose=verbose, overwrite=True)
