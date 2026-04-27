import subprocess
from typing import Dict, List, Optional


def call(cmds: List[str], verbose: bool, env: Optional[Dict[str, str]] = None) -> subprocess.Popen[str]:
    stdout = None if verbose else subprocess.PIPE
    stderr = None if verbose else subprocess.PIPE
    result = subprocess.Popen(' '.join(cmds), shell=True, stdout=stdout, stderr=stderr, text=True, env=env)
    if verbose and result.stdout is not None:
        for line in result.stdout:
            print(line, end='')
    result.wait()
    return result
