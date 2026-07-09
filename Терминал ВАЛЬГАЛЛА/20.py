import sys
import os
import random
import datetime
import time
import numpy as np

from PyQt6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QLineEdit,
                             QVBoxLayout, QWidget, QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QTextCursor

import pygame
import pygame.sndarray

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================
PASSWORD     = "777"
ORG_LOGIN    = "ЕРЕТИК"
ORG_PASSWORD = "bufuda1998"
TARGET_IP    = "127.0.0.1"

COLOR_TEXT = "#00FF41"
COLOR_BG   = "#0D0D0D"
COLOR_WARN = "#FFFF00"
COLOR_ERR  = "#FF0000"
COLOR_LOG  = "#888888"

BASE_FILES = [f"SEC_DATA_BLOCK_{i:02}.DAT" for i in range(1, 21)] + [
    "ENCRYPTED_CORE.BIN",
    "LOG_FINAL.DAT",
]

TERMINAL_FONT = QFont("Courier New", 18, QFont.Weight.Bold)
HUD_FONT      = QFont("Courier New", 12, QFont.Weight.Bold)

# =============================================================================
# МИНИГРА: ЗАХВАТ ЧАСТОТЫ
# =============================================================================
SIGNAL_WIDTH      = 38
SIGNAL_ZONE       = 5
SIGNAL_ROUNDS     = 3
SIGNAL_BASE_SPEED = 0.09
SIGNAL_MAX_ERRORS = 2


# =============================================================================
# АУДИО ДВИЖОК
# =============================================================================
class Audio:
    """
    Генерирует все звуки программно через numpy + pygame.mixer.
    Внешние звуковые файлы НЕ нужны — всё синтезируется на лету.

    Именованные звуки (audio.play("name")):
      "access_ok"   — успешный вход игрока
      "access_org"  — вход организатора
      "access_fail" — неверный пароль
      "usb_ok"      — USB-носитель определён
      "signal_hit"  — захват сигнала в минигре (попадание)
      "signal_miss" — промах в минигре
      "alert"       — тревога, начало минигры
      "sync_ok"     — ключ синхронизирован после минигры
      "lockout"     — провал, блокировка системы
      "countdown"   — тик обратного отсчёта при lockout
      "boot_tick"   — тик при загрузке системы
      "ambient"     — фоновый шум (зацикленный, канал 7)
    """
    RATE = 44100

    def __init__(self):
        pygame.mixer.pre_init(self.RATE, -16, 1, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(8)
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._ambient_ch: pygame.mixer.Channel | None = None
        self._build_all()

    # ------------------------------------------------------------------
    # ГЕНЕРАТОРЫ ВОЛН
    # ------------------------------------------------------------------
    def _sine(self, freq: float, dur_ms: int, vol: float = 0.6,
              fade_ms: int = 10) -> np.ndarray:
        n   = int(self.RATE * dur_ms / 1000)
        t   = np.linspace(0, dur_ms / 1000, n, endpoint=False)
        wav = np.sin(2 * np.pi * freq * t)
        fade = int(self.RATE * fade_ms / 1000)
        if fade < n:
            wav[-fade:] *= np.linspace(1, 0, fade)
        return (wav * vol * 32767).astype(np.int16)

    def _noise(self, dur_ms: int, vol: float = 0.15) -> np.ndarray:
        n = int(self.RATE * dur_ms / 1000)
        return (np.random.uniform(-1, 1, n) * vol * 32767).astype(np.int16)

    def _sweep(self, f0: float, f1: float, dur_ms: int,
               vol: float = 0.5) -> np.ndarray:
        n     = int(self.RATE * dur_ms / 1000)
        freqs = np.linspace(f0, f1, n)
        phase = np.cumsum(2 * np.pi * freqs / self.RATE)
        wav   = np.sin(phase)
        return (wav * vol * 32767).astype(np.int16)

    def _concat(self, *arrays: np.ndarray) -> np.ndarray:
        return np.concatenate(arrays)

    def _to_sound(self, arr: np.ndarray) -> pygame.mixer.Sound:
        return pygame.sndarray.make_sound(arr)

    # ------------------------------------------------------------------
    # ПРЕДГЕНЕРАЦИЯ ВСЕХ ЗВУКОВ
    # ------------------------------------------------------------------
    def _build_all(self):
        R = self._cache

        # Успешный вход игрока — два восходящих тона
        R["access_ok"] = self._to_sound(self._concat(
            self._sine(800,  80),
            self._sine(1200, 120),
        ))

        # Вход организатора — трель вверх
        R["access_org"] = self._to_sound(self._concat(
            self._sine(1000, 60),
            self._sine(1400, 60),
            self._sine(1800, 120),
        ))

        # Неверный пароль — низкий двойной сигнал с шумом
        R["access_fail"] = self._to_sound(self._concat(
            self._sine(280, 200),
            self._noise(40,  0.05),
            self._sine(220, 250),
        ))

        # USB определён — пик + свип вверх
        R["usb_ok"] = self._to_sound(self._concat(
            self._sine(1000, 80),
            self._sweep(800, 1400, 100),
        ))

        # Попадание в минигре — двойной высокий
        R["signal_hit"] = self._to_sound(self._concat(
            self._sine(1200, 60),
            self._sine(1600, 80),
        ))

        # Промах в минигре — резкий низкий + шум
        R["signal_miss"] = self._to_sound(self._concat(
            self._sine(300, 120, vol=0.7),
            self._noise(80, 0.1),
        ))

        # Тревога / начало минигры — нарастающий свип
        R["alert"] = self._to_sound(self._concat(
            self._sweep(400, 900,  200),
            self._sweep(900, 400,  200),
            self._sweep(400, 1100, 150),
        ))

        # Ключ синхронизирован — приятная трель
        R["sync_ok"] = self._to_sound(self._concat(
            self._sine(900,  60),
            self._sine(1100, 60),
            self._sine(1400, 100),
        ))

        # Lockout — нисходящие сигналы тревоги
        R["lockout"] = self._to_sound(self._concat(
            self._sine(500, 200, vol=0.8),
            self._noise(60, 0.15),
            self._sine(380, 250, vol=0.8),
            self._noise(60, 0.15),
            self._sine(260, 350, vol=0.9),
            self._noise(100, 0.2),
        ))

        # Тик обратного отсчёта
        R["countdown"] = self._to_sound(self._sine(660, 120, vol=0.5))

        # Тик загрузки — тихий щелчок
        R["boot_tick"] = self._to_sound(self._concat(
            self._sine(1800, 20, vol=0.2),
            self._noise(15, 0.05),
        ))

        # Фоновый шум — 3 сек статики + тихий гул 60 Гц
        base_noise = self._noise(3000, vol=0.04)
        hum        = self._sine(60, 3000, vol=0.03)
        ambient    = np.clip(
            base_noise.astype(np.int32) + hum.astype(np.int32),
            -32767, 32767
        ).astype(np.int16)
        R["ambient"] = self._to_sound(ambient)

    # ------------------------------------------------------------------
    # ПУБЛИЧНЫЙ API
    # ------------------------------------------------------------------
    def beep(self, freq: int, dur_ms: int, vol: float = 0.55) -> None:
        """Произвольный синусоидальный тон."""
        arr = self._sine(float(freq), dur_ms, vol=vol)
        snd = self._to_sound(arr)
        ch  = pygame.mixer.find_channel()
        if ch:
            ch.play(snd)

    def play(self, name: str) -> None:
        """Именованный звук из кэша."""
        snd = self._cache.get(name)
        if not snd:
            return
        ch = pygame.mixer.find_channel()
        if ch:
            ch.play(snd)

    def start_ambient(self) -> None:
        """Запустить фоновый шум (зацикленно на канале 7)."""
        snd = self._cache.get("ambient")
        if snd and self._ambient_ch is None:
            self._ambient_ch = pygame.mixer.Channel(7)
            self._ambient_ch.play(snd, loops=-1)

    def stop_ambient(self) -> None:
        if self._ambient_ch:
            self._ambient_ch.stop()
            self._ambient_ch = None


# Глобальный экземпляр
audio = Audio()


# =============================================================================
# УТИЛИТЫ
# =============================================================================
def beep(freq: int, dur: int) -> None:
    audio.beep(freq, dur)


def active_drives() -> list[str]:
    """Список примонтированных USB на Linux (/media, /run/media)."""
    mounts = []
    for base in ["/media", "/run/media"]:
        if os.path.isdir(base):
            try:
                for user in os.listdir(base):
                    user_path = os.path.join(base, user)
                    if os.path.isdir(user_path):
                        for dev in os.listdir(user_path):
                            mounts.append(os.path.join(user_path, dev))
            except PermissionError:
                pass
    return mounts


# =============================================================================
# ЛОГИЧЕСКИЙ ПОТОК
# =============================================================================
class TerminalThread(QThread):
    output       = pyqtSignal(str, str, bool)
    input_ready  = pyqtSignal(bool, str)
    hud_node     = pyqtSignal(str)
    clear_screen = pyqtSignal()
    redraw_line  = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.user_input    = None
        self.arrow_key     = None
        self.start_drives  = active_drives()
        self.file_delay_ms = 120
        self.fake_files    = BASE_FILES[:]

        self.sig_rounds     = SIGNAL_ROUNDS
        self.sig_zone       = SIGNAL_ZONE
        self.sig_max_errors = SIGNAL_MAX_ERRORS
        self.sig_speed      = SIGNAL_BASE_SPEED

    # ------------------------------------------------------------------
    # ВВОД / ВЫВОД
    # ------------------------------------------------------------------
    def wait_input(self, prompt: str = "") -> str:
        self.user_input = None
        self.input_ready.emit(True, prompt)
        while self.user_input is None:
            self.msleep(100)
        return self.user_input

    def wait_arrow(self) -> str:
        self.arrow_key = None
        while self.arrow_key is None:
            self.msleep(30)
        key = self.arrow_key
        self.arrow_key = None
        return key

    def print_line(self, text: str, color: str = COLOR_TEXT, animated: bool = True) -> None:
        self.output.emit(text, color, animated)
        if animated:
            self.msleep(len(text) * 20 + 150)

    def print_raw(self, text: str, color: str = COLOR_TEXT) -> None:
        self.output.emit(text, color, False)

    def divider(self, char: str = "-", width: int = 60) -> None:
        self.print_raw(char * width)

    def ask_int(self, prompt: str, default: int, lo: int, hi: int) -> int:
        raw = self.wait_input(prompt)
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            self.print_raw(f"  ! Вне диапазона [{lo}..{hi}], оставлено: {default}", COLOR_WARN)
        except ValueError:
            self.print_raw(f"  ! Неверный формат, оставлено: {default}", COLOR_WARN)
        return default

    def ask_float(self, prompt: str, default: float, lo: float, hi: float) -> float:
        raw = self.wait_input(prompt)
        try:
            val = float(raw.replace(",", "."))
            if lo <= val <= hi:
                return val
            self.print_raw(f"  ! Вне диапазона [{lo}..{hi}], оставлено: {default}", COLOR_WARN)
        except ValueError:
            self.print_raw(f"  ! Неверный формат, оставлено: {default}", COLOR_WARN)
        return default

    # ------------------------------------------------------------------
    # ФИНАЛИЗАЦИЯ
    # ------------------------------------------------------------------
    def write_lock_file(self, drive: str) -> bool:
        try:
            path = os.path.join(drive, "VALHALLA_LOCK.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("--- VALHALLA SYSTEM SECURITY LOG ---\n")
                f.write("STATUS: SUCCESSFUL_DATA_EXTRACTION\n")
                f.write(f"TIMESTAMP: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
                f.write(f"SOURCE_IP: {TARGET_IP}\n")
                f.write(f"SESSION_ID: {random.randint(10000, 99999)}-XQ\n")
                f.write("------------------------------------\n")
                f.flush()
                os.fsync(f.fileno())
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # ГЛАВНЫЙ ЦИКЛ
    # ------------------------------------------------------------------
    def run(self) -> None:
        audio.start_ambient()
        while True:
            self.clear_screen.emit()
            self.hud_node.emit("BOOT_SEQUENCE")
            self._boot()
            self.hud_node.emit("AUTH_PROTOCOL")
            is_organizer = self._auth()
            if is_organizer:
                self._organizer_setup()
                continue
            self._connect_loop()

    # ------------------------------------------------------------------
    # СЕКЦИИ ЛОГИКИ
    # ------------------------------------------------------------------
    def _boot(self) -> None:
        self.print_raw("UNIX System V Release 4.0 (tty1)")
        self.msleep(400)
        for line in [
            "[    0.00 ] UNIX Kernel version 4.0.1-release",
            "[    0.85 ] usb: host controller initialized",
            "[    1.50 ] fs: mounting root filesystem... done",
            "[    2.00 ] services: daemon started",
        ]:
            audio.play("boot_tick")
            self.print_raw(line)
            self.msleep(200)

    def _auth(self) -> bool:
        while True:
            login = self.wait_input("login: ")
            pwd   = self.wait_input("password: ")

            if login == ORG_LOGIN and pwd == ORG_PASSWORD:
                audio.play("access_org")
                self.print_line("\n[ ACCESS GRANTED: ORGANIZER MODE ]")
                return True

            if pwd == PASSWORD:
                audio.play("access_ok")
                self.print_line("\nWelcome. Secure connection ready.")
                return False

            audio.play("access_fail")
            self.print_line("\nLogin incorrect. Try again.\n", COLOR_ERR)
            self.msleep(1000)

    # ------------------------------------------------------------------
    # МЕНЮ ОРГАНИЗАТОРА
    # ------------------------------------------------------------------
    def _organizer_setup(self) -> None:
        while True:
            self.clear_screen.emit()
            self.divider("=")
            self.print_raw("  VALHALLA  ::  ПАНЕЛЬ АДМИНИСТРАТОРА")
            self.divider("=")
            self.print_raw("")
            self.print_raw(f"  1. ВРЕМЯ КОПИРОВАНИЯ      [ {self._fmt_copy_time()} ]")
            self.print_raw(f"  2. РАУНДОВ В МИНИГРЕ       [ {self.sig_rounds} ]")
            self.print_raw(f"  3. ШИРИНА ПРИЦЕЛА          [ {self.sig_zone} ]")
            self.print_raw(f"  4. НАЧАЛЬНАЯ СКОРОСТЬ      [ {self.sig_speed:.3f} сек/тик ]")
            self.print_raw(f"  5. ДОПУСТИМО ПРОМАХОВ      [ {self.sig_max_errors} ]")
            self.print_raw(f"  6. ПОЗИЦИЯ МИНИГРЫ         [ {self._fmt_lock_point()} ]")
            self.print_raw("")
            self.print_raw("  0. ВЫЙТИ ИЗ НАСТРОЕК")
            self.print_raw("")
            self.divider("=")

            choice = self.wait_input("  ВЫБОР: ")

            if choice == "0":
                self.print_line("\nВЫХОД ИЗ РЕЖИМА НАСТРОЙКИ...")
                self.msleep(1000)
                return

            elif choice == "1":
                minutes = self.ask_float("  ВРЕМЯ (МИН, 0.5–60): ", 5.0, 0.5, 60.0)
                count = max(len(BASE_FILES), int(minutes * 24))
                self.fake_files    = [f"SEC_DATA_BLOCK_{i:03}.DAT" for i in range(1, count + 1)]
                self.fake_files   += ["ENCRYPTED_CORE.BIN", "LOG_FINAL.DAT"]
                self.file_delay_ms = int((minutes * 60 * 1000) / len(self.fake_files))
                self.print_raw(f"  OK: {len(self.fake_files)} файлов, ~{minutes} мин")

            elif choice == "2":
                self.sig_rounds = self.ask_int("  РАУНДОВ (1–5): ", self.sig_rounds, 1, 5)

            elif choice == "3":
                self.sig_zone = self.ask_int("  ШИРИНА ПРИЦЕЛА (2–12): ", self.sig_zone, 2, 12)
                self.print_raw(f"  OK: зона захвата = {self.sig_zone} симв.")

            elif choice == "4":
                self.sig_speed = self.ask_float(
                    "  СКОРОСТЬ (0.02=быстро, 0.2=медленно): ",
                    self.sig_speed, 0.02, 0.2
                )

            elif choice == "5":
                self.sig_max_errors = self.ask_int(
                    "  МАКС ПРОМАХОВ (0–5): ",
                    self.sig_max_errors, 0, 5
                )

            elif choice == "6":
                self.print_raw("  Введите % прогресса копирования когда появится минигра,")
                self.print_raw("  или 0 для случайного момента (30–70%).")
                val = self.ask_int("  ПОЗИЦИЯ % (0–95): ", 0, 0, 95)
                self._lock_point_override = val if val > 0 else None
                label = f"{val}%" if val > 0 else "случайно"
                self.print_raw(f"  OK: минигра появится в {label}")

            self.msleep(800)

    def _fmt_copy_time(self) -> str:
        total_ms = self.file_delay_ms * len(self.fake_files)
        secs = total_ms / 1000
        return f"{secs/60:.1f} мин"

    def _fmt_lock_point(self) -> str:
        pt = getattr(self, "_lock_point_override", None)
        return f"{pt}%" if pt else "случайно"

    # ------------------------------------------------------------------
    # МИНИГРА: ЗАХВАТ ЧАСТОТЫ
    # ------------------------------------------------------------------
    def _signal_lock_game(self) -> bool:
        W    = SIGNAL_WIDTH
        ZONE = self.sig_zone

        self.arrow_key = None
        self.msleep(100)
        self.arrow_key = None

        self.print_raw("")
        self.print_raw("  ┌─────────────────────────────────────────────┐")
        self.print_raw("  │   VALHALLA  ::  SIGNAL LOCK PROTOCOL        │")
        self.print_raw("  │                                             │")
        self.print_raw("  │  ENTER — поймать сигнал в прицеле           │")
        self.print_raw("  │                                             │")
        self.print_raw("  │  >>> НАЖМИТЕ ENTER ЧТОБЫ НАЧАТЬ <<<         │")
        self.print_raw("  └─────────────────────────────────────────────┘")
        self.print_raw("")

        while True:
            key = self.arrow_key
            if key is not None:
                self.arrow_key = None
                if key == "ENTER":
                    break
            self.msleep(50)

        self.msleep(80)
        self.arrow_key = None

        marker_pos = 0
        marker_dir = 1
        speed      = self.sig_speed
        cursor_pos = (W - ZONE) // 2
        errors     = 0
        hits       = 0

        self.print_raw(self._render_scale(W, ZONE, marker_pos, cursor_pos))
        tick_start = time.time()

        while hits < self.sig_rounds:
            if self.arrow_key is not None:
                key = self.arrow_key
                self.arrow_key = None
                if key == "ENTER":
                    captured = cursor_pos <= marker_pos < cursor_pos + ZONE
                    if captured:
                        audio.play("signal_hit")
                        hits += 1
                        self.output.emit(
                            f"  [ ЗАХВАТ {hits}/{self.sig_rounds} ] СИГНАЛ ЗАФИКСИРОВАН",
                            COLOR_TEXT, False
                        )
                        self.msleep(600)
                        self.arrow_key = None
                        if hits < self.sig_rounds:
                            speed = max(0.03, speed * 0.75)
                            self.print_raw(self._render_scale(W, ZONE, marker_pos, cursor_pos))
                    else:
                        audio.play("signal_miss")
                        errors += 1
                        bar = "X" * errors + "O" * (self.sig_max_errors + 1 - errors)
                        self.output.emit(f"  [!!] МИМО  [{bar}]", COLOR_ERR, False)
                        self.msleep(500)
                        self.arrow_key = None
                        if errors > self.sig_max_errors:
                            return False
                        self.print_raw(self._render_scale(W, ZONE, marker_pos, cursor_pos))

            now = time.time()
            if now - tick_start >= speed:
                marker_pos += marker_dir
                if marker_pos >= W - 1:
                    marker_dir = -1
                elif marker_pos <= 0:
                    marker_dir = 1
                tick_start = now

            self.redraw_line.emit(
                self._render_scale(W, ZONE, marker_pos, cursor_pos),
                COLOR_TEXT
            )
            self.msleep(20)

        return True

    @staticmethod
    def _render_scale(width: int, zone: int, marker: int, cursor: int) -> str:
        cells = []
        for i in range(width):
            in_zone   = cursor <= i < cursor + zone
            is_marker = (i == marker)
            if is_marker and in_zone:
                cells.append("*")
            elif is_marker:
                cells.append("O")
            elif i == cursor:
                cells.append("[")
            elif i == cursor + zone - 1:
                cells.append("]")
            elif in_zone:
                cells.append(" ")
            else:
                cells.append(".")
        return "  |" + "".join(cells) + "|"

    def _lockout(self) -> None:
        self.hud_node.emit("!!! INTRUSION DETECTED !!!")
        audio.play("lockout")
        self.msleep(400)

        self.clear_screen.emit()
        self.msleep(200)

        self.print_raw("")
        self.print_raw("")
        self.print_raw("  ██╗███╗   ██╗████████╗██████╗ ██╗   ██╗███████╗██╗ ██████╗ ███╗   ██╗", COLOR_ERR)
        self.print_raw("  ██║████╗  ██║╚══██╔══╝██╔══██╗██║   ██║╚════██║██║██╔═══██╗████╗  ██║", COLOR_ERR)
        self.print_raw("  ██║██╔██╗ ██║   ██║   ██████╔╝██║   ██║    ██╔╝██║██║   ██║██╔██╗ ██║", COLOR_ERR)
        self.print_raw("  ██║██║╚██╗██║   ██║   ██╔══██╗██║   ██║   ██╔╝ ██║██║   ██║██║╚██╗██║", COLOR_ERR)
        self.print_raw("  ██║██║ ╚████║   ██║   ██║  ██║╚██████╔╝   ██║  ██║╚██████╔╝██║ ╚████║", COLOR_ERR)
        self.print_raw("  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝", COLOR_ERR)
        self.print_raw("")
        self.print_raw("  ╔═══════════════════════════════════════════════════════════════╗", COLOR_ERR)
        self.print_raw("  ║                                                               ║", COLOR_ERR)
        self.print_raw("  ║   ВЫЯВЛЕНА ПОПЫТКА НЕСАНКЦИОНИРОВАННОГО ВТОРЖЕНИЯ             ║", COLOR_ERR)
        self.print_raw("  ║                                                               ║", COLOR_ERR)
        self.print_raw("  ║   ИНИЦИИРОВАНА АВАРИЙНАЯ ПЕРЕЗАГРУЗКА СИСТЕМЫ                ║", COLOR_ERR)
        self.print_raw("  ║   ВСЕ АКТИВНЫЕ СЕССИИ ПРИНУДИТЕЛЬНО ЗАВЕРШЕНЫ                ║", COLOR_ERR)
        self.print_raw("  ║   ДАННЫЕ ИНЦИДЕНТА ПЕРЕДАНЫ В СЛУЖБУ БЕЗОПАСНОСТИ             ║", COLOR_ERR)
        self.print_raw("  ║                                                               ║", COLOR_ERR)
        self.print_raw("  ╚═══════════════════════════════════════════════════════════════╝", COLOR_ERR)
        self.print_raw("")
        self.msleep(800)

        ts = datetime.datetime.now()
        for msg in [
            f"  [ {ts:%H:%M:%S} ]  INCIDENT_ID: {random.randint(10000,99999)}-SEC",
            f"  [ {ts:%H:%M:%S} ]  SOURCE: {TARGET_IP}",
            f"  [ {ts:%H:%M:%S} ]  THREAT_LEVEL: CRITICAL",
            f"  [ {ts:%H:%M:%S} ]  ACTION: EMERGENCY_REBOOT_SCHEDULED",
        ]:
            self.print_raw(msg, COLOR_ERR)
            self.msleep(500)

        self.print_raw("")
        self.print_raw("  Аварийная перезагрузка через...", COLOR_ERR)
        for i in range(5, 0, -1):
            self.print_raw(f"  {i}...", COLOR_ERR)
            audio.play("countdown")
            self.msleep(850)
        audio.beep(200, 1000)

    def _connect_loop(self) -> None:
        while True:
            ip = self.wait_input("user@terminal:~$ ")
            if ip.strip() != TARGET_IP:
                self.print_line(f"Host {ip} not found.")
                continue

            self.print_line(f">>> Connecting to {TARGET_IP}...")
            self.msleep(1000)
            self.hud_node.emit("VALHALLA_CORE")
            self.print_line(">>> Session authorized. Remote shell active.")
            self.msleep(800)

            for line in [
                "╔════════════════════════════════════════════════════════════╗",
                "║  V  A  L  H  A  L  L  A    S  E  R  V  E  R    C  O  R  E  ║",
                "╚════════════════════════════════════════════════════════════╝",
            ]:
                self.print_raw(line)
                self.msleep(80)

            self._main_menu_loop()
            return

    def _main_menu_loop(self) -> None:
        while True:
            self.divider()
            for item in [
                "1. КОПИРОВАТЬ ДАННЫЕ НА НОСИТЕЛЬ",
                "2. СКАНЕР СЕТЕВОГО ОКРУЖЕНИЯ",
                "3. ПРОСМОТР СИСТЕМНЫХ ЛОГОВ",
                "4. ОЧИСТИТЬ ЭКРАН ТЕРМИНАЛА",
                "5. ПЕРЕЗАГРУЗКА ЛОКАЛЬНОЙ СИСТЕМЫ",
                "6. ЗАВЕРШИТЬ СЕТЕВОЙ СЕАНС",
            ]:
                self.print_raw(item)
            self.divider()

            choice = self.wait_input(f"root@{TARGET_IP}:~# ")

            if choice == "1":
                self._cmd_copy()
            elif choice == "2":
                self._cmd_scan()
            elif choice == "3":
                self._cmd_logs()
            elif choice == "4":
                self.clear_screen.emit()
            elif choice == "5":
                self.print_line("\n>>> ИНИЦИАЛИЗАЦИЯ ПЕРЕЗАГРУЗКИ...", COLOR_ERR)
                self.msleep(1000)
                return
            elif choice == "6":
                return

    # ------------------------------------------------------------------
    # КОМАНДЫ МЕНЮ
    # ------------------------------------------------------------------
    def _cmd_copy(self) -> None:
        self.print_line(">>> ПРОВЕРКА USB_SLOTS...")
        drive = self._wait_for_usb()
        self.print_line(f"[ OK ] УСТРОЙСТВО {drive} ИДЕНТИФИЦИРОВАНО.\n")
        audio.play("usb_ok")

        pt = getattr(self, "_lock_point_override", None)
        lock_point = pt if pt else random.randint(30, 70)
        lock_done  = False

        for i, filename in enumerate(self.fake_files):
            if not os.path.exists(drive):
                self.print_line("\n!!! СБОЙ: НОСИТЕЛЬ ИЗВЛЕЧЕН", COLOR_ERR)
                return

            progress = int((i + 1) / len(self.fake_files) * 100)

            if progress >= lock_point and not lock_done:
                audio.play("alert")
                self.print_raw("")
                self.print_raw(f"[ ALERT ] ШИФРОВАНИЕ БЛОКА {progress}% — ТРЕБУЕТСЯ СИНХРОНИЗАЦИЯ КЛЮЧА", COLOR_WARN)
                self.print_raw("[ ЗАХВАТИТЕ СИГНАЛ ДЛЯ ПРОДОЛЖЕНИЯ ПЕРЕДАЧИ ]", COLOR_WARN)
                self.print_raw("")
                passed = self._signal_lock_game()
                if not passed:
                    self._lockout()
                    return
                audio.play("sync_ok")
                self.print_raw("[ OK ] КЛЮЧ СИНХРОНИЗИРОВАН. ПРОДОЛЖЕНИЕ ПЕРЕДАЧИ...", COLOR_TEXT)
                self.print_raw("")
                lock_done = True

            filled = progress // 5
            bar = "#" * filled + "." * (20 - filled)
            self.print_raw(f"[{bar}] {progress}% ЗАПИСЬ: {filename}")
            self.msleep(self.file_delay_ms)

        if self.write_lock_file(drive):
            self.print_line("\n[ OK ] SECURITY LOCK FILE GENERATED.")

        audio.play("access_ok")
        self.print_line("\n[ УСПЕХ ] ПЕРЕДАЧА ЗАВЕРШЕНА. ИЗВЛЕКИТЕ УСТРОЙСТВО!")
        while os.path.exists(drive):
            self.msleep(500)

    def _wait_for_usb(self) -> str:
        while True:
            new = [d for d in active_drives() if d not in self.start_drives]
            if new:
                return new[0]
            self.print_raw(">>> ОЖИДАНИЕ НОСИТЕЛЯ (INSERT USB)...", COLOR_WARN)
            self.msleep(2000)

    def _cmd_scan(self) -> None:
        self.print_line(">>> Scanning subnet...")
        for _ in range(5):
            ip = f"192.168.1.{random.randint(2, 254)}"
            audio.play("boot_tick")
            self.print_raw(f"Node found: {ip} [ONLINE]")
            self.msleep(400)

    def _cmd_logs(self) -> None:
        self.print_line(">>> Reading system.log...")
        for _ in range(10):
            ts     = datetime.datetime.now()
            result = random.choice(["granted", "denied"])
            self.print_raw(f"LOG: {ts} - Access {result}", COLOR_LOG)
            self.msleep(100)


# =============================================================================
# GUI
# =============================================================================
class ValhallaTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.start_time     = time.time()
        self.current_prompt = ""
        self.node_status    = "LOCAL_TTY"

        self._init_ui()
        self._init_hud_timer()
        self._init_thread()

    def _init_ui(self) -> None:
        self.setWindowTitle("VALHALLA UNIX")
        self.showFullScreen()
        self.setCursor(Qt.CursorShape.BlankCursor)

        p = self.palette()
        p.setColor(QPalette.ColorRole.Window, QColor(COLOR_BG))
        self.setPalette(p)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(TERMINAL_FONT)
        self.log_view.setStyleSheet(
            f"background-color:{COLOR_BG}; border:none; color:{COLOR_TEXT}; white-space:pre;"
        )
        self.log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.log_view)

        self.input_field = QLineEdit()
        self.input_field.setFont(TERMINAL_FONT)
        self.input_field.setStyleSheet(
            f"background-color:{COLOR_BG}; color:{COLOR_TEXT}; border:none; padding:5px 0;"
        )
        self.input_field.returnPressed.connect(self._handle_input)
        self.input_field.setEnabled(False)
        layout.addWidget(self.input_field)

        self.hud_bar = QLabel()
        self.hud_bar.setFixedHeight(30)
        self.hud_bar.setFont(HUD_FONT)
        self.hud_bar.setStyleSheet(
            f"color:{COLOR_TEXT}; border-top:1px solid {COLOR_TEXT}; background-color:{COLOR_BG};"
        )
        layout.addWidget(self.hud_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def _init_hud_timer(self) -> None:
        self.hud_timer = QTimer()
        self.hud_timer.timeout.connect(self._update_hud)
        self.hud_timer.start(1000)

    def _init_thread(self) -> None:
        self.thread = TerminalThread()
        self.thread.output.connect(self._render_output)
        self.thread.input_ready.connect(self._toggle_input)
        self.thread.hud_node.connect(lambda s: setattr(self, "node_status", s))
        self.thread.clear_screen.connect(self.log_view.clear)
        self.thread.redraw_line.connect(self._redraw_last_line)
        self.thread.start()

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _update_hud(self) -> None:
        elapsed  = int(time.time() - self.start_time)
        m, s     = divmod(elapsed, 60)
        h, m     = divmod(m, 60)
        now      = datetime.datetime.now().strftime("%H:%M:%S")
        strength = random.randint(94, 99)
        self.hud_bar.setText(
            f" [ NODE: {self.node_status} ] | [ UPTIME: {h:02}:{m:02}:{s:02} ] "
            f"| [ STR: {strength}% ] | [ {now} ]"
        )

    # ------------------------------------------------------------------
    # РЕНДЕР
    # ------------------------------------------------------------------
    def _render_output(self, text: str, color: str, animated: bool) -> None:
        if animated:
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
            self.log_view.insertHtml(f'<br><span style="color:{color};">')
            for char in text:
                cursor = self.log_view.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText(char)
                QApplication.processEvents()
                time.sleep(0.01)
        else:
            self.log_view.append(
                f'<pre style="color:{color}; margin:0; padding:0; font-family:Courier New;">'
                f'{text}</pre>'
            )
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _redraw_last_line(self, text: str, color: str) -> None:
        doc    = self.log_view.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        block = cursor.block()
        while block.isValid() and block.text().strip() == "":
            block = block.previous()

        if block.isValid():
            bc = QTextCursor(block)
            bc.select(QTextCursor.SelectionType.BlockUnderCursor)
            bc.removeSelectedText()
            bc.insertHtml(
                f'<pre style="color:{color}; margin:0; padding:0; font-family:Courier New;">'
                f'{text}</pre>'
            )
        else:
            self.log_view.append(
                f'<pre style="color:{color}; margin:0; padding:0; font-family:Courier New;">'
                f'{text}</pre>'
            )
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _toggle_input(self, enabled: bool, prompt: str) -> None:
        self.input_field.setEnabled(enabled)
        if enabled:
            self.current_prompt = prompt
            self.input_field.setText(prompt)
            self.input_field.setFocus()
            self.input_field.setCursorPosition(len(prompt))
        else:
            self.input_field.clear()

    def _handle_input(self) -> None:
        text = self.input_field.text()[len(self.current_prompt):]
        self.input_field.setEnabled(False)
        self.thread.user_input = text

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            audio.stop_ambient()
            self.close()
        elif key == Qt.Key.Key_Left:
            self.thread.arrow_key = "LEFT"
        elif key == Qt.Key.Key_Right:
            self.thread.arrow_key = "RIGHT"
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.input_field.isEnabled():
                self.thread.arrow_key = "ENTER"


# =============================================================================
# ТОЧКА ВХОДА
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ValhallaTerminal()
    window.show()
    sys.exit(app.exec())
