#!/bin/bash

#   $1: Path to the .eqy file containing the gold and gate configuration for the equivalence check
#       For more information, consult the official wiki: https://yosyshq.readthedocs.io/projects/eqy/en/latest/quickstart.html
#   $2: Output directory, into which the generated files will be output
#       Is automatically generated if not present

# Execute equivalence check using EQY, put output files into the specified output directory
eqy $1 -d $2
