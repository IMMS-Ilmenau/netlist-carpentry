library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL; -- Required for arithmetic operations

entity Counter16Bit is
    Port (
        clk   : in  STD_LOGIC;
        reset : in  STD_LOGIC;
        q     : out STD_LOGIC_VECTOR(15 downto 0)
    );
end Counter16Bit;

architecture Behavioral of Counter16Bit is
    -- Internal signal to perform math (unsigned type)
    signal count_reg : unsigned(15 downto 0) := (others => '0');
begin

    process(clk, reset)
    begin
    if reset = '1' then
        count_reg <= (others => '0'); -- Reset to 0
    elsif rising_edge(clk) then
        count_reg <= count_reg + 1; -- Increment
    end if;
end process;

    -- Convert unsigned back to std_logic_vector for the output port
    q <= std_logic_vector(count_reg);

end Behavioral;
