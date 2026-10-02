package com.example.bombdefuse

import android.content.SharedPreferences
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var lcdHeader: TextView
    private lateinit var lcdPhase: TextView
    private lateinit var lcdLine1: TextView
    private lateinit var lcdLine2: TextView
    private lateinit var lcdLine3: TextView
    private lateinit var lcdLine4: TextView
    private lateinit var ledStatus: View
    private lateinit var progressBar: ProgressBar
    private lateinit var btnArm: Button

    private val sound by lazy { SoundPlayer(this) }
    private lateinit var prefs: SharedPreferences

    private val ADMIN_CODE = "0000"

    private var isArmed = false
    private var inputBuffer = ""
    private var currentTimer = 45
    private var countdownSeconds = 45
    private var unlockCode = "7777"
    private var defuseCode = "7777"

    private enum class Screen { LOCKED, ARMED, DEFUSED, BOOM, MENU, INPUT }
    private var screen = Screen.LOCKED

    private enum class InputKind { NONE, UNLOCK, DEFUSE, TIMER }
    private var inputKind = InputKind.NONE
    private var inputValue = ""

    private val handler = Handler(Looper.getMainLooper())
    private var lastTick = 0L

    private val tickRunnable = object : Runnable {
        override fun run() {
            if (!isArmed) return
            val now = System.currentTimeMillis()
            if (now - lastTick >= 1000L) {
                lastTick = now
                currentTimer--
                if (currentTimer <= 0) {
                    currentTimer = 0
                    isArmed = false
                    screen = Screen.BOOM
                    sound.play(GameSound.BOOM)
                    render()
                    return
                }
                sound.play(GameSound.TICK)
                render()
            }
            handler.postDelayed(this, 200L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences("БОМБА", MODE_PRIVATE)
        unlockCode = prefs.getString("РАЗБЛОКИРОВКА", "7777") ?: "7777"
        defuseCode = prefs.getString("РАЗМИНИРОВАНИЕ", "7777") ?: "7777"
        countdownSeconds = prefs.getInt("ВРЕМЯ ДО ВЗРЫВА", 45)
        currentTimer = countdownSeconds

        lcdHeader = findViewById(R.id.lcdHeader)
        lcdPhase = findViewById(R.id.lcdPhase)
        lcdLine1 = findViewById(R.id.lcdLine1)
        lcdLine2 = findViewById(R.id.lcdLine2)
        lcdLine3 = findViewById(R.id.lcdLine3)
        lcdLine4 = findViewById(R.id.lcdLine4)
        ledStatus = findViewById(R.id.ledStatus)
        progressBar = findViewById(R.id.progressBar)
        btnArm = findViewById(R.id.btnArm)

        val digits = mapOf(
            R.id.btn0 to '0', R.id.btn1 to '1', R.id.btn2 to '2',
            R.id.btn3 to '3', R.id.btn4 to '4', R.id.btn5 to '5',
            R.id.btn6 to '6', R.id.btn7 to '7', R.id.btn8 to '8',
            R.id.btn9 to '9', R.id.btnStar to '*', R.id.btnHash to '#'
        )
        for ((id, ch) in digits) {
            findViewById<Button>(id).setOnClickListener { onKey(ch) }
        }
        findViewById<Button>(R.id.btnBack).setOnClickListener { onKey('C') }
        findViewById<Button>(R.id.btnMenu).setOnClickListener { onKey('B') }
        btnArm.setOnClickListener { onKey('A') }

        render()
    }

    private fun onKey(key: Char) {
        when (screen) {
            Screen.LOCKED -> handleLocked(key)
            Screen.ARMED -> handleArmed(key)
            Screen.MENU -> handleMenu(key)
            Screen.INPUT -> handleInput(key)
            Screen.DEFUSED, Screen.BOOM -> {
                if (key == 'A' || key == '#') resetToLocked()
            }
        }
    }

    private fun handleLocked(key: Char) {
        when {
            key.isDigit() && inputBuffer.length < 4 -> {
                sound.play(GameSound.CLICK)
                inputBuffer += key
                render()
            }
            key == 'C' && inputBuffer.isNotEmpty() -> {
                sound.play(GameSound.CLICK)
                inputBuffer = inputBuffer.dropLast(1)
                render()
            }
            key == 'A' -> {
                if (inputBuffer == unlockCode) {
                    isArmed = true
                    inputBuffer = ""
                    currentTimer = countdownSeconds
                    lastTick = System.currentTimeMillis()
                    screen = Screen.ARMED
                    sound.play(GameSound.ARM)
                    handler.removeCallbacks(tickRunnable)
                    handler.post(tickRunnable)
                    render()
                } else {
                    wrongCode()
                }
            }
            key == 'B' -> {
                if (inputBuffer == ADMIN_CODE) {
                    inputBuffer = ""
                    screen = Screen.MENU
                    sound.play(GameSound.UNLOCK)
                    render()
                } else {
                    wrongCode()
                }
            }
        }
    }

    private fun handleArmed(key: Char) {
        when {
            key.isDigit() && inputBuffer.length < 4 -> {
                sound.play(GameSound.CLICK)
                inputBuffer += key
                render()
            }
            key == 'C' && inputBuffer.isNotEmpty() -> {
                sound.play(GameSound.CLICK)
                inputBuffer = inputBuffer.dropLast(1)
                render()
            }
            key == 'A' -> {
                if (inputBuffer == defuseCode) {
                    isArmed = false
                    inputBuffer = ""
                    screen = Screen.DEFUSED
                    sound.play(GameSound.DEFUSED)
                    handler.removeCallbacks(tickRunnable)
                    render()
                } else {
                    wrongCode()
                }
            }
        }
    }

    private fun handleMenu(key: Char) {
        when (key) {
            '1' -> enterInput(InputKind.UNLOCK, unlockCode)
            '2' -> enterInput(InputKind.DEFUSE, defuseCode)
            '3' -> enterInput(InputKind.TIMER, countdownSeconds.toString())
            '#' -> {
                screen = Screen.LOCKED
                inputBuffer = ""
                render()
            }
        }
    }

    private fun enterInput(kind: InputKind, defaultVal: String) {
        inputKind = kind
        inputValue = defaultVal
        screen = Screen.INPUT
        render()
    }

    private fun handleInput(key: Char) {
        val maxLen = if (inputKind == InputKind.TIMER) 3 else 4

        when {
            key.isDigit() && inputValue.length < maxLen -> {
                sound.play(GameSound.CLICK)
                if (inputValue == "0" && inputKind == InputKind.TIMER) inputValue = ""
                inputValue += key
                render()
            }
            key == 'C' && inputValue.isNotEmpty() -> {
                sound.play(GameSound.CLICK)
                inputValue = inputValue.dropLast(1)
                render()
            }
            key == '*' -> {
                sound.play(GameSound.CLICK)
                screen = Screen.MENU
                render()
            }
            key == '#' -> confirmInput()
        }
    }

    private fun confirmInput() {
        when (inputKind) {
            InputKind.UNLOCK -> {
                if (inputValue.length == 4) {
                    unlockCode = inputValue
                    prefs.edit().putString("РАЗБЛОКИРОВКА", unlockCode).apply()
                    sound.play(GameSound.DEFUSED)
                    screen = Screen.MENU
                    render()
                } else {
                    sound.play(GameSound.ERROR)
                }
            }
            InputKind.DEFUSE -> {
                if (inputValue.length == 4) {
                    defuseCode = inputValue
                    prefs.edit().putString("РАЗМИНИРОВАНИЕ", defuseCode).apply()
                    sound.play(GameSound.DEFUSED)
                    screen = Screen.MENU
                    render()
                } else {
                    sound.play(GameSound.ERROR)
                }
            }
            InputKind.TIMER -> {
                val v = inputValue.toIntOrNull() ?: 0
                if (v > 0) {
                    countdownSeconds = v
                    prefs.edit().putInt("ВРЕМЯ ДО ВЗРЫВА", countdownSeconds).apply()
                    sound.play(GameSound.DEFUSED)
                    screen = Screen.MENU
                    render()
                } else {
                    sound.play(GameSound.ERROR)
                }
            }
            else -> {}
        }
    }

    private fun wrongCode() {
        sound.play(GameSound.ERROR)
        inputBuffer = ""
        val currentScreen = screen
        lcdLine2.text = "НЕПРАВИЛЬНЫЙ КОД!"
        handler.postDelayed({
            if (screen == currentScreen) render()
        }, 1000L)
    }

    private fun resetToLocked() {
        isArmed = false
        inputBuffer = ""
        currentTimer = countdownSeconds
        screen = Screen.LOCKED
        handler.removeCallbacks(tickRunnable)
        render()
    }

    private fun render() {
        when (screen) {
            Screen.LOCKED -> renderLocked()
            Screen.ARMED -> renderArmed()
            Screen.DEFUSED -> renderDefused()
            Screen.BOOM -> renderBoom()
            Screen.MENU -> renderMenu()
            Screen.INPUT -> renderInput()
        }
        updateLed()
        updateArmButton()
    }

    private fun renderLocked() {
        lcdHeader.text = "БОМБА"
        lcdPhase.text = "ЗАБЛОКИРОВАНО"
        lcdPhase.setTextColor(0xFFFF6B35.toInt())
        lcdLine1.text = "ОКНО ВВОДА ПАРОЛЯ"
        lcdLine2.text = "ВВЕДИТЕ ПАРОЛЬ: " + stars(inputBuffer)
        lcdLine3.text = ""
        lcdLine4.text = ""
        progressBar.visibility = View.INVISIBLE
    }

    private fun renderArmed() {
        lcdHeader.text = "БОМБА"
        lcdPhase.text = "УСТАНОВЛЕНА"
        lcdPhase.setTextColor(0xFFFF3B30.toInt())
        lcdLine1.text = "БОМБА УСТАНОВЛЕНА!"
        lcdLine2.text = "ВРЕМЯ ДО ВЗРЫВА: ${currentTimer}s"
        lcdLine3.text = "ВВЕДИТЕ КОД: " + stars(inputBuffer)
        lcdLine4.text = ""
        showTimerProgress()
    }

    private fun renderDefused() {
        lcdHeader.text = "БОМБА"
        lcdPhase.text = "РАЗМИНИРОВАНА"
        lcdPhase.setTextColor(0xFF2ECC71.toInt())
        lcdLine1.text = "БОМБА РАЗМИНИРОВАНА!"
        lcdLine2.text = ""
        lcdLine3.text = "МИССИЯ ВЫПОЛНЕНА!"
        lcdLine4.text = "ВЗВОД ДЛЯ СБРОСА"
        progressBar.visibility = View.INVISIBLE
    }

    private fun renderBoom() {
        lcdHeader.text = "БОМБА"
        lcdPhase.text = "ВЗРЫВ"
        lcdPhase.setTextColor(0xFFFF3B30.toInt())
        lcdLine1.text = "*** ВЗРЫВ! ***"
        lcdLine2.text = ""
        lcdLine3.text = "МИССИЯ ПРОВАЛЕНА!"
        lcdLine4.text = "ВЗВОД ДЛЯ СБРОСА"
        progressBar.visibility = View.INVISIBLE
    }

    private fun renderMenu() {
        lcdHeader.text = "БОМБА"
        lcdPhase.text = "МЕНЮ"
        lcdPhase.setTextColor(0xFF2ECC71.toInt())
        lcdLine1.text = "ИНЖЕНЕРНОЕ МЕНЮ"
        lcdLine2.text = "1: КОД РАЗБЛОКИРОВКИ"
        lcdLine3.text = "2: КОД РАЗМИНИРОВАНИЯ"
        lcdLine4.text = "3: ВРЕМЯ   # = ВЫХОД"
        progressBar.visibility = View.INVISIBLE
    }

    private fun renderInput() {
        lcdHeader.text = ""
        lcdPhase.text = "ВВОД"
        lcdPhase.setTextColor(0xFF2ECC71.toInt())
        val title = when (inputKind) {
            InputKind.UNLOCK -> "ВВЕДИТЕ КОД РАЗБЛОКИРОВКИ"
            InputKind.DEFUSE -> "ВВЕДИТЕ КОД РАЗМИНИРОВАНИЯ"
            InputKind.TIMER -> "УКАЖИТЕ ВРЕМЯ (СЕК)"
            else -> "ВВОД"
        }
        lcdLine1.text = title
        lcdLine2.text = "> $inputValue"
        lcdLine3.text = ""
        lcdLine4.text = "# = OK    * = ОТМЕНА"
        progressBar.visibility = View.INVISIBLE
    }

    private fun stars(s: String): String = "*".repeat(s.length)

    private fun showTimerProgress() {
        if (countdownSeconds <= 0) return
        val percent = ((currentTimer.toFloat() / countdownSeconds) * 100).toInt().coerceIn(0, 100)
        progressBar.visibility = View.VISIBLE
        progressBar.progress = percent
        val color = when {
            percent < 25 -> "#FF3B30"
            percent < 50 -> "#FFB800"
            else -> "#2ECC71"
        }
        progressBar.progressTintList = android.content.res.ColorStateList.valueOf(
            android.graphics.Color.parseColor(color)
        )
    }

    private fun updateLed() {
        val onDrawable = ContextCompat.getDrawable(this, R.drawable.led_red)
        val offDrawable = ContextCompat.getDrawable(this, R.drawable.led_off)
        ledStatus.background = if (isArmed) onDrawable else offDrawable
    }

    private fun updateArmButton() {
        if (screen == Screen.ARMED) {
            btnArm.text = "РАЗМИНИРОВАТЬ"
            btnArm.setTextColor(0xFF2ECC71.toInt())
            btnArm.setBackgroundResource(R.drawable.btn_defuse)
        } else {
            btnArm.text = "ВЗВОД"
            btnArm.setTextColor(0xFFFF3B30.toInt())
            btnArm.setBackgroundResource(R.drawable.btn_arm)
        }
    }

    override fun onDestroy() {
        handler.removeCallbacks(tickRunnable)
        sound.release()
        super.onDestroy()
    }
}