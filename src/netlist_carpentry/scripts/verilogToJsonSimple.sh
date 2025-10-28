#!/bin/bash

# $1: input directory - where the files can be found
cd $1
ext=""
# File has SystemVerilog syntax -> put "-sv" after "read_verilog"
if [[ $2 == *.sv ]]
then
    ext="-sv "
fi

if [[ $5 != "" ]]
then
    top="hierarchy -top $5 -libdir ."
fi

yosys -p "
    read_verilog $ext$2
    $top
    proc
    memory
    techmap -map $4
    opt; clean; check
    insbuf
    proc
    write_json $3
"
