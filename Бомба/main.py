mport machine
import time
import random
import esp32
from machine import Pin, I2C, UART
from lcd import I2cLcd

# ============================================================
#  НАСТРОЙКА ПИНОВ (ИЗМЕНИТЕ ПОД ВАШУ СХЕМУ)
# ============================================================
# Клавиатура 4x3 (ряды и столбцы)
ROW_PINS = [13, 12, 14, 27]      # 4 ряда
COL_PINS = [26, 25, 33]          # 3 столбца

# Провода (4 шт.)
WIRE_PINS = [15, 16, 17, 18]     # входы с подтяжкой вверх

# I2C для LCD 20x4
I2C_SCL = 22
I2C_SDA = 21

# DFPlayer Mini (UART2)
DF_TX = 2    # ESP32 TX2 -> DFPlayer RX
DF_RX = 4    # ESP32 RX2 <- DFPlayer TX
DF_UART_NUM = 2

# Физические кнопки (замыкают на GND, внутренняя подтяжка PULL_UP)
BTN_A = 5    # ARM / подтверждение
BTN_B = 19   # MENU
BTN_C = 23   # BACKSPACE (удаление символа)
BTN_D = 35   # резервная (не используется, но можно задействовать)
# ============================================================

# --- Инициализация клавиатуры 4x3 ---
rows = [Pin(p, Pin.OUT) for p in ROW_PINS]
cols = [Pin(p, Pin.IN, Pin.PULL_DOWN) for p in COL_PINS]

# Раскладка (только цифры, * и #)
KEYMAP = [
    ['1','2','3'],
    ['4','5','6'],
    ['7','8','9'],
    ['*','0','#']
]

# --- Провода ---
wire_pins = [Pin(p, Pin.IN, Pin.PULL_UP) for p in WIRE_PINS]

# --- Физические кнопки ---
btn_a = Pin(BTN_A, Pin.IN, Pin.PULL_UP)
btn_b = Pin(BTN_B, Pin.IN, Pin.PULL_UP)
btn_c = Pin(BTN_C, Pin.IN, Pin.PULL_UP)
btn_d = Pin(BTN_D, Pin.IN, Pin.PULL_UP)

# --- LCD I2C ---
i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=400000)
try:
    lcd = I2cLcd(i2c, 0x27, 4, 20)
except Exception:
    try:
        lcd = I2cLcd(i2c, 0x3F, 4, 20)
    except Exception:
        raise RuntimeError("LCD not found")

# ============================================================
#  DFPLAYER MINI (воспроизведение звуков с SD-карты)
# ============================================================
DF_CMD_PLAY = 0x0D
DF_CMD_VOLUME = 0x06

def df_send_cmd(cmd, param1=0, param2=0):
    """Отправка команды DFPlayer по UART"""
    buf = bytearray(10)
    buf[0] = 0x7E
    buf[1] = 0xFF
    buf[2] = 0x06
    buf[3] = cmd
    buf[4] = 0x00
    buf[5] = param1
    buf[6] = param2
    checksum = 0 - (buf[1] + buf[2] + buf[3] + buf[4] + buf[5] + buf[6])
    buf[7] = (checksum >> 8) & 0xFF
    buf[8] = checksum & 0xFF
    buf[9] = 0xEF
    df_uart.write(buf)

def df_play(track):
    """Воспроизвести трек с номером (1..2999)"""
    high = (track >> 8) & 0xFF
    low = track & 0xFF
    df_send_cmd(DF_CMD_PLAY, high, low)

def df_set_volume(vol):
    """Громкость 0..30"""
    df_send_cmd(DF_CMD_VOLUME, 0, vol)

# Инициализация UART и установка громкости
df_uart = UART(DF_UART_NUM, baudrate=9600, tx=Pin(DF_TX), rx=Pin(DF_RX))
time.sleep(0.5)
df_set_volume(20)   # 50% громкости

# Номера треков (замените под свои файлы: 0001.mp3 ... 0008.mp3)
TRACK_CLICK = 1
TRACK_ERROR = 2
TRACK_UNLOCK = 3
TRACK_ARM = 4
TRACK_DEFUSED = 5
TRACK_BOOM = 6
TRACK_WRONG_CUT = 7
TRACK_PANIC = 8

def play_click():   df_play(TRACK_CLICK)
def play_error():   df_play(TRACK_ERROR)
def play_unlock():  df_play(TRACK_UNLOCK)
def play_arm():     df_play(TRACK_ARM)
def play_defused(): df_play(TRACK_DEFUSED)
def play_boom():    df_play(TRACK_BOOM)
def play_wrong_cut(): df_play(TRACK_WRONG_CUT)
def play_panic():   df_play(TRACK_PANIC)

# ============================================================
#  NVS (сохранение настроек в энергонезависимой памяти)
# ============================================================
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
game_mode = nvs_load_int("mode", 0)   # 0 – кодовый, 1 – проводной

# ============================================================
#  ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ
# ============================================================
input_buffer = ""
is_armed = False
last_tick = time.ticks_ms()
current_timer = countdown_seconds
safe_wire = -1
wrong_cuts = 0
hints_display = ["?", "?", "?", "?"]
wire_cut_processed = [False, False, False, False]

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def get_key():
    """Сканирование матричной клавиатуры 4x3"""
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
    return (text + " " * length)[:length]

def lcd_print(row, text):
    lcd.move_to(0, row)
    lcd.putstr(pad_right(text, 20))

def show_locked():
    global input_buffer
    input_buffer = ""
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "KEYPAD LOCKED")
    lcd_print(1, "Enter Code: ")
    lcd_print(2, "A=ARM  B=MENU")
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
    play_defused()
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "BOMB DEFUSED!")
    lcd_print(2, "MISSION COMPLETE!")
    time.sleep(3)
    show_locked()

def show_boom():
    lcd.clear()
    time.sleep_ms(10)
    lcd_print(0, "*** BOOM! ***")
    lcd_print(2, "MISSION FAILED!")
    play_boom()
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
            play_click()
            val += k
            lcd_print(1, "> " + val)
        elif k == 'C' and val:   # на случай, если кто-то использует C (но мы его убрали)
            play_click()
            val = val[:-1]
            lcd_print(1, "> " + val)
        elif k == '#':
            if len(val) == 4:
                return val
            else:
                play_error()
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
            play_click()
            val_str += k
            lcd_print(1, "> " + val_str)
        elif k == 'C' and val_str:
            play_click()
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
    play_unlock()
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
                play_defused()
        elif k == '2':
            new_val = input_4digit("SET DEFUSE CODE:", secret_code)
            if new_val:
                secret_code = new_val
                nvs_save_str("defuse", secret_code)
                play_defused()
        elif k == '3':
            new_val = input_number("SET TIMER (SEC):", countdown_seconds)
            if new_val and new_val > 0:
                countdown_seconds = new_val
                nvs_save_int("timer", countdown_seconds)
                play_defused()
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
                    play_unlock()
                    mode_selected = True
                elif k2 == 'B':
                    game_mode = 1
                    nvs_save_int("mode", game_mode)
                    play_unlock()
                    mode_selected = True
                elif k2 == '#':
                    mode_selected = True
                time.sleep_ms(10)
        elif k == '#':
            break
        time.sleep_ms(10)
    show_locked()

# ============================================================
#  ГЛАВНЫЙ ЦИКЛ
# ============================================================
show_locked()

while True:
    # ---- Сканирование клавиатуры ----
    key = get_key()

    # ---- Обработка физических кнопок (замена A, B, C, D) ----
    # Кнопка A (ARM / подтверждение)
    if btn_a.value() == 0:
        time.sleep_ms(50)
        key = 'A'
        while btn_a.value() == 0:
            time.sleep_ms(10)
    # Кнопка B (MENU)
    elif btn_b.value() == 0:
        time.sleep_ms(50)
        key = 'B'
        while btn_b.value() == 0:
            time.sleep_ms(10)
    # Кнопка C (BACKSPACE)
    elif btn_c.value() == 0:
        time.sleep_ms(50)
        key = 'C'
        while btn_c.value() == 0:
            time.sleep_ms(10)
    # Кнопка D (резерв, не используется, но можно добавить логику)
    elif btn_d.value() == 0:
        time.sleep_ms(50)
        key = 'D'
        while btn_d.value() == 0:
            time.sleep_ms(10)

    # ---- ОБРАБОТКА СОСТОЯНИЙ ----
    if key:
        # === СОСТОЯНИЕ: ЗАБЛОКИРОВАНО ===
        if not is_armed:
            if key.isdigit() and len(input_buffer) < 4:
                play_click()
                input_buffer += key
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'C' and input_buffer:
                play_click()
                input_buffer = input_buffer[:-1]
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'A':
                if input_buffer == unlock_code:
                    is_armed = True
                    play_arm()
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
                    play_error()
                    lcd_print(1, "WRONG CODE!")
                    time.sleep(1)
                    show_locked()
            elif key == 'B':
                if input_buffer == ADMIN_CODE:
                    open_menu()
                else:
                    play_error()
                    lcd_print(1, "WRONG ADMIN!")
                    time.sleep(1)
                    show_locked()

        # === СОСТОЯНИЕ: ВООРУЖЕНА (кодовый режим) ===
        elif is_armed and game_mode == 0:
            if key.isdigit() and len(input_buffer) < 4:
                play_click()
                input_buffer += key
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'C' and input_buffer:
                play_click()
                input_buffer = input_buffer[:-1]
                lcd.move_to(12, 1)
                stars = "*" * len(input_buffer)
                lcd.putstr(stars + " " * (4 - len(input_buffer)))
            elif key == 'A':
                if input_buffer == secret_code:
                    is_armed = False
                    show_defused()
                else:
                    play_error()
                    lcd_print(1, "WRONG CODE!")
                    time.sleep(1)
                    input_buffer = ""
                    lcd_print(1, "Enter Code:     ")

    # === ПРОВОДНОЙ РЕЖИМ (опрос проводов) ===
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
                        play_panic()
                        time.sleep_ms(500)
                        lcd_print(3, "")
                    else:
                        lcd_print(3, "-10s!")
                        current_timer -= 10
                        if current_timer < 0:
                            current_timer = 0
                        lcd_print(0, "Time left: " + str(current_timer) + "s")
                        play_wrong_cut()
                        time.sleep_ms(500)
                        lcd_print(3, "")
                break

    # === ТАЙМЕР (обновление каждую секунду) ===
    if is_armed:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_tick) >= 1000:
            last_tick = now
            current_timer -= 1
            lcd_print(0, "Time left: " + str(current_timer) + "s ")
            if current_timer <= 0:
                is_armed = False
                show_boom()

    time.sleep_ms(10)
