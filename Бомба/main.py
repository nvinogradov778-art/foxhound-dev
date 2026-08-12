import machine
import time
import random
import esp32
from machine import Pin, I2C, PWM
from lcd import I2cLcd

buzzer_pin = Pin(19, Pin.OUT)
buzzer = PWM(buzzer_pin)
buzzer.duty(0)

led_green = Pin(2, Pin.OUT)
led_red = Pin(4, Pin.OUT)

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)

try:
    lcd = I2cLcd(i2c, 0x27, 4, 20)
except Exception as e:
    try:
        lcd = I2cLcd(i2c, 0x3F, 4, 20)
    except Exception as e2:
        pass

row_pins = [13, 12, 14, 27]
col_pins = [26, 25, 33, 32]
rows = [Pin(pin, Pin.OUT) for pin in row_pins]
cols = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in col_pins]

KEYMAP = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

# Провода: индекс 0 -> пин 15 -> провод 1, индекс 1 -> пин 16 -> провод 2 и т.д.
wire_pins = [Pin(15, Pin.IN, Pin.PULL_UP),   # провод 1
             Pin(16, Pin.IN, Pin.PULL_UP),   # провод 2
             Pin(17, Pin.IN, Pin.PULL_UP),   # провод 3
             Pin(18, Pin.IN, Pin.PULL_UP)]   # провод 4

def tone(freq, duration_ms):
    if freq == 0:
        buzzer.duty(0)
        time.sleep_ms(duration_ms)
    else:
        buzzer.freq(freq)
        buzzer.duty(512)
        time.sleep_ms(duration_ms)
        buzzer.duty(0)

def sound_click(): tone(1000, 50)
def sound_error(): tone(300, 300)
def sound_unlock(): tone(800,100); time.sleep_ms(50); tone(1200,150)

def sound_arm():
    for f in range(800,2000,200):
        tone(f,40)

def sound_defused():
    tone(1500,200); tone(1800,200); tone(2200,400)

def sound_boom():
    for _ in range(5):
        tone(600,250)
        tone(400,250)

def sound_wrong_cut():
    for _ in range(6):
        for f in range(800, 400, -50):
            tone(f, 30)
        for f in range(400, 800, 50):
            tone(f, 30)

def sound_panic():
    for _ in range(10):
        tone(1200, 50)
        time.sleep_ms(30)

NVS_NAMESPACE = "bomb_cfg"

def nvs_save_str(key, value):
    try:
        nvs = esp32.NVS(NVS_NAMESPACE)
        nvs.set_blob(key, value.encode())
        nvs.commit()
    except:
        pass

def nvs_load_str(key, default):
    try:
        nvs = esp32.NVS(NVS_NAMESPACE)
        buf = bytearray(10)
        nvs.get_blob(key, buf)
        return buf.decode().strip('\x00')
    except:
        return default

def nvs_save_int(key, value):
    try:
        nvs = esp32.NVS(NVS_NAMESPACE)
        nvs.set_i32(key, value)
        nvs.commit()
    except:
        pass

def nvs_load_int(key, default):
    try:
        nvs = esp32.NVS(NVS_NAMESPACE)
        return nvs.get_i32(key)
    except:
        return default

ADMIN_CODE = "1712"

unlock_code = nvs_load_str("unlock", "7777")
secret_code = nvs_load_str("defuse", "7777")
countdown_seconds = nvs_load_int("timer", 45)
game_mode = nvs_load_int("mode", 0)

input_buffer = ""
is_armed = False
last_tick = time.ticks_ms()
current_timer = countdown_seconds
safe_wire = -1
wrong_cuts = 0
hints_display = ["?", "?", "?", "?"]
wire_cut_processed = [False, False, False, False]

def get_key():
    for r_idx, row in enumerate(rows):
        row.value(1)
        time.sleep_us(10)
        for c_idx, col in enumerate(cols):
            if col.value() == 1:
                row.value(0)
                while col.value() == 1:
                    time.sleep_ms(10)
                return KEYMAP[r_idx][c_idx]
        row.value(0)
    return None

def pad_right(text, length=20):
    if len(text) >= length:
        return text[:length]
    return text + " " * (length - len(text))

def lcd_print(row, text):
    lcd.move_to(0, row)
    lcd.putstr(pad_right(text, 20))

def show_locked():
    global input_buffer
    input_buffer = ""
    led_green.value(0)
    led_red.value(0)
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "KEYPAD LOCKED")
    lcd_print(1, "Enter Code: ")
    lcd_print(2, "A=ARM B=MENU")
    mode_text = "WIRE" if game_mode == 1 else "CODE"
    lcd_print(3, "Mode: " + mode_text)

def show_armed_code():
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "ARMED! RUN!")
    time.sleep(1.5)
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "Time left: " + str(current_timer) + "s")
    lcd_print(1, "Enter Code: ")

def show_armed_wire():
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "ARMED! CUT WIRE!")
    time.sleep(1.5)
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "Time left: " + str(current_timer) + "s")
    lcd_print(1, "[1] [2] [3] [4]")
    hint_line = ""
    for s in hints_display:
        hint_line += " " + s + "  "
    lcd_print(2, hint_line)
    lcd_print(3, "")

def update_wire_display():
    line = ""
    for i in range(4):
        if wire_pins[i].value() == 0:
            line += "[X] "
        else:
            line += "[" + str(i+1) + "] "
    lcd_print(1, line)

def reveal_hint_after_mistake():
    global hints_display
    hidden = [i for i, v in enumerate(hints_display) if v == "?"]
    if not hidden:
        return
    plus_revealed = (hints_display[safe_wire] == "+")
    wrong_hidden = [i for i in hidden if i != safe_wire]
    if not plus_revealed and (random.randint(0, 1) == 0 or not wrong_hidden):
        hints_display[safe_wire] = "+"
    elif wrong_hidden:
        idx = random.choice(wrong_hidden)
        hints_display[idx] = "-"
    else:
        if not plus_revealed:
            hints_display[safe_wire] = "+"

def show_defused():
    sound_defused()
    led_green.value(1)
    led_red.value(0)
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "BOMB DEFUSED!")
    lcd_print(2, "MISSION COMPLETE!")
    time.sleep(3)
    show_locked()

def show_boom():
    led_green.value(0)
    led_red.value(1)
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "*** BOOM! ***")
    lcd_print(2, "MISSION FAILED!")
    sound_boom()
    time.sleep(2)
    show_locked()

def input_4digit(title, default_val=""):
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, title)
    lcd_print(1, "> " + default_val)
    val = default_val
    while True:
        k = get_key()
        if k and k.isdigit() and len(val) < 4:
            sound_click()
            val += k
            lcd_print(1, "> " + val)
        elif k == 'C' and val:
            sound_click()
            val = val[:-1]
            lcd_print(1, "> " + val)
        elif k == '#':
            if len(val) == 4:
                return val
            else:
                sound_error()
        elif k == '*':
            return None
        time.sleep_ms(10)

def input_number(title, default_val=45):
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, title)
    val_str = str(default_val)
    lcd_print(1, "> " + val_str)
    while True:
        k = get_key()
        if k and k.isdigit() and len(val_str) < 3:
            sound_click()
            val_str += k
            lcd_print(1, "> " + val_str)
        elif k == 'C' and val_str:
            sound_click()
            val_str = val_str[:-1]
            if not val_str:
                val_str = "0"
            lcd_print(1, "> " + val_str)
        elif k == '#':
            return int(val_str)
        elif k == '*':
            return None
        time.sleep_ms(10)

def open_menu():
    global unlock_code, secret_code, countdown_seconds, game_mode
    sound_unlock()
    while True:
        lcd.clear()
        time.sleep_ms(10)
        lcd_print(0, "ENGINEER MENU")
        lcd_print(1, "1:UNLOCK CODE")
        lcd_print(2, "2:DEFUSE CODE")
        lcd_print(3, "3:TIMER 4:MODE")
        k = None
        while k is None:
            k = get_key()
            time.sleep_ms(10)
        if k == '1':
            new_val = input_4digit("SET UNLOCK CODE:", unlock_code)
            if new_val:
                unlock_code = new_val
                nvs_save_str("unlock", unlock_code)
                sound_defused()
        elif k == '2':
            new_val = input_4digit("SET DEFUSE CODE:", secret_code)
            if new_val:
                secret_code = new_val
                nvs_save_str("defuse", secret_code)
                sound_defused()
        elif k == '3':
            new_val = input_number("SET TIMER (SEC):", countdown_seconds)
            if new_val and new_val > 0:
                countdown_seconds = new_val
                nvs_save_int("timer", countdown_seconds)
                sound_defused()
        elif k == '4':
            lcd.clear()
            time.sleep_ms(10)
            lcd_print(0, "SELECT MODE:")
            lcd_print(1, "A: CODE")
            lcd_print(2, "B: WIRE")
            lcd_print(3, "CURRENT: " + ("WIRE" if game_mode == 1 else "CODE"))
            mode_selected = False
            while not mode_selected:
                k2 = get_key()
                if k2 == 'A':
                    game_mode = 0
                    nvs_save_int("mode", game_mode)
                    sound_unlock()
                    mode_selected = True
                elif k2 == 'B':
                    game_mode = 1
                    nvs_save_int("mode", game_mode)
                    sound_unlock()
                    mode_selected = True
                elif k2 == '#':
                    mode_selected = True
                time.sleep_ms(10)
        elif k == '#':
            break
        time.sleep_ms(10)
    show_locked()

show_locked()

while True:
    key = get_key()
    if key:
        if not is_armed:
            if key.isdigit() and len(input_buffer) < 4:
                sound_click()
                input_buffer += key
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'C' and input_buffer:
                sound_click()
                input_buffer = input_buffer[:-1]
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'A':
                if input_buffer == unlock_code:
                    is_armed = True
                    sound_arm()
                    led_green.value(0)
                    led_red.value(1)
                    current_timer = countdown_seconds
                    last_tick = time.ticks_ms()
                    input_buffer = ""
                    if game_mode == 1:
                        safe_wire = random.randint(0, 3)
                        hints_display = ["?", "?", "?", "?"]
                        wrong_cuts = 0
                        wire_cut_processed = [False, False, False, False]
                        show_armed_wire()
                    else:
                        show_armed_code()
                else:
                    sound_error()
                    lcd_print(1, "WRONG CODE!")
                    time.sleep(1)
                    show_locked()
            elif key == 'B':
                if input_buffer == ADMIN_CODE:
                    open_menu()
                else:
                    sound_error()
                    lcd_print(1, "WRONG ADMIN!")
                    time.sleep(1)
                    show_locked()
        elif is_armed and game_mode == 0:
            if key.isdigit() and len(input_buffer) < 4:
                sound_click()
                input_buffer += key
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'C' and input_buffer:
                sound_click()
                input_buffer = input_buffer[:-1]
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'A':
                if input_buffer == secret_code:
                    is_armed = False
                    show_defused()
                else:
                    sound_error()
                    lcd_print(1, "WRONG CODE!")
                    time.sleep(1)
                    input_buffer = ""
                    lcd_print(1, "Enter Code:     ")

    if is_armed and game_mode == 1:
        for i in range(4):
            if wire_pins[i].value() == 0 and not wire_cut_processed[i]:
                wire_cut_processed[i] = True
                if i == safe_wire:
                    is_armed = False
                    update_wire_display()
                    time.sleep_ms(500)
                    show_defused()
                else:
                    wrong_cuts += 1
                    update_wire_display()
                    reveal_hint_after_mistake()
                    hint_line = ""
                    for s in hints_display:
                        hint_line += " " + s + "  "
                    lcd_print(2, hint_line)
                    if wrong_cuts >= 3:
                        is_armed = False
                        lcd_print(3, "BOOM! WRONG WIRE!")
                        time.sleep_ms(500)
                        show_boom()
                    elif wrong_cuts == 2:
                        lcd_print(3, "-50% time!")
                        current_timer = current_timer // 2
                        lcd_print(0, "Time left: " + str(current_timer) + "s")
                        sound_panic()
                        time.sleep_ms(500)
                        lcd_print(3, "")
                    else:
                        lcd_print(3, "-10s!")
                        current_timer -= 10
                        if current_timer < 0:
                            current_timer = 0
                        lcd_print(0, "Time left: " + str(current_timer) + "s")
                        sound_wrong_cut()
                        time.sleep_ms(500)
                        lcd_print(3, "")
                break

    if is_armed:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_tick) >= 1000:
            last_tick = now
            current_timer -= 1
            led_red.value(not led_red.value())
            tone(1200, 60)
            lcd_print(0, "Time left: " + str(current_timer) + "s ")
            if current_timer <= 0:
                is_armed = False
                show_boom()

    time.sleep_ms(10)