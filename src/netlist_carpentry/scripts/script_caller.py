import subprocess
from typing import List


def call(cmds: List[str], verbose: bool) -> subprocess.Popen[str]:
    out_target = subprocess.PIPE if verbose else subprocess.DEVNULL
    result = subprocess.Popen(' '.join(cmds), shell=True, stdout=out_target, stderr=subprocess.STDOUT, text=True)
    if verbose and result.stdout is not None:
        for line in result.stdout:
            print(line, end='')
    result.wait()
    return result
