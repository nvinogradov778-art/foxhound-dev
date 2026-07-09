import time

class LcdApi:
    def __init__(self, num_lines, num_columns):
        self.num_lines = num_lines
        self.num_columns = num_columns
    def clear(self):
        self.hal_write_command(0x01)
        time.sleep_ms(2)
    def move_to(self, cursor_x, cursor_y):
        addr = cursor_x & 0x3f
        if cursor_y & 1: addr += 0x40
        if cursor_y & 2: addr += self.num_columns
        self.hal_write_command(0x80 | addr)
    def putstr(self, string):
        for char in string:
            self.hal_write_char(ord(char))

class I2cLcd(LcdApi):
    def __init__(self, i2c, i2c_addr, num_lines, num_columns):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.i2c.writeto(self.i2c_addr, b'\x00')
        time.sleep_ms(20)
        self.hal_write_command(0x03)
        time.sleep_ms(5)
        self.hal_write_command(0x03)
        time.sleep_ms(5)
        self.hal_write_command(0x03)
        time.sleep_ms(1)
        self.hal_write_command(0x02)
        self.hal_write_command(0x28)
        self.hal_write_command(0x0c)
        self.hal_write_command(0x06)
        self.clear()
    def hal_write_command(self, cmd):
        self.i2c.writeto(self.i2c_addr, bytes([(cmd & 0xF0) | 0x08, (cmd & 0xF0) | 0x0C, (cmd & 0xF0) | 0x08]))
        self.i2c.writeto(self.i2c_addr, bytes([((cmd << 4) & 0xF0) | 0x08, ((cmd << 4) & 0xF0) | 0x0C, ((cmd << 4) & 0xF0) | 0x08]))
    def hal_write_char(self, char):
        self.i2c.writeto(self.i2c_addr, bytes([(char & 0xF0) | 0x09, (char & 0xF0) | 0x0D, (char & 0xF0) | 0x09]))
        self.i2c.writeto(self.i2c_addr, bytes([((char << 4) & 0xF0) | 0x09, ((char << 4) & 0xF0) | 0x0D, ((char << 4) & 0xF0) | 0x09]))
