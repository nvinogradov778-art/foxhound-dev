import machine
import ssd1306
import time

# ========== DFPLAYER (полностью без PWM) ==========
class DFPlayer:
    """Драйвер для DFPlayer Mini через UART."""
    def __init__(self, uart):
        self.uart = uart
        self._send_cmd(0x0F, 0x00, 0x00)   # сброс
        time.sleep_ms(200)
        self.set_volume(20)               # громкость 0..30
        self._send_cmd(0x09, 0x00, 0x00)  # повтор выключен

    def _send_cmd(self, cmd, arg_hi, arg_lo):
        data = bytearray([0x7E, 0xFF, 0x06, cmd, 0x00, arg_hi, arg_lo, 0xFE, 0xEF])
        self.uart.write(data)
        time.sleep_ms(50)

    def set_volume(self, vol):
        vol = max(0, min(30, vol))
        self._send_cmd(0x06, 0x00, vol)

    def play(self, track_num):
        """Воспроизвести трек с номером track_num (1..3000)."""
        hi = (track_num >> 8) & 0xFF
        lo = track_num & 0xFF
        self._send_cmd(0x03, hi, lo)

    def stop(self):
        self._send_cmd(0x16, 0x00, 0x00)

    def pause(self):
        self._send_cmd(0x0E, 0x00, 0x00)

    def resume(self):
        self._send_cmd(0x0D, 0x00, 0x00)

# ========== ИНИЦИАЛИЗАЦИЯ ПЕРИФЕРИИ ==========
i2c = machine.SoftI2C(sda=machine.Pin(21), scl=machine.Pin(22), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

btn_up     = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
btn_ok     = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)
btn_down   = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_UP)
btn_player = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)

# ========== ИНИЦИАЛИЗАЦИЯ DFPLAYER ==========
try:
    uart_df = machine.UART(2, baudrate=9600, tx=17, rx=16, timeout=100)
    dfplayer = DFPlayer(uart_df)
    dfplayer.set_volume(20)
    print("DFPlayer инициализирован")
except Exception as e:
    print("DFPlayer не обнаружен, звук отключён:", e)
    dfplayer = None

# ========== СООТВЕТСТВИЕ ЗВУКОВ НОМЕРАМ ТРЕКОВ ==========
SOUND_TRACKS = {
    "start":          1,   # старт игры
    "wave_release":   2,   # начало волны
    "game_over":      3,   # конец игры
    "click":          4,   # нажатие вверх
    "click_down":     5,   # нажатие вниз
    "ok":             6,   # подтверждение
    "death":          7,   # потеря жизни
    "respawn_cancel": 8,   # добавление жизни (удержание)
    "pause":          9,   # пауза
    "resume":         10   # возобновление
}

def play_sound(sound_type):
    """Воспроизвести звук через DFPlayer. Если DFPlayer отсутствует – ничего не делать."""
    if dfplayer is None:
        return
    track = SOUND_TRACKS.get(sound_type)
    if track is not None:
        dfplayer.play(track)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def check_click(button_pin):
    if button_pin.value() == 0:
        time.sleep_ms(40)
        if button_pin.value() == 0:
            while button_pin.value() == 0:
                time.sleep_ms(5)
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

# ========== НАСТРОЙКА ИГРЫ ==========
def config_session():
    global lives, game_minutes, wave_minutes, max_seconds, seconds_left
    global max_wave_seconds, wave_seconds_left, state_menu, timer_active

    if dfplayer is not None:
        dfplayer.stop()          # остановить текущий трек при входе в настройку

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
            play_sound("start")   # трек 1 – старт игры
            break
        time.sleep_ms(10)

    max_seconds = game_minutes * 60
    seconds_left = max_seconds

    max_wave_seconds = wave_minutes * 60
    wave_seconds_left = max_wave_seconds

    state_menu = False
    timer_active = True
    render_game_ui()

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ (для доступа в функциях) ==========
lives = 100
game_minutes = 45
wave_minutes = 5

max_seconds = game_minutes * 60
seconds_left = max_seconds

max_wave_seconds = wave_minutes * 60
wave_seconds_left = max_wave_seconds

timer_active = False
state_menu = True

# ========== ЗАПУСК ==========
config_session()
last_time_checkpoint = time.ticks_ms()

# ========== ГЛАВНЫЙ ИГРОВОЙ ЦИКЛ ==========
while True:
    if not state_menu:
        # Кнопка OK — перейти в настройки
        if check_click(btn_ok):
            if dfplayer is not None:
                dfplayer.stop()
            config_session()
            last_time_checkpoint = time.ticks_ms()
            continue

        # Кнопки UP/DOWN — пауза/возобновление
        if check_click(btn_up) or check_click(btn_down):
            timer_active = not timer_active
            render_game_ui()
            if timer_active:
                play_sound("resume")
                if dfplayer is not None:
                    dfplayer.resume()   # если DFPlayer был на паузе, возобновить
            else:
                play_sound("pause")
                if dfplayer is not None:
                    dfplayer.pause()

        # Кнопка PLAYER — убавление жизни или добавление при удержании
        if btn_player.value() == 0:
            hold_start = time.ticks_ms()
            is_hold = False
            while btn_player.value() == 0:
                if time.ticks_diff(time.ticks_ms(), hold_start) > 2000:
                    is_hold = True
                    lives += 1
                    render_game_ui()
                    play_sound("respawn_cancel")
                    while btn_player.value() == 0:
                        time.sleep_ms(10)
                    break
                time.sleep_ms(10)

            if not is_hold and lives > 0:
                lives -= 1
                render_game_ui()
                play_sound("death")

        # Таймер
        if timer_active and seconds_left > 0:
            if time.ticks_diff(time.ticks_ms(), last_time_checkpoint) >= 1000:
                seconds_left -= 1
                if max_wave_seconds > 0 and wave_seconds_left > 0:
                    wave_seconds_left -= 1
                if max_wave_seconds > 0 and wave_seconds_left == 0 and seconds_left > 0:
                    render_game_ui()
                    play_sound("wave_release")   # трек 2 – начало волны
                    wave_seconds_left = max_wave_seconds
                render_game_ui()
                last_time_checkpoint = time.ticks_ms()

                if seconds_left == 0:
                    timer_active = False
                    wave_seconds_left = 0
                    render_game_ui()
                    play_sound("game_over")      # трек 3 – конец игры

    time.sleep_ms(15)
