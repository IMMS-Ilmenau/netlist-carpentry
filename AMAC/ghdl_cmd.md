# Generieren
ghdl --synth -fsynopsys -fexplicit --out=verilog @../sources.txt -e META_X_dig_core > design_orig.v

# Sanitizen
2 Instanzen werden als `reg` benannt, was ein Verilog Keyword ist --> umbenennen (z.B. `reg_inst`)
