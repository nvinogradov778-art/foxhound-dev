# lcd.py - I2C LCD 20x4 Driver for ESP32 (MicroPython)

import time
from machine import I2C

# Команды LCD
LCD_CLEAR = 0x01
LCD_HOME = 0x02
LCD_ENTRY_MODE = 0x04
LCD_DISPLAY = 0x08
LCD_SHIFT = 0x10
LCD_FUNCTION = 0x20
LCD_CGRAM = 0x40
LCD_DDRAM = 0x80

# Флаги
LCD_ENTRY_LEFT = 0x02
LCD_DISPLAY_ON = 0x04
LCD_CURSOR_OFF = 0x00
LCD_BLINK_OFF = 0x00
LCD_8BIT_MODE = 0x10
LCD_4BIT_MODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10_DOTS = 0x04
LCD_5x8_DOTS = 0x00

# Адреса строк для 20x4
# Строки: 0, 1, 2, 3 -> адреса: 0x00, 0x40, 0x14, 0x54
ROW_ADDR = [0x00, 0x40, 0x14, 0x54]

class I2cLcd:
    def __init__(self, i2c, addr=0x27, rows=4, cols=20):
        self.i2c = i2c
        self.addr = addr
        self.rows = rows
        self.cols = cols
        self.backlight = 0x08
        
        # Ждем готовности LCD
        time.sleep_ms(100)
        
        # Инициализация в 4-битном режиме (3 попытки)
        for _ in range(3):
            self._write_nibble(0x03)
            time.sleep_ms(5)
        
        self._write_nibble(0x02)  # 4-битный режим
        time.sleep_ms(1)
        
        # Конфигурация дисплея
        self._send_cmd(LCD_FUNCTION | LCD_4BIT_MODE | LCD_2LINE | LCD_5x8_DOTS)
        self._send_cmd(LCD_DISPLAY | LCD_DISPLAY_ON | LCD_CURSOR_OFF | LCD_BLINK_OFF)
        self.clear()
        self._send_cmd(LCD_ENTRY_MODE | LCD_ENTRY_LEFT)
        time.sleep_ms(10)
        
        print(f"LCD initialized: {rows}x{cols}, addr: 0x{addr:02X}")

    def _write_byte(self, data):
        """Отправка байта с backlight"""
        try:
            self.i2c.writeto(self.addr, bytes([data | self.backlight]))
        except:
            pass

    def _pulse_enable(self, data):
        """Импульс на EN пине"""
        self._write_byte(data | 0x04)  # EN = 1
        time.sleep_us(10)
        self._write_byte(data & ~0x04) # EN = 0
        time.sleep_us(100)

    def _write_nibble(self, nibble):
        """Отправка полубайта"""
        self._write_byte(nibble << 4)
        self._pulse_enable(nibble << 4)

    def _send_cmd(self, cmd):
        """Отправка команды"""
        high = cmd & 0xF0
        low = (cmd << 4) & 0xF0
        
        self._write_byte(high)
        self._pulse_enable(high)
        self._write_byte(low)
        self._pulse_enable(low)
        
        if cmd == LCD_CLEAR or cmd == LCD_HOME:
            time.sleep_ms(2)

    def _send_data(self, data):
        """Отправка данных"""
        high = data & 0xF0
        low = (data << 4) & 0xF0
        
        self._write_byte(high | 0x01)  # RS = 1
        self._pulse_enable(high | 0x01)
        self._write_byte(low | 0x01)
        self._pulse_enable(low | 0x01)

    def clear(self):
        """Очистка дисплея"""
        self._send_cmd(LCD_CLEAR)
        time.sleep_ms(5)

    def home(self):
        """Курсор в начало"""
        self._send_cmd(LCD_HOME)
        time.sleep_ms(5)

    def move_to(self, col, row):
        """Перемещение курсора (col 0-19, row 0-3)"""
        if row >= self.rows:
            row = self.rows - 1
        if col >= self.cols:
            col = self.cols - 1
        
        addr = ROW_ADDR[row] + col
        self._send_cmd(LCD_DDRAM | addr)

    def putstr(self, text):
        """Вывод строки"""
        for char in str(text):
            self._send_data(ord(char))

    def putchar(self, char):
        """Вывод одного символа"""
        self._send_data(ord(char))

    def create_char(self, location, charmap):
        """Создание пользовательского символа (0-7)"""
        location &= 0x7
        self._send_cmd(LCD_CGRAM | (location << 3))
        for i in range(8):
            self._send_data(charmap[i])