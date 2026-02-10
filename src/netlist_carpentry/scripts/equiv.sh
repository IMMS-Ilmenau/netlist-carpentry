#!/bin/bash

yosys -p "
read_verilog $1 # Load the "Gold" (Reference) design
prep -top $2 -flatten
design -stash gold

read_verilog $3 # Load the "Gate" (Implementation) design
prep -top $4 -flatten
design -stash gate

# Create the Equivalence Miter (new module 'equiv') by matching ports of 'gold' and 'gate'
design -copy-from gold -as gold $2
design -copy-from gate -as gate $4
equiv_make gold gate equiv
hierarchy -top equiv

flatten
chformal -early # Prepares formal cells for equivalence check
async2sync      # Resolves async FFs into synced FF (since it happens in both designs, equality is preserved)
equiv_simple    # Simple combinational equivalence
equiv_struct    # Structural matching (matches logic cones, e.g. wires with same names)
equiv_induct    # Temporal induction (for sequential logic/FFs)

# Check results
equiv_status -assert"
