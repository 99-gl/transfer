set_clock_latency -source -early -min -rise  -0.211746 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -early -min -fall  -0.140034 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -early -max -rise  -0.211746 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -early -max -fall  -0.140034 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -late -min -rise  -0.211746 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -late -min -fall  -0.140034 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -late -max -rise  -0.211746 [get_ports {clk_i}] -clock core_clock 
set_clock_latency -source -late -max -fall  -0.140034 [get_ports {clk_i}] -clock core_clock 
