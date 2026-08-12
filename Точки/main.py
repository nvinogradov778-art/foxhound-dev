import time
from machine import Pin, PWM, I2C
from lcd_i2c import LCD_I2C

I2C_SCL_PIN = 22
I2C_SDA_PIN = 21
BTN_TEAM1_PIN = 12
BTN_TEAM2_PIN = 14
BTN_UP_PIN = 13
BTN_DOWN_PIN = 15
BTN_SEL_PIN = 2
BTN_EXIT_PIN = 4
LED_TEAM1_PIN = 26
LED_TEAM2_PIN = 27
BUZZER_PIN = 25

DEFAULT_CAPTURE_TIME = 4.0
DEFAULT_SCORE_INTERVAL = 1.0
DEFAULT_GAME_TIME = 10.0
NEUTRAL, TEAM_1, TEAM_2 = 0, 1, 2
TEAM_NAMES = {TEAM_1: "ALPHA", TEAM_2: "BRAVO"}

try:
    i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
    lcd = LCD_I2C(i2c, 0x27, 4, 20)
except Exception as e:
    print(f"LCD init fail: {e}")

btn_t1 = Pin(BTN_TEAM1_PIN, Pin.IN, Pin.PULL_UP)
btn_t2 = Pin(BTN_TEAM2_PIN, Pin.IN, Pin.PULL_UP)
btn_up = Pin(BTN_UP_PIN, Pin.IN, Pin.PULL_UP)
btn_down = Pin(BTN_DOWN_PIN, Pin.IN, Pin.PULL_UP)
btn_sel = Pin(BTN_SEL_PIN, Pin.IN, Pin.PULL_UP)
btn_exit = Pin(BTN_EXIT_PIN, Pin.IN, Pin.PULL_UP)

led_t1 = Pin(LED_TEAM1_PIN, Pin.OUT)
led_t2 = Pin(LED_TEAM2_PIN, Pin.OUT)
buzzer = PWM(Pin(BUZZER_PIN), freq=1000, duty=0)

class GameState:
    def __init__(self):
        self.owner = NEUTRAL
        self.scores = {TEAM_1: 0, TEAM_2: 0}
        self.capture_time = DEFAULT_CAPTURE_TIME
        self.score_interval = DEFAULT_SCORE_INTERVAL
        self.game_time = DEFAULT_GAME_TIME
        self.in_menu = False
        self.menu_index = 0
        self.editing = False
        self.capturing_team = NEUTRAL
        self.capture_start_time = 0
        self.last_score_time = 0
        self.is_beeping = False
        self.last_lcd_update = 0
        self.tone_stop_time = 0
        self.menu_exit_time = 0
        self.game_start_time = 0
        self.game_over = False

state = GameState()
btn_states = {k: False for k in ["t1", "t2", "up", "down", "sel", "exit"]}

def read_button(pin, name, debounce_ms=20):
    current = (pin.value() == 0)
    if current != btn_states[name]:
        time.sleep_ms(debounce_ms)
        current = (pin.value() == 0)
        btn_states[name] = current
    return current

def play_tone(freq, duty=512):
    buzzer.freq(freq)
    buzzer.duty(duty)

def stop_tone():
    buzzer.duty(0)

def timed_beep(freq, duration_ms):
    play_tone(freq)
    state.tone_stop_time = time.ticks_add(time.ticks_ms(), duration_ms)

def update_display():
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("---- DOMINATION ----")
    lcd.move_to(1, 0)
    if state.owner == TEAM_1:
        lcd.putstr("Owner: ALPHA        ")
        led_t1.value(1)
        led_t2.value(0)
    elif state.owner == TEAM_2:
        lcd.putstr("Owner: BRAVO        ")
        led_t1.value(0)
        led_t2.value(1)
    else:
        lcd.putstr("Owner: NEUTRAL      ")
        led_t1.value(0)
        led_t2.value(0)
    lcd.move_to(2, 0)
    lcd.putstr(f"ALPH:{state.scores[TEAM_1]:04d} BRAV:{state.scores[TEAM_2]:04d}")

def draw_progress(elapsed_ms):
    capture_ms = int(state.capture_time * 1000)
    bars = min(int((elapsed_ms / capture_ms) * 18), 18)
    lcd.move_to(3, 0)
    lcd.putstr("[" + "=" * bars + " " * (18 - bars) + "]")

def show_menu():
    state.in_menu = True
    state.editing = False
    lcd.clear()
    
    while read_button(btn_exit, "exit"):
        time.sleep_ms(10)
    
    while state.in_menu:
        lcd.move_to(0, 0)
        lcd.putstr("--- SETTINGS ---")
        
        if not state.editing:
            prefix0 = ">" if state.menu_index == 0 else " "
            prefix1 = ">" if state.menu_index == 1 else " "
            prefix2 = ">" if state.menu_index == 2 else " "
            lcd.move_to(1, 0)
            lcd.putstr(f"{prefix0}CapTime: {state.capture_time:.1f}s ")
            lcd.move_to(2, 0)
            lcd.putstr(f"{prefix1}ScrInt: {state.score_interval:.1f}s ")
            lcd.move_to(3, 0)
            lcd.putstr(f"{prefix2}GameTime: {state.game_time:.0f}m ")
        else:
            lcd.move_to(1, 0)
            mark0 = "*" if state.menu_index == 0 else " "
            lcd.putstr(f"{mark0}CapTime: {state.capture_time:.1f}s ")
            lcd.move_to(2, 0)
            mark1 = "*" if state.menu_index == 1 else " "
            lcd.putstr(f"{mark1}ScrInt: {state.score_interval:.1f}s ")
            lcd.move_to(3, 0)
            mark2 = "*" if state.menu_index == 2 else " "
            lcd.putstr(f"{mark2}GameTime: {state.game_time:.0f}m ")
        
        if read_button(btn_up, "up"):
            if not state.editing:
                state.menu_index = max(0, state.menu_index - 1)
            else:
                if state.menu_index == 0:
                    state.capture_time = min(10.0, state.capture_time + 0.5)
                elif state.menu_index == 1:
                    state.score_interval = min(5.0, state.score_interval + 0.5)
                else:
                    state.game_time = min(60.0, state.game_time + 1.0)
            time.sleep_ms(200)
            
        elif read_button(btn_down, "down"):
            if not state.editing:
                state.menu_index = min(2, state.menu_index + 1)
            else:
                if state.menu_index == 0:
                    state.capture_time = max(0.5, state.capture_time - 0.5)
                elif state.menu_index == 1:
                    state.score_interval = max(0.5, state.score_interval - 0.5)
                else:
                    state.game_time = max(1.0, state.game_time - 1.0)
            time.sleep_ms(200)
            
        elif read_button(btn_sel, "sel"):
            state.editing = not state.editing
            time.sleep_ms(200)
            
        elif read_button(btn_exit, "exit"):
            state.in_menu = False
            state.editing = False
            state.menu_exit_time = time.ticks_ms()
            update_display()
            while read_button(btn_exit, "exit"):
                time.sleep_ms(10)
            time.sleep_ms(100)
        
        time.sleep_ms(50)

def show_game_over():
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("=== GAME OVER ===")
    lcd.move_to(1, 0)
    lcd.putstr(f"ALPHA: {state.scores[TEAM_1]:04d}")
    lcd.move_to(2, 0)
    lcd.putstr(f"BRAVO: {state.scores[TEAM_2]:04d}")
    lcd.move_to(3, 0)
    if state.scores[TEAM_1] > state.scores[TEAM_2]:
        lcd.putstr("WINNER: ALPHA!")
    elif state.scores[TEAM_2] > state.scores[TEAM_1]:
        lcd.putstr("WINNER: BRAVO!")
    else:
        lcd.putstr("DRAW!")
    
    led_t1.value(0)
    led_t2.value(0)
    
    while not read_button(btn_exit, "exit"):
        time.sleep_ms(100)
    
    state.scores = {TEAM_1: 0, TEAM_2: 0}
    state.owner = NEUTRAL
    state.game_over = False
    state.game_start_time = time.ticks_ms()
    update_display()

def main():
    update_display()
    state.last_score_time = time.ticks_ms()
    state.game_start_time = time.ticks_ms()
    
    while True:
        now = time.ticks_ms()
        
        if state.game_over:
            time.sleep_ms(20)
            continue
        
        elapsed_game = time.ticks_diff(now, state.game_start_time) / 60000
        if elapsed_game >= state.game_time:
            state.game_over = True
            show_game_over()
            continue
        
        if read_button(btn_exit, "exit") and not state.in_menu and time.ticks_diff(now, state.menu_exit_time) > 1000:
            stop_tone()
            state.is_beeping = False
            state.capturing_team = NEUTRAL
            lcd.move_to(3, 0)
            lcd.putstr(" " * 20)
            show_menu()
            state.last_score_time = time.ticks_ms()
            continue
        
        if state.in_menu:
            time.sleep_ms(20)
            continue
        
        t1_pressed = read_button(btn_t1, "t1")
        t2_pressed = read_button(btn_t2, "t2")
        current_press = TEAM_1 if (t1_pressed and not t2_pressed and state.owner != TEAM_1) else TEAM_2 if (t2_pressed and not t1_pressed and state.owner != TEAM_2) else NEUTRAL
        
        if current_press != NEUTRAL:
            if state.capturing_team != current_press:
                state.capturing_team = current_press
                state.capture_start_time = now
            
            elapsed_ms = time.ticks_diff(now, state.capture_start_time)
            if time.ticks_diff(now, state.last_lcd_update) > 100:
                draw_progress(elapsed_ms)
                state.last_lcd_update = now
            
            beep_state = (elapsed_ms // 200) % 2 == 0
            if beep_state != state.is_beeping:
                if beep_state:
                    play_tone(1500)
                else:
                    stop_tone()
                state.is_beeping = beep_state
            
            if elapsed_ms >= state.capture_time * 1000:
                state.owner = current_press
                state.capturing_team = NEUTRAL
                state.last_score_time = now
                timed_beep(2000, 500)
                state.is_beeping = False
                lcd.move_to(3, 0)
                lcd.putstr(" " * 20)
                lcd.move_to(1, 0)
                if state.owner == TEAM_1:
                    lcd.putstr("Owner: ALPHA        ")
                    led_t1.value(1)
                    led_t2.value(0)
                else:
                    lcd.putstr("Owner: BRAVO        ")
                    led_t1.value(0)
                    led_t2.value(1)
        else:
            if state.capturing_team != NEUTRAL:
                state.capturing_team = NEUTRAL
                stop_tone()
                state.is_beeping = False
                lcd.move_to(3, 0)
                lcd.putstr(" " * 20)
                lcd.move_to(1, 0)
                if state.owner == TEAM_1:
                    lcd.putstr("Owner: ALPHA        ")
                elif state.owner == TEAM_2:
                    lcd.putstr("Owner: BRAVO        ")
                else:
                    lcd.putstr("Owner: NEUTRAL      ")
        
        if state.tone_stop_time and time.ticks_diff(now, state.tone_stop_time) >= 0:
            stop_tone()
            state.tone_stop_time = 0
        
        if state.owner != NEUTRAL and time.ticks_diff(now, state.last_score_time) >= state.score_interval * 1000:
            state.scores[state.owner] += 1
            state.last_score_time = now
            lcd.move_to(2, 0)
            lcd.putstr(f"ALPH:{state.scores[TEAM_1]:04d} BRAV:{state.scores[TEAM_2]:04d}")
        
        time.sleep_ms(20)

main()