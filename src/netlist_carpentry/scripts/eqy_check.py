import os
import shutil
import subprocess
from pathlib import Path
from typing import List


class EqyWrapper:
    """
    Wrapper class for running Yosys EQY to prove the logical equivalence of two Verilog designs.
    It generates a .eqy script from a template and executes it using the Yosys EQY tool.
    """

    def __init__(self, path: str):
        """
        Initializes the EqyWrapper with the path to the directory with the Yosys EQY script.

        Args:
            path (str): The path to the directory where the .eqy script will be saved.
        """
        self.path = Path(path)
        """The path to the directory where the .eqy script will be saved."""

    def format_template(self, gold_vfile_paths: List[str], gold_top_module: str, gate_vfile_paths: List[str], gate_top_module: str) -> str:
        """
        Formats the EQY template string with the provided input parameters.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

        Args:
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (str): The top module name for the gold design.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (str): The top module name for the gate design.

        Returns:
            str: The formatted EQY template string.
        """
        template = """[gold]\n{gold_vsources}\n{gold_top_module}\nmemory_map\n\n[gate]\n{gate_vsources}\n{gate_top_module}\nmemory_map\n\n[strategy sat]\nuse sat\ndepth 10"""
        gold_vfiles = '\n'.join(f'read_verilog {p}' for p in gold_vfile_paths)
        gold_top_module = 'prep -top ' + gold_top_module if gold_top_module else ''
        gate_vfiles = '\n'.join(f'read_verilog {p}' for p in gate_vfile_paths)
        gate_top_module = 'prep -top ' + gate_top_module if gate_top_module else ''
        return template.format(gold_vsources=gold_vfiles, gold_top_module=gold_top_module, gate_vsources=gate_vfiles, gate_top_module=gate_top_module)

    def proc(self, gold_path: str, gold_top_module: str, gate_path: str, gate_top_module: str) -> None:
        dir_path = os.path.dirname(os.path.abspath(__file__))
        script_path = f'{dir_path}/eqy_proc.sh'
        subprocess.call(['chmod', 'u+x', script_path])
        subprocess.call([script_path, gold_path, gold_top_module], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.call([script_path, gate_path, gate_top_module], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def create_eqy_file(self, gold_vfile_paths: List[str], gold_top_module: str, gate_vfile_paths: List[str], gate_top_module: str) -> None:
        """
        Creates the EQY script file at the specified path.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.


        Args:
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (str): The top module name for the gold design.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (str): The top module name for the gate design.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            f.write(self.format_template(gold_vfile_paths, gold_top_module, gate_vfile_paths, gate_top_module))

    def run_eqy(self, output_path: str = os.getcwd(), remove_if_successful: bool = False, overwrite: bool = False) -> int:
        """
        Runs the Yosys EQY tool to prove the logical equivalence of the Verilog designs.

        The script for the equivalence check is the one specified in the `path` attribute of this class.

        If the parameter overwrite is set to True and the output directory exists already, it will be overwritten.
        If the directory exists, and the parameter is False or omitted, the equivalence checking script will fail with a corresponding error message.

        Args:
            output_path (str, optional): The path to the directory where the EQY tool will be executed. Defaults to the current working directory.
            remove_if_successful (bool, optional): Whether to remove the output directory after a successful equivalence proof. Defaults to False.
            overwrite (bool, optional): Whether to overwrite the output directory if it already exists. Defaults to False.

        Returns:
            int: The return code of the EQY tool. 0 if the equivalence proof was successful, otherwise a non-zero value along with an error message.
        """
        if overwrite and os.path.exists(output_path):
            shutil.rmtree(output_path, ignore_errors=True)
        dir_path = os.path.dirname(os.path.abspath(__file__))
        return_code = subprocess.call([f'{dir_path}/eqy.sh', self.path, output_path])
        if return_code == 0 and remove_if_successful:
            shutil.rmtree(output_path, ignore_errors=True)
        return return_code
