set_clock_latency -source -early -max -rise  -0.127687 [get_ports {clk}] -clock aes_clk 
set_clock_latency -source -early -max -fall  -0.131388 [get_ports {clk}] -clock aes_clk 
set_clock_latency -source -late -max -rise  -0.127687 [get_ports {clk}] -clock aes_clk 
set_clock_latency -source -late -max -fall  -0.131388 [get_ports {clk}] -clock aes_clk 
