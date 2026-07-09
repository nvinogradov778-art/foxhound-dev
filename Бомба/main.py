import machine
import time
from machine import Pin, I2C, PWM
from lcd import I2cLcd

# --- НАСТРОЙКА ЖЕЛЕЗА ---
# Используем PWM для генерации звуков разной частоты
buzzer_pin = Pin(19, Pin.OUT)
buzzer = PWM(buzzer_pin)
buzzer.duty(0) # Изначально выключен

led_green = Pin(2, Pin.OUT)
led_red = Pin(4, Pin.OUT)

# Настройка дисплея I2C
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
lcd = I2cLcd(i2c, 0x27, 2, 16)

# Настройка клавиатуры 4х4
row_pins = [13, 12, 14, 27]
col_pins = [26, 25, 33, 32]
rows = [Pin(pin, Pin.OUT) for pin in row_pins]
cols = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in col_pins]

KEYMAP = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

# --- УЛУЧШЕННЫЕ ЗВУКОВЫЕ ЭФФЕКТЫ ---
def tone(freq, duration_ms):
    """Генерация звука определенной частоты"""
    if freq == 0:
        buzzer.duty(0)
        time.sleep_ms(duration_ms)
    else:
        buzzer.freq(freq)
        buzzer.duty(512) # 50% громкости
        time.sleep_ms(duration_ms)
        buzzer.duty(0)

def sound_click(): tone(1000, 50)
def sound_error(): tone(300, 300)
def sound_unlock():
    tone(800, 100)
    time.sleep_ms(50)
    tone(1200, 150)
def sound_arm():
    for f in range(800, 2000, 200):
        tone(f, 40)
def sound_defused():
    tone(1500, 200)
    tone(1800, 200)
    tone(2200, 400)

# --- СКАНЕР КЛАВИАТУРЫ ---
def get_key():
    for r_idx, row in enumerate(rows):
        row.value(1)
        for c_idx, col in enumerate(cols):
            if col.value() == 1:
                row.value(0)
                while col.value() == 1:
                    time.sleep_ms(10)
                return KEYMAP[r_idx][c_idx]
        row.value(0)
    return None

# --- ИГРОВЫЕ ПЕРЕМЕННЫЕ ---
unlock_code = "7777"   # Код для разблокировки клавиатуры
secret_code = "1234"   # Код для разминирования бомбы
countdown_seconds = 45 # Стандартное время таймера

input_buffer = ""
is_unlocked = False    # Статус блокировки клавиатуры
is_armed = False       # Статус активности бомбы
last_tick = time.ticks_ms()

# --- СТАТУСНЫЕ ЭКРАНЫ ---
def show_locked():
    global input_buffer
    input_buffer = ""
    led_green.value(0)
    led_red.value(0)
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("KEYPAD LOCKED")
    lcd.move_to(0, 1)
    lcd.putstr("Enter Code: ")

def show_ready():
    global input_buffer
    input_buffer = ""
    led_green.value(1)
    led_red.value(0)
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("UNLOCKED! A=MENU")
    lcd.move_to(0, 1)
    lcd.putstr("Press * to ARM")

# --- СЕКРЕТНОЕ МЕНЮ НАСТРОЕК ---
def open_menu():
    global secret_code, countdown_seconds
    sound_unlock()
    
    # 1. Настройка времени
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("SET TIME (SEC):")
    lcd.move_to(0, 1)
    lcd.putstr("> ")
    time_str = ""
    while True:
        k = get_key()
        if k and k.isdigit() and len(time_str) < 3:
            sound_click()
            time_str += k
            lcd.move_to(2, 1)
            lcd.putstr(time_str)
        elif k == '#':
            if time_str: countdown_seconds = int(time_str)
            break
            
    # 2. Настройка нового кода разминирования
    sound_unlock()
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("SET DEFUSE CODE:")
    lcd.move_to(0, 1)
    lcd.putstr("> ")
    code_str = ""
    while True:
        k = get_key()
        if k and k.isdigit() and len(code_str) < 6:
            sound_click()
            code_str += k
            lcd.move_to(2, 1)
            lcd.putstr(code_str)
        elif k == '#':
            if code_str: secret_code = code_str
            break
            
    sound_defused()
    show_ready()

# Инициализация запуска
show_locked()

# --- ОСНОВНОЙ ЦИКЛ ---
while True:
    key = get_key()
    
    if key:
        # 1. ЕСЛИ КЛАВИАТУРА ЗАБЛОКИРОВАНА
        if not is_unlocked and not is_armed:
            if key.isdigit() and len(input_buffer) < 6:
                sound_click()
                input_buffer += key
                lcd.move_to(12, 1)
                lcd.putstr("*" * len(input_buffer))
            elif key == '#':
                if input_buffer == unlock_code:
                    is_unlocked = True
                    sound_unlock()
                    show_ready()
                else:
                    sound_error()
                    lcd.move_to(0, 1)
                    lcd.putstr("WRONG CODE!     ")
                    time.sleep(1)
                    show_locked()

        # 2. ЕСЛИ КЛАВИАТУРА РАЗБЛОКИРОВАНА (Ожидание закладки бомбы)
        elif is_unlocked and not is_armed:
            if key == '*':
                is_armed = True
                is_unlocked = False # Клавиатура снова закрывается при старте
                input_buffer = ""
                sound_arm()
                led_green.value(0)
                led_red.value(1)
                lcd.clear()
                lcd.putstr("ARMED! RUN!")
                time.sleep(1.5)
                lcd.clear()
                last_tick = time.ticks_ms()
                current_timer = countdown_seconds
            elif key == 'A': # Вход в меню настроек
                open_menu()

        # 3. ЕСЛИ БОМБА ВЗВЕДЕНА (Идет обратный отсчет)
        elif is_armed:
            if key == '#':
                if input_buffer == secret_code:
                    is_armed = False
                    sound_defused()
                    lcd.clear()
                    lcd.putstr("BOMB DEFUSED!")
                    time.sleep(3)
                    show_locked() # Возврат к полной блокировке
                else:
                    sound_error()
                    input_buffer = ""
                    lcd.move_to(0, 1)
                    lcd.putstr("WRONG CODE!     ")
                    time.sleep(1)
                    lcd.move_to(0, 1)
                    lcd.putstr("Code:           ")
            elif key.isdigit() and len(input_buffer) < 6:
                sound_click()
                input_buffer += key
                lcd.move_to(0, 1)
                lcd.putstr(f"Code: {'*' * len(input_buffer)}   ")

    # ЛОГИКА ТАЙМЕРА (Когда бомба активна)
    if is_armed:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_tick) >= 1000:
            last_tick = now
            current_timer -= 1
            
            led_red.value(not led_red.value())
            # Динамик коротко пищит каждую секунду
            tone(1200, 60)
            
            lcd.move_to(0, 0)
            lcd.putstr(f"Time left: {current_timer}s  ")
            
            # Сценарий Взрыва
            if current_timer <= 0:
                is_armed = False
                led_green.value(0)
                led_red.value(1)
                lcd.clear()
                lcd.putstr("BOOM!!!")
                # Воспроизведение сирены взрыва
                for _ in range(5):
                    tone(600, 250)
                    tone(400, 250)
                show_locked()

    time.sleep_ms(10)
