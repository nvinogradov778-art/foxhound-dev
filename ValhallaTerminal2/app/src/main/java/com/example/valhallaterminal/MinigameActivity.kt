package com.example.valhallaterminal

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import kotlin.random.Random

class MinigameActivity : AppCompatActivity() {

    private lateinit var scaleView: SignalScaleView
    private lateinit var roundText: TextView
    private lateinit var errorsText: TextView
    private lateinit var enterBtn: Button
    private lateinit var actionBtn: Button
    private lateinit var titleView: TextView
    private lateinit var subtitleView: TextView

    private var sigRounds = 3
    private var sigZone = 5
    private var sigMaxErrors = 2
    private var sigSpeed = 0.09

    private var markerPos = 0
    private var markerDir = 1
    private var cursorPos = 0
    private var errors = 0
    private var hits = 0
    private var gameRunning = false
    private var gameFinished = false

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var tickRunnable: Runnable

    private val beepGenerator = BeepGenerator()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_minigame)

        sigRounds = intent.getIntExtra("rounds", 3)
        sigZone = intent.getIntExtra("zone", 5)
        sigMaxErrors = intent.getIntExtra("maxErrors", 2)
        sigSpeed = intent.getDoubleExtra("speed", 0.09)

        val title = intent.getStringExtra("title") ?: "ПЕРЕХВАТ СИГНАЛА"
        val subtitle = intent.getStringExtra("subtitle") ?: ""

        scaleView = findViewById(R.id.signal_scale)
        roundText = findViewById(R.id.round_text)
        errorsText = findViewById(R.id.errors_text)
        enterBtn = findViewById(R.id.game_enter_btn)
        actionBtn = findViewById(R.id.game_action_btn)
        titleView = findViewById(R.id.game_title)
        subtitleView = findViewById(R.id.game_subtitle)

        titleView.text = title
        if (title.contains("ВНИМАНИЕ", ignoreCase = true)) {
            titleView.setTextColor(android.graphics.Color.parseColor("#FF0000"))
            titleView.textSize = 18f
        } else {
            titleView.setTextColor(android.graphics.Color.parseColor("#00FF41"))
            titleView.textSize = 24f
        }

        if (subtitle.isNotEmpty()) {
            subtitleView.text = subtitle
            subtitleView.visibility = View.VISIBLE
        }

        cursorPos = (38 - sigZone) / 2

        enterBtn.setOnClickListener {
            if (gameRunning && !gameFinished) {
                onEnterPressed()
            }
        }

        actionBtn.setOnClickListener {
            if (!gameRunning && !gameFinished) {
                startGame()
            }
        }

        showStartScreen()
    }

    private fun showStartScreen() {
        gameRunning = false
        gameFinished = false
        roundText.text = "РАУНД: 0/$sigRounds"
        errorsText.text = "ОШИБКИ: 0/$sigMaxErrors"
        enterBtn.visibility = View.GONE
        actionBtn.visibility = View.VISIBLE
        actionBtn.text = "НАЧАТЬ"
        scaleView.update(0, cursorPos, sigZone, 38)
        beepGenerator.beep(1800.0, 100)
    }

    private fun startGame() {
        gameRunning = true
        gameFinished = false
        markerPos = 0
        markerDir = 1
        errors = 0
        hits = 0
        updateInfo()
        titleView.text = "ЗАХВАТИТЕ СИГНАЛ"
        titleView.setTextColor(android.graphics.Color.parseColor("#00FF41"))
        titleView.textSize = 24f
        enterBtn.visibility = View.VISIBLE
        actionBtn.visibility = View.GONE
        beepGenerator.beep(1200.0, 80)

        tickRunnable = object : Runnable {
            override fun run() {
                if (gameRunning && !gameFinished) {
                    moveMarker()
                    handler.postDelayed(this, (sigSpeed * 1000).toLong())
                }
            }
        }
        handler.post(tickRunnable)
    }

    private fun moveMarker() {
        markerPos += markerDir
        if (markerPos >= 38 - 1) markerDir = -1
        else if (markerPos <= 0) markerDir = 1
        scaleView.update(markerPos, cursorPos, sigZone, 38)
    }

    private fun onEnterPressed() {
        if (gameFinished || !gameRunning) return

        val captured = cursorPos <= markerPos && markerPos < cursorPos + sigZone
        if (captured) {
            beepGenerator.beep(1400.0, 60)
            hits++
            if (hits >= sigRounds) {
                gameFinished = true
                gameRunning = false
                titleView.text = "УСПЕХ!"
                titleView.setTextColor(android.graphics.Color.parseColor("#00FF41"))
                titleView.textSize = 24f
                enterBtn.visibility = View.GONE
                actionBtn.visibility = View.GONE
                beepGenerator.beep(2000.0, 300)
                beepGenerator.beep(2500.0, 300)
                updateInfo()
                handler.postDelayed({
                    setResult(RESULT_OK, intent.apply { putExtra("result", "SUCCESS") })
                    finish()
                }, 1500)
                return
            }
            sigSpeed = maxOf(0.03, sigSpeed * 0.75)
            markerPos = Random.nextInt(0, 38)
            scaleView.update(markerPos, cursorPos, sigZone, 38)
            updateInfo()
        } else {
            beepGenerator.beep(250.0, 200)
            errors++
            if (errors > sigMaxErrors) {
                gameFinished = true
                gameRunning = false
                titleView.text = "ПРОВАЛ"
                titleView.setTextColor(android.graphics.Color.parseColor("#FF0000"))
                titleView.textSize = 24f
                enterBtn.visibility = View.GONE
                actionBtn.visibility = View.GONE
                beepGenerator.beep(300.0, 500)
                updateInfo()
                handler.postDelayed({
                    setResult(RESULT_OK, intent.apply { putExtra("result", "FAIL") })
                    finish()
                }, 1500)
                return
            }
            updateInfo()
            markerPos = Random.nextInt(0, 38)
            scaleView.update(markerPos, cursorPos, sigZone, 38)
        }
    }

    private fun updateInfo() {
        roundText.text = "РАУНД: $hits/$sigRounds"
        errorsText.text = "ОШИБКИ: $errors/$sigMaxErrors"
    }

    override fun onDestroy() {
        handler.removeCallbacks(tickRunnable)
        super.onDestroy()
    }
}