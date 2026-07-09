import machine
import ssd1306
import time

# --- ИНИЦИАЛИЗАЦИЯ ПЕРИФЕРИИ ---
i2c = machine.SoftI2C(sda=machine.Pin(21), scl=machine.Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

speaker = machine.PWM(machine.Pin(19))
speaker.duty(0)

btn_up     = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP) 
btn_ok     = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP) 
btn_down   = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP) 
btn_player = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP) 

lives = 100
game_minutes = 45
wave_minutes = 5  

max_seconds = game_minutes * 60
seconds_left = max_seconds

max_wave_seconds = wave_minutes * 60
wave_seconds_left = max_wave_seconds

timer_active = False
state_menu = True

def beep(freq, duration_ms):
    try:
        speaker.freq(freq)
        speaker.duty(512)
        time.sleep_ms(duration_ms)
        speaker.duty(0)
    except:
        pass

def play_sound(sound_type):
    if sound_type == "click":        beep(850, 25)
    elif sound_type == "click_down": beep(600, 25)
    elif sound_type == "ok":
        beep(1000, 60); time.sleep_ms(20); beep(1400, 80)
    elif sound_type == "start":
        for _ in range(2): beep(880, 150); time.sleep_ms(40)
        beep(1300, 400)
    elif sound_type == "death":      beep(250, 180) 
    elif sound_type == "respawn_cancel":
        beep(900, 60); time.sleep_ms(30); beep(1200, 60); time.sleep_ms(30); beep(1600, 120)
    elif sound_type == "pause":      beep(600, 80); time.sleep_ms(40); beep(400, 120)
    elif sound_type == "resume":     beep(450, 60); time.sleep_ms(40); beep(800, 100)
    elif sound_type == "wave_release":
        for _ in range(3): beep(1100, 400); time.sleep_ms(100)
    elif sound_type == "game_over":
        for _ in range(2):
            for f in range(350, 950, 25): speaker.freq(f); speaker.duty(512); time.sleep_ms(4)
            for f in range(950, 350, -25): speaker.freq(f); speaker.duty(512); time.sleep_ms(4)
        speaker.duty(0)

def check_click(button_pin):
    if button_pin.value() == 0:
        time.sleep_ms(40) 
        if button_pin.value() == 0:
            while button_pin.value() == 0: time.sleep_ms(5) 
            return True
    return False

def render_setup_ui(step_title, current_val, metric=""):
    oled.fill(0)
    oled.rect(0, 0, 128, 64, 1)
    oled.fill_rect(2, 2, 124, 13, 1)
    oled.text("SETUP", 44, 5, 0)
    
    oled.text(step_title, 8, 25, 1)
    
    if step_title == "WAVE TIME:" and current_val == 0:
        val_str = "< WAVE: OFF >"
    else:
        val_str = "< {} {} >".format(current_val, metric)
        
    x_offset = 64 - (len(val_str) * 4)
    oled.text(val_str, x_offset, 45, 1)
    oled.show() 

def config_session():
    global lives, game_minutes, wave_minutes, max_seconds, seconds_left, max_wave_seconds, wave_seconds_left, state_menu, timer_active
    state_menu = True
    timer_active = False
    
    render_setup_ui("TOTAL LIVES:", lives)
    while True:
        if check_click(btn_up):
            lives = 10 if lives >= 990 else lives + 10
            render_setup_ui("TOTAL LIVES:", lives)
            play_sound("click")
        elif check_click(btn_down):
            lives = 990 if lives <= 10 else lives - 10
            render_setup_ui("TOTAL LIVES:", lives)
            play_sound("click_down")
        elif check_click(btn_ok):
            play_sound("ok")
            break
        time.sleep_ms(10)

    render_setup_ui("MATCH TIME:", game_minutes, "MIN")
    while True:
        if check_click(btn_up):
            game_minutes = 5 if game_minutes >= 180 else game_minutes + 5
            render_setup_ui("MATCH TIME:", game_minutes, "MIN")
            play_sound("click")
        elif check_click(btn_down):
            game_minutes = 180 if game_minutes <= 5 else game_minutes - 5
            render_setup_ui("MATCH TIME:", game_minutes, "MIN")
            play_sound("click_down")
        elif check_click(btn_ok):
            play_sound("ok")
            break
        time.sleep_ms(10)

    render_setup_ui("WAVE TIME:", wave_minutes, "MIN")
    while True:
        if check_click(btn_up):
            wave_minutes = 0 if wave_minutes >= 30 else wave_minutes + 1
            render_setup_ui("WAVE TIME:", wave_minutes, "MIN")
            play_sound("click")
        elif check_click(btn_down):
            wave_minutes = 30 if wave_minutes <= 0 else wave_minutes - 1
            render_setup_ui("WAVE TIME:", wave_minutes, "MIN")
            play_sound("click_down")
        elif check_click(btn_ok):
            play_sound("start")
            break
        time.sleep_ms(10)

    max_seconds = game_minutes * 60
    seconds_left = max_seconds
    
    max_wave_seconds = wave_minutes * 60
    wave_seconds_left = max_wave_seconds
    
    state_menu = False
    timer_active = True
    render_game_ui()

def render_game_ui():
    oled.fill(0)
    m, s = seconds_left // 60, seconds_left % 60
    time_str = "{:02d}:{:02d}".format(m, s)
    
    if max_wave_seconds == 0:
        oled.rect(0, 0, 128, 64, 1)
        oled.hline(0, 16, 128, 1)
        oled.text("MISSION TIMER", 12, 5, 1)
        oled.text("TIME: {}".format(time_str), 16, 26, 1)
        oled.line(0, 44, 128, 44, 1)
        oled.text("LIVES LEFT: {}".format(lives), 8, 51, 1)
        
    else:
        wm, ws = wave_seconds_left // 60, wave_seconds_left % 60
        wave_str = "{:02d}:{:02d}".format(wm, ws)
        
        oled.text("M:{}".format(time_str), 2, 4, 1)
        oled.text("LIVES:{}".format(lives), 66, 4, 1)
        oled.hline(0, 15, 128, 1)
        
        oled.text("NEXT WAVE IN:", 12, 22, 1)
        oled.text("[ {} ]".format(wave_str), 36, 36, 1)
        
        oled.fill_rect(0, 53, 128, 11, 1)
        if max_wave_seconds > 0:
            fill_width = int(124 * (wave_seconds_left / max_wave_seconds))
            oled.fill_rect(2, 55, fill_width, 7, 0)

    if seconds_left == 0:
        oled.fill_rect(4, 16, 120, 32, 0)
        oled.rect(4, 16, 120, 32, 1)
        oled.text("GAME OVER!", 24, 28, 1)
    elif not timer_active:
        oled.fill_rect(4, 16, 120, 32, 0)
        oled.rect(4, 16, 120, 32, 1)
        oled.text("- PAUSED -", 24, 28, 1)
        
    oled.show()

# --- СТАРТ ТОЧКИ ---
config_session()
last_time_checkpoint = time.ticks_ms()

# --- ГЛАВНЫЙ ИГРОВОЙ ЦИКЛ ---
while True:
    if not state_menu:
        if check_click(btn_ok):
            config_session()
            last_time_checkpoint = time.ticks_ms()
            continue

        if check_click(btn_up) or check_click(btn_down):
            timer_active = not timer_active
            render_game_ui()
            if timer_active: play_sound("resume")
            else: play_sound("pause")

        if btn_player.value() == 0:
            hold_start = time.ticks_ms()
            is_hold = False
            while btn_player.value() == 0:
                if time.ticks_diff(time.ticks_ms(), hold_start) > 2000:
                    is_hold = True
                    lives += 1  
                    render_game_ui()
                    play_sound("respawn_cancel")
                    while btn_player.value() == 0: time.sleep_ms(10)
                    break
                time.sleep_ms(10)
            
            if not is_hold and lives > 0:
                lives -= 1
                render_game_ui()
                play_sound("death")

        if timer_active and seconds_left > 0:
            if time.ticks_diff(time.ticks_ms(), last_time_checkpoint) >= 1000:
                seconds_left -= 1
                if max_wave_seconds > 0 and wave_seconds_left > 0:
                    wave_seconds_left -= 1
                if max_wave_seconds > 0 and wave_seconds_left == 0 and seconds_left > 0:
                    render_game_ui()
                    play_sound("wave_release")
                    wave_seconds_left = max_wave_seconds
                render_game_ui()
                last_time_checkpoint = time.ticks_ms()
                
                if seconds_left == 0:
                    timer_active = False
                    wave_seconds_left = 0
                    render_game_ui()
                    play_sound("game_over")

    time.sleep_ms(15)
