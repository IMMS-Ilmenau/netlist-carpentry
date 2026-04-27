import subprocess
from typing import Dict, List, Optional


def call(cmds: List[str], verbose: bool, env: Optional[Dict[str, str]] = None) -> subprocess.Popen[str]:
    return subprocess.run(' '.join(cmds), shell=True, capture_output=not verbose, text=True, env=env)
