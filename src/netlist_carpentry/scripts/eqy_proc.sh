#!/bin/bash

if [[ $2 != "" ]]
then
    top="hierarchy -top $2 -libdir ."
fi

yosys -p "
    read_verilog $1
    $top
    proc; opt; clean
    write_verilog $1
"
