
library ieee;
use ieee.std_logic_1164.all;

-------------------------------------------------

entity demux is
port(
    I   : 	in  std_logic;
	S   :	in  std_logic;
	O0  :	out std_logic;
	O1  :	out std_logic
);
end demux;

-------------------------------------------------


architecture behv1 of demux is
begin
	O0 <= I when S = '0' else '0';
	O1 <= I when S = '1' else '0';
end behv1;
