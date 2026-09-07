package com.example.valhallaterminal

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Html
import android.view.KeyEvent
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.sin

class MainActivity : AppCompatActivity() {

    private lateinit var logText: TextView
    private lateinit var inputField: EditText
    private lateinit var hudBar: TextView
    private lateinit var scrollView: ScrollView
    private lateinit var btnEnter: Button
    private lateinit var statusIndicator: View

    private val terminalThread = TerminalThread(this)
    private val mainHandler = Handler(Looper.getMainLooper())
    private val logBuilder = StringBuilder()

    private var currentPrompt = ""
    private var lastBlockStart = 0

    private val beepGenerator = BeepGenerator()

    private val minigameLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val data = result.data
            val gameResult = data?.getStringExtra("result")
            terminalThread.onMinigameResult(gameResult == "SUCCESS")
        } else {
            terminalThread.onMinigameResult(false)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        logText = findViewById(R.id.log_text)
        inputField = findViewById(R.id.input_field)
        hudBar = findViewById(R.id.hud_bar)
        scrollView = findViewById(R.id.scroll_view)
        btnEnter = findViewById(R.id.btn_enter)
        statusIndicator = findViewById(R.id.status_indicator)

        inputField.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
                imm.hideSoftInputFromWindow(inputField.windowToken, 0)
            }
        }

        setupKeyboard()

        inputField.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                submitInput()
                true
            } else false
        }

        terminalThread.start()
    }

    fun appendLog(text: String, color: String = "#00FF41", updateLast: Boolean = true) {
        mainHandler.post {
            if (updateLast) {
                lastBlockStart = logBuilder.length
            }
            logBuilder.append("<font color='$color'>")
                .append(android.text.TextUtils.htmlEncode(text))
                .append("</font><br>")
            logText.setText(Html.fromHtml(logBuilder.toString(), Html.FROM_HTML_MODE_LEGACY))
            scrollView.post { scrollView.fullScroll(View.FOCUS_DOWN) }
        }
    }

    fun replaceLastLine(text: String, color: String = "#00FF41") {
        mainHandler.post {
            logBuilder.setLength(lastBlockStart)
            logBuilder.append("<pre><font color='$color'>")
                .append(android.text.TextUtils.htmlEncode(text))
                .append("</font></pre>")
            logText.setText(Html.fromHtml(logBuilder.toString(), Html.FROM_HTML_MODE_LEGACY))
            scrollView.post { scrollView.fullScroll(View.FOCUS_DOWN) }
        }
    }

    fun clearLog() {
        mainHandler.post {
            logBuilder.clear()
            logText.text = ""
            lastBlockStart = 0
        }
    }

    fun updateHudNode(node: String) {
        mainHandler.post {
            val uptime = terminalThread.getUptimeString()
            val currentTime = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
                .format(java.util.Date())
            val strength = (94..99).random()
            hudBar.text = "[ NODE: $node ] | [ UPTIME: $uptime ] | [ STR: $strength% ] | [ $currentTime ]"
        }
    }

    fun enableInput(enabled: Boolean, prompt: String = "") {
        mainHandler.post {
            currentPrompt = prompt
            inputField.isEnabled = enabled
            if (enabled) {
                inputField.setText(prompt)
                inputField.requestFocus()
                inputField.setSelection(prompt.length)
                val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
                imm.hideSoftInputFromWindow(inputField.windowToken, 0)
            } else {
                inputField.text.clear()
                currentPrompt = ""
            }
        }
    }

    fun beep(freq: Double, durationMs: Int, volume: Double = 0.7) {
        beepGenerator.beep(freq, durationMs, volume)
    }

    private fun setupKeyboard() {
        val digitButtons = listOf(
            R.id.btn_1, R.id.btn_2, R.id.btn_3,
            R.id.btn_4, R.id.btn_5, R.id.btn_6,
            R.id.btn_7, R.id.btn_8, R.id.btn_9,
            R.id.btn_0
        )
        digitButtons.forEach { id ->
            findViewById<Button>(id).setOnClickListener { btn ->
                if (inputField.isEnabled) {
                    inputField.append((btn as Button).text.toString())
                }
            }
        }

        findViewById<Button>(R.id.btn_left).setOnClickListener {
            terminalThread.arrowKey = "LEFT"
        }
        findViewById<Button>(R.id.btn_right).setOnClickListener {
            terminalThread.arrowKey = "RIGHT"
        }
        btnEnter.setOnClickListener {
            if (inputField.isEnabled) {
                submitInput()
            } else {
                terminalThread.arrowKey = "ENTER"
            }
        }
    }

    private fun submitInput() {
        if (inputField.isEnabled) {
            var text = inputField.text.toString()
            if (currentPrompt.isNotEmpty() && text.startsWith(currentPrompt)) {
                text = text.substring(currentPrompt.length)
            }
            inputField.isEnabled = false
            inputField.text.clear()
            terminalThread.userInput = text.trim()
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                terminalThread.arrowKey = "LEFT"
                return true
            }
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                terminalThread.arrowKey = "RIGHT"
                return true
            }
            KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_DPAD_CENTER -> {
                if (!inputField.isEnabled) {
                    terminalThread.arrowKey = "ENTER"
                    return true
                }
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    fun launchMinigame(rounds: Int, zone: Int, maxErrors: Int, speed: Double, title: String = "ПЕРЕХВАТ СИГНАЛА", subtitle: String = "") {
        val intent = android.content.Intent(this, MinigameActivity::class.java).apply {
            putExtra("rounds", rounds)
            putExtra("zone", zone)
            putExtra("maxErrors", maxErrors)
            putExtra("speed", speed)
            putExtra("title", title)
            putExtra("subtitle", subtitle)
        }
        minigameLauncher.launch(intent)
    }
}

class BeepGenerator {
    private val sampleRate = 44100

    fun beep(freq: Double, durationMs: Int, volume: Double = 0.7) {
        val numSamples = (durationMs * sampleRate / 1000).toInt()
        val samples = ShortArray(numSamples)
        for (i in 0 until numSamples) {
            val t = i / sampleRate.toDouble()
            samples[i] = (sin(2 * Math.PI * freq * t) * volume * Short.MAX_VALUE).toInt().toShort()
        }
        val audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(samples.size * 2)
            .setTransferMode(AudioTrack.MODE_STATIC)
            .build()
        audioTrack.write(samples, 0, samples.size)
        audioTrack.play()
    }
}