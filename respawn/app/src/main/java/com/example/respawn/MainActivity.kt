package com.example.respawn

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.CountDownTimer
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var lcdHeader: TextView
    private lateinit var lcdPhase: TextView
    private lateinit var oledLine1: TextView
    private lateinit var oledLine2: TextView
    private lateinit var oledLine3: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var ledStatus: View

    private val sound by lazy { SoundPlayer(this) }

    private var setupStep = 0
    private var lives = 100
    private var gameMinutes = 45
    private var waveMinutes = 5

    private var secondsLeft = 0
    private var waveSecondsLeft = 0
    private var timerActive = false

    private var countDown: CountDownTimer? = null

    private var playerHoldRunnable: Runnable? = null
    private var playerLongFired = false

    @SuppressLint("ClickableViewAccessibility")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        lcdHeader = findViewById(R.id.lcdHeader)
        lcdPhase = findViewById(R.id.lcdPhase)
        oledLine1 = findViewById(R.id.oledLine1)
        oledLine2 = findViewById(R.id.oledLine2)
        oledLine3 = findViewById(R.id.oledLine3)
        progressBar = findViewById(R.id.progressBar)
        ledStatus = findViewById(R.id.ledStatus)

        findViewById<Button>(R.id.btnUp).setOnClickListener { onUp() }
        findViewById<Button>(R.id.btnOk).setOnClickListener { onOk() }
        findViewById<Button>(R.id.btnDown).setOnClickListener { onDown() }

        val btnPlayer = findViewById<Button>(R.id.btnRespawn)
        btnPlayer.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    playerLongFired = false
                    playerHoldRunnable = Runnable {
                        playerLongFired = true
                        playerLongPress()
                    }
                    btnPlayer.postDelayed(playerHoldRunnable, 2000L)
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    playerHoldRunnable?.let { btnPlayer.removeCallbacks(it) }
                    if (!playerLongFired) playerTap()
                    true
                }
                else -> false
            }
        }

        render()
    }

    private fun onUp() {
        if (setupStep == 3) { togglePause(); return }
        when (setupStep) {
            0 -> lives = if (lives >= 990) 10 else lives + 10
            1 -> gameMinutes = if (gameMinutes >= 180) 5 else gameMinutes + 5
            2 -> waveMinutes = if (waveMinutes >= 30) 0 else waveMinutes + 1
        }
        sound.play(GameSound.CLICK)
        render()
    }

    private fun onDown() {
        if (setupStep == 3) { togglePause(); return }
        when (setupStep) {
            0 -> lives = if (lives <= 10) 990 else lives - 10
            1 -> gameMinutes = if (gameMinutes <= 5) 180 else gameMinutes - 5
            2 -> waveMinutes = if (waveMinutes <= 0) 30 else waveMinutes - 1
        }
        sound.play(GameSound.CLICK_DOWN)
        render()
    }

    private fun onOk() {
        sound.play(GameSound.OK)
        if (setupStep < 3) {
            setupStep++
            if (setupStep == 3) startGame()
        } else {
            countDown?.cancel()
            setupStep = 0
        }
        render()
    }

    private fun startGame() {
        sound.play(GameSound.START)
        secondsLeft = gameMinutes * 60
        waveSecondsLeft = waveMinutes * 60
        timerActive = true

        countDown?.cancel()
        countDown = object : CountDownTimer(Long.MAX_VALUE, 1000L) {
            override fun onTick(ms: Long) {
                if (!timerActive || secondsLeft <= 0) return

                secondsLeft--
                if (waveMinutes > 0 && waveSecondsLeft > 0) waveSecondsLeft--

                if (waveMinutes > 0 && waveSecondsLeft == 0 && secondsLeft > 0) {
                    sound.play(GameSound.WAVE_RELEASE)
                    waveSecondsLeft = waveMinutes * 60
                }

                if (secondsLeft == 0) {
                    timerActive = false
                    sound.play(GameSound.GAME_OVER)
                }

                render()
            }

            override fun onFinish() {}
        }.start()
    }

    private fun togglePause() {
        timerActive = !timerActive
        sound.play(if (timerActive) GameSound.RESUME else GameSound.PAUSE)
        render()
    }

    private fun playerTap() {
        if (lives > 0) {
            lives--
            sound.play(GameSound.DEATH)
            render()
        }
    }

    private fun playerLongPress() {
        lives++
        sound.play(GameSound.RESPAWN_CANCEL)
        render()
    }

    private fun render() {
        when (setupStep) {
            0 -> {
                lcdHeader.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                lcdPhase.text = "ЭТАП 1/3"
                oledLine1.textSize = 20f
                oledLine2.textSize = 26f
                oledLine3.textSize = 14f
                oledLine1.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                oledLine2.text = "ВСЕГО ЖИЗНЕЙ:"
                oledLine3.text = "< $lives >"
                hideProgress()
                setLed(false)
            }
            1 -> {
                lcdHeader.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                lcdPhase.text = "ЭТАП 2/3"
                oledLine1.textSize = 20f
                oledLine2.textSize = 26f
                oledLine3.textSize = 14f
                oledLine1.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                oledLine2.text = "ВРЕМЯ ИГРЫ:"
                oledLine3.text = "< $gameMinutes МИН >"
                hideProgress()
                setLed(false)
            }
            2 -> {
                lcdHeader.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                lcdPhase.text = "ЭТАП 3/3"
                oledLine1.textSize = 20f
                oledLine2.textSize = 26f
                oledLine3.textSize = 14f
                oledLine1.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                oledLine2.text = "ВРЕМЯ ВОЛНЫ:"
                oledLine3.text = if (waveMinutes == 0) "< ВОЛНА: ВЫКЛ >"
                else "< $waveMinutes МИН >"
                hideProgress()
                setLed(false)
            }
            else -> {
                lcdHeader.text = "ТОЧКА ВОЗРОЖДЕНИЯ"
                lcdPhase.text = when {
                    secondsLeft == 0 -> "OVER"
                    !timerActive -> "ПАУЗА"
                    else -> "ИГРА"
                }
                oledLine1.textSize = 20f
                oledLine2.textSize = 26f
                oledLine3.textSize = 14f

                val m = secondsLeft / 60
                val s = secondsLeft % 60
                oledLine1.text = "ВРЕМЯ: %02d:%02d".format(m, s)
                oledLine2.text = "ЖИЗНИ: $lives"
                oledLine3.text = when {
                    secondsLeft == 0 -> "ИГРА ОКОНЧЕНА!"
                    !timerActive -> "- ПАУЗА -"
                    waveMinutes > 0 -> {
                        val wm = waveSecondsLeft / 60
                        val ws = waveSecondsLeft % 60
                        "ВОЛНА: %02d:%02d".format(wm, ws)
                    }
                    else -> ""
                }

                if (waveMinutes > 0 && timerActive && secondsLeft > 0) {
                    showWaveProgress()
                } else {
                    hideProgress()
                }
                setLed(timerActive && secondsLeft > 0)
            }
        }
    }

    private fun showWaveProgress() {
        val maxWave = waveMinutes * 60
        if (maxWave <= 0) { hideProgress(); return }
        val percent = ((waveSecondsLeft.toFloat() / maxWave) * 100).toInt()
        progressBar.visibility = View.VISIBLE
        progressBar.progress = percent
        progressBar.progressTintList = android.content.res.ColorStateList.valueOf(
            android.graphics.Color.parseColor("#2ECC71")
        )
    }

    private fun hideProgress() {
        progressBar.visibility = View.INVISIBLE
        progressBar.progress = 0
    }

    private fun setLed(on: Boolean) {
        val onDrawable = ContextCompat.getDrawable(this, R.drawable.led_on)
        val offDrawable = ContextCompat.getDrawable(this, R.drawable.led_off)
        ledStatus.background = if (on) onDrawable else offDrawable
    }

    override fun onDestroy() {
        countDown?.cancel()
        sound.release()
        super.onDestroy()
    }
}