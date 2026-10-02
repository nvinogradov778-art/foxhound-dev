package com.example.domination

import android.annotation.SuppressLint
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    companion object {
        const val NEUTRAL = 0
        const val TEAM_1 = 1
        const val TEAM_2 = 2
        const val TICK_MS = 20L
    }

    private var owner = NEUTRAL
    private var score1 = 0
    private var score2 = 0
    private var captureTime = 4.0f
    private var scoreInterval = 1.0f
    private var gameTime = 10.0f

    private var inMenu = false
    private var menuIndex = 0
    private var editing = false

    private var capturingTeam = NEUTRAL
    private var captureStartTime = 0L
    private var lastScoreTime = 0L
    private var gameStartTime = 0L
    private var gameOver = false

    private var isBeeping = false
    private var menuExitTime = 0L

    private var t1Pressed = false
    private var t2Pressed = false
    private var upPressed = false
    private var downPressed = false
    private var selPressed = false
    private var exitPressed = false

    private var prevUp = false
    private var prevDown = false
    private var prevSel = false
    private var prevExit = false

    private lateinit var lcdHeader: TextView
    private lateinit var lcd1: TextView
    private lateinit var lcd2: TextView
    private lateinit var lcd3: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var led1: View
    private lateinit var led2: View

    private lateinit var btnT1: Button
    private lateinit var btnT2: Button
    private lateinit var btnUp: Button
    private lateinit var btnDown: Button
    private lateinit var btnSel: Button
    private lateinit var btnExit: Button

    private lateinit var tone: ToneGenerator
    private val handler = Handler(Looper.getMainLooper())

    private val loopRunnable = object : Runnable {
        override fun run() {
            try { tick() } catch (e: Exception) { e.printStackTrace() }
            handler.postDelayed(this, TICK_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        lcdHeader = findViewById(R.id.lcdHeader)
        lcd1 = findViewById(R.id.lcdLine1)
        lcd2 = findViewById(R.id.lcdLine2)
        lcd3 = findViewById(R.id.lcdLine3)
        progressBar = findViewById(R.id.progressBar)
        led1 = findViewById(R.id.ledTeam1)
        led2 = findViewById(R.id.ledTeam2)

        btnT1 = findViewById(R.id.btnTeam1)
        btnT2 = findViewById(R.id.btnTeam2)
        btnUp = findViewById(R.id.btnUp)
        btnDown = findViewById(R.id.btnDown)
        btnSel = findViewById(R.id.btnSel)
        btnExit = findViewById(R.id.btnSettings)

        setupHoldButton(btnT1) { t1Pressed = it }
        setupHoldButton(btnT2) { t2Pressed = it }
        setupHoldButton(btnUp) { upPressed = it }
        setupHoldButton(btnDown) { downPressed = it }
        setupHoldButton(btnSel) { selPressed = it }
        setupHoldButton(btnExit) { exitPressed = it }

        tone = ToneGenerator(AudioManager.STREAM_MUSIC, 100)

        updateDisplay()
        lastScoreTime = System.currentTimeMillis()
        gameStartTime = lastScoreTime
        handler.post(loopRunnable)
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun setupHoldButton(btn: Button, setter: (Boolean) -> Unit) {
        btn.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> setter(true)
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> setter(false)
            }
            true
        }
    }

    private fun tick() {
        val now = System.currentTimeMillis()

        val upEdge = upPressed && !prevUp
        val downEdge = downPressed && !prevDown
        val selEdge = selPressed && !prevSel
        val exitEdge = exitPressed && !prevExit
        prevUp = upPressed
        prevDown = downPressed
        prevSel = selPressed
        prevExit = exitPressed

        if (gameOver) {
            if (exitEdge) resetAfterGameOver()
            return
        }

        val elapsedMin = (now - gameStartTime) / 60000f
        if (elapsedMin >= gameTime) {
            gameOver = true
            showGameOver()
            return
        }

        if (exitEdge && !inMenu && (now - menuExitTime) > 1000) {
            stopTone()
            isBeeping = false
            capturingTeam = NEUTRAL
            hideProgress()
            showMenu()
            lastScoreTime = System.currentTimeMillis()
            return
        }

        if (inMenu) {
            handleMenuInput(upEdge, downEdge, selEdge, exitEdge)
            return
        }

        val currentPress = when {
            t1Pressed && !t2Pressed && owner != TEAM_1 -> TEAM_1
            t2Pressed && !t1Pressed && owner != TEAM_2 -> TEAM_2
            else -> NEUTRAL
        }

        if (currentPress != NEUTRAL) {
            if (capturingTeam != currentPress) {
                capturingTeam = currentPress
                captureStartTime = now
            }

            val elapsedMs = now - captureStartTime
            showProgress(elapsedMs, currentPress)

            val beepState = (elapsedMs / 200) % 2 == 0L
            if (beepState != isBeeping) {
                if (beepState) startBeepTone() else stopTone()
                isBeeping = beepState
            }

            if (elapsedMs >= (captureTime * 1000).toLong()) {
                owner = currentPress
                capturingTeam = NEUTRAL
                lastScoreTime = now
                stopTone()
                playAck()
                isBeeping = false
                hideProgress()
                renderOwnerLine()
                updateLeds()
            }
        } else {
            if (capturingTeam != NEUTRAL) {
                capturingTeam = NEUTRAL
                stopTone()
                isBeeping = false
                hideProgress()
                renderOwnerLine()
            }
        }

        if (owner != NEUTRAL && (now - lastScoreTime) >= (scoreInterval * 1000).toLong()) {
            if (owner == TEAM_1) score1++ else score2++
            lastScoreTime = now
            renderScores()
        }
    }

    private fun showProgress(elapsedMs: Long, team: Int) {
        val captureMs = (captureTime * 1000).toLong()
        val percent = minOf((elapsedMs * 100 / captureMs).toInt(), 100)
        progressBar.visibility = View.VISIBLE
        progressBar.progress = percent

        val tint = if (team == TEAM_1) "#FFB800" else "#00B4FF"
        progressBar.progressTintList = android.content.res.ColorStateList.valueOf(
            android.graphics.Color.parseColor(tint)
        )
    }

    private fun hideProgress() {
        progressBar.visibility = View.INVISIBLE
        progressBar.progress = 0
    }

    private fun showMenu() {
        inMenu = true
        editing = false
        renderMenu()
    }

    private fun handleMenuInput(upEdge: Boolean, downEdge: Boolean, selEdge: Boolean, exitEdge: Boolean) {
        if (upEdge) {
            if (!editing) menuIndex = maxOf(0, menuIndex - 1)
            else when (menuIndex) {
                0 -> captureTime = minOf(10f, captureTime + 0.5f)
                1 -> scoreInterval = minOf(5f, scoreInterval + 0.5f)
                else -> gameTime = minOf(60f, gameTime + 1f)
            }
            renderMenu()
        } else if (downEdge) {
            if (!editing) menuIndex = minOf(2, menuIndex + 1)
            else when (menuIndex) {
                0 -> captureTime = maxOf(0.5f, captureTime - 0.5f)
                1 -> scoreInterval = maxOf(0.5f, scoreInterval - 0.5f)
                else -> gameTime = maxOf(1f, gameTime - 1f)
            }
            renderMenu()
        } else if (selEdge) {
            editing = !editing
            renderMenu()
        } else if (exitEdge) {
            inMenu = false
            editing = false
            menuExitTime = System.currentTimeMillis()
            updateDisplay()
        }
    }

    private fun renderMenu() {
        lcdHeader.text = "НАСТРОЙКИ"
        lcd1.textSize = 18f
        lcd2.textSize = 18f
        lcd3.textSize = 18f
        lcd1.text = menuLine(0, "СКОРОСТЬ ЗАХВАТА", String.format("%.1fс", captureTime))
        lcd2.text = menuLine(1, "ВРЕМЯ НАЧИСЛЕНИЯ 1 У.Е. ОЧКА ЗАХВАТА",   String.format("%.1fс", scoreInterval))
        lcd3.text = menuLine(2, "ВРЕМЯ ИГРЫ",   "${gameTime.toInt()}м")
        hideProgress()
    }

    private fun menuLine(index: Int, label: String, value: String): String {
        val prefix = if (!editing) {
            if (menuIndex == index) ">" else " "
        } else {
            if (menuIndex == index) "*" else " "
        }
        return "$prefix $label: $value"
    }

    private fun showGameOver() {
        lcdHeader.text = "ИГРА ОКОНЧЕНА"
        lcd1.text = "АЛЬФА: ${score1.toString().padStart(4, '0')}"
        lcd2.text = "БРАВО: ${score2.toString().padStart(4, '0')}"
        lcd3.text = when {
            score1 > score2 -> "ПОБЕДА: АЛЬФА!"
            score2 > score1 -> "ПОБЕДА: БРАВО!"
            else -> "НИЧЬЯ!"
        }
        hideProgress()
        setLed(led1, false)
        setLed(led2, false)
    }

    private fun resetAfterGameOver() {
        score1 = 0
        score2 = 0
        owner = NEUTRAL
        gameOver = false
        gameStartTime = System.currentTimeMillis()
        lastScoreTime = gameStartTime
        updateDisplay()
    }

    private fun updateDisplay() {
        lcdHeader.text = "ТОЧКА ИНТЕРЕСА"
        renderOwnerLine()
        renderScores()
        lcd3.text = ""
        hideProgress()
        updateLeds()
    }

    private fun renderOwnerLine() {
        lcd1.text = when (owner) {
            TEAM_1 -> "СТАТУС: под контролем АЛЬФА"
            TEAM_2 -> "СТАТУС: пот контролем БРАВО"
            else -> "СТАТУС: НЕЙТРАЛЬНА"
        }
    }

    private fun renderScores() {
        lcd2.text = "$score1 : $score2"
    }

    private fun updateLeds() {
        val alpha = ContextCompat.getDrawable(this, R.drawable.led_alpha)
        val bravo = ContextCompat.getDrawable(this, R.drawable.led_bravo)
        val off = ContextCompat.getDrawable(this, R.drawable.led_off)
        led1.background = if (owner == TEAM_1) alpha else off
        led2.background = if (owner == TEAM_2) bravo else off
    }

    private fun setLed(view: View, on: Boolean) {
        if (!on) view.background = ContextCompat.getDrawable(this, R.drawable.led_off)
    }

    private fun startBeepTone() {
        try { tone.startTone(ToneGenerator.TONE_PROP_BEEP) } catch (_: Exception) {}
    }

    private fun playAck() {
        try { tone.startTone(ToneGenerator.TONE_PROP_ACK, 500) } catch (_: Exception) {}
    }

    private fun stopTone() {
        try { tone.stopTone() } catch (_: Exception) {}
    }

    override fun onDestroy() {
        handler.removeCallbacks(loopRunnable)
        try { tone.release() } catch (_: Exception) {}
        super.onDestroy()
    }
}