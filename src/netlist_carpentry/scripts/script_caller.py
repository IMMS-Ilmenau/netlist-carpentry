import shutil
import subprocess
from typing import Dict, List, Optional, Union

from netlist_carpentry import ON_WINDOWS


def call(cmds: List[str], verbose: bool, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    """Runs the given commands in a subprocess and returns the completed process.

    On Windows, the commands are passed as a list to PowerShell; on Linux/macOS, they are
    joined into a single string and executed via `bash`. Output is captured unless `verbose` is True,
    in which case it is streamed to the console.

    Args:
        cmds (List[str]): The commands to execute. On Windows, the list is passed as-is;
            on Linux/macOS, the elements are joined with spaces into a single shell string.
        verbose (bool): Whether to stream the process output to the console instead of capturing it.
        env (Optional[Dict[str, str]], optional): The environment variables for the subprocess.
            If None, the current environment is inherited. Defaults to None.

    Returns:
        subprocess.CompletedProcess[str]: The completed process, with stdout and stderr available
            when the output was captured (i.e. `verbose` is False).
    """
    formatted_cmds: Union[str, List[str]] = cmds if ON_WINDOWS else ' '.join(cmds)
    executable = shutil.which('bash') if not ON_WINDOWS else None
    return subprocess.run(formatted_cmds, shell=not ON_WINDOWS, capture_output=not verbose, text=True, env=env, executable=executable)


def prepare_call(script: str) -> List[str]:
    """Prepares a shell script for execution by :meth:`call`, adding fail-on-error behavior.

    Prepends `set -e` (Linux/macOS) or `$ErrorActionPreference = 'Stop'` (Windows) to the script,
    so that the shell aborts on the first failing command. On Windows, the script is wrapped in a
    `powershell.exe` invocation; on Linux/macOS, it is returned as a single-element list for bash.

    Args:
        script (str): The shell script content to prepare.

    Returns:
        List[str]: The prepared commands, ready to be passed to `call`.
    """
    fail_on_error = "$ErrorActionPreference = 'Stop'" if ON_WINDOWS else 'set -e'
    script = f'{fail_on_error}\n{script}'
    if ON_WINDOWS:
        # Windows --> PowerShell
        return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script]
    else:
        # Linux/macOS --> bash
        return [script]
