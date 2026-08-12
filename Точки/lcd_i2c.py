import time

class LCD_I2C:
    def __init__(self, i2c, address, rows, cols):
        self.i2c = i2c
        self.address = address
        self.rows = rows
        self.cols = cols
        self.backlight = 0x08
        self._init_lcd()

    def _write_byte(self, val):
        try:
            self.i2c.writeto(self.address, bytearray([val]))
        except OSError:
            pass # Игнорируем ошибку, если дисплей не подключен

    def _send(self, val, mode):
        high = mode | (val & 0xF0) | self.backlight
        low = mode | ((val << 4) & 0xF0) | self.backlight
        self._write_byte(high)
        self._write_byte(high | 0x04)
        self._write_byte(high & ~0x04)
        self._write_byte(low)
        self._write_byte(low | 0x04)
        self._write_byte(low & ~0x04)

    def command(self, cmd):
        self._send(cmd, 0)

    def write_char(self, char):
        self._send(char, 1)

    def _init_lcd(self):
        time.sleep_ms(50)
        for cmd in (0x33, 0x32, 0x28, 0x0C, 0x06):
            self.command(cmd)
        self.clear()

    def clear(self):
        self.command(0x01)
        time.sleep_ms(2)

    def move_to(self, row, col):
        offsets = [0x00, 0x40, 0x14, 0x54]
        self.command(0x80 | (offsets[row] + col))

    def putstr(self, text):
        for char in text:
            self.write_char(ord(char))