package com.example.valhalla

import android.app.Dialog
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.random.Random

class MainActivity : AppCompatActivity() {

    companion object {
        const val PASSWORD      = "777"
        const val ORG_PASSWORD  = "145963278"
        const val TARGET_IP     = "127.0.0.1"
        const val MAX_INPUT_LEN = 12

        const val COLOR_TEXT = "#00FF41"
        const val COLOR_BG   = "#0D0D0D"
        const val COLOR_WARN = "#FFFF00"
        const val COLOR_ERR  = "#FF0000"
        const val COLOR_LOG  = "#888888"
    }

    private lateinit var hudBar: TextView
    private lateinit var logView: TextView
    private lateinit var scrollView: ScrollView
    private lateinit var inputDisplay: EditText
    private lateinit var btnUsb: Button
    private lateinit var btnCancel: Button
    private lateinit var actionBar: View

    private val handler = Handler(Looper.getMainLooper())
    private val audio by lazy { AudioEngine() }
    private val startTime = System.currentTimeMillis()

    private var nodeStatus = "LOCAL_TTY"

    private val inputBuffer = StringBuilder()
    private var inputActive = false
    private var inputLatch: CountDownLatch? = null
    private var inputResult: String? = null

    private var sigRounds = 3
    private var sigZone = 5
    private var sigMaxErrors = 2
    private var sigSpeed = 0.09
    private var fileDelayMs = 120L
    private var lockPointOverride: Int? = null
    private var fakeFiles = mutableListOf<String>()

    private val cancelRequested = AtomicBoolean(false)

    init {
        for (i in 1..20) fakeFiles.add("SEC_DATA_BLOCK_%02d.DAT".format(i))
        fakeFiles.add("ENCRYPTED_CORE.BIN")
        fakeFiles.add("LOG_FINAL.DAT")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        hudBar = findViewById(R.id.hudBar)
        logView = findViewById(R.id.logView)
        scrollView = findViewById(R.id.scrollView)
        inputDisplay = findViewById(R.id.inputDisplay)
        btnUsb = findViewById(R.id.btnUsb)
        btnCancel = findViewById(R.id.btnCancel)
        actionBar = findViewById(R.id.actionBar)

        val numButtons = mapOf(
            R.id.nBtn0 to '0', R.id.nBtn1 to '1', R.id.nBtn2 to '2',
            R.id.nBtn3 to '3', R.id.nBtn4 to '4', R.id.nBtn5 to '5',
            R.id.nBtn6 to '6', R.id.nBtn7 to '7', R.id.nBtn8 to '8',
            R.id.nBtn9 to '9'
        )
        for ((id, ch) in numButtons) {
            findViewById<Button>(id).setOnClickListener { numpadDigit(ch) }
        }
        findViewById<Button>(R.id.nBtnBack).setOnClickListener { numpadBack() }
        findViewById<Button>(R.id.nBtnOk).setOnClickListener { numpadOk() }

        inputDisplay.isFocusable = false
        inputDisplay.isClickable = false

        btnCancel.setOnClickListener {
            cancelRequested.set(true)
            appendLine("\n[ !! ] ЗАПРОС ПРЕРЫВАНИЯ...", COLOR_WARN)
        }

        startHud()
        thread { gameLoop() }
    }

    private fun numpadDigit(ch: Char) {
        if (!inputActive) return
        if (inputBuffer.length >= MAX_INPUT_LEN) return
        inputBuffer.append(ch)
        audio.play("key_press")
        updateInputDisplay()
    }

    private fun numpadBack() {
        if (!inputActive) return
        if (inputBuffer.isNotEmpty()) {
            inputBuffer.deleteCharAt(inputBuffer.length - 1)
            audio.play("key_back")
            updateInputDisplay()
        }
    }

    private fun numpadOk() {
        if (!inputActive) return
        inputResult = inputBuffer.toString()
        inputActive = false
        audio.play("key_ok")
        inputLatch?.countDown()
    }

    private fun updateInputDisplay() {
        handler.post { inputDisplay.setText(inputBuffer.toString()) }
    }

    private fun startHud() {
        val runnable = object : Runnable {
            override fun run() {
                val elapsed = (System.currentTimeMillis() - startTime) / 1000
                val h = elapsed / 3600
                val m = (elapsed % 3600) / 60
                val s = elapsed % 60
                val strength = Random.nextInt(94, 100)
                val now = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
                hudBar.text = "[ NODE: $nodeStatus ] | [ UPTIME: %02d:%02d:%02d ] | [ STR: $strength%% ] | [ $now ]"
                    .format(h, m, s)
                handler.postDelayed(this, 1000)
            }
        }
        handler.post(runnable)
    }

    private fun appendLine(text: String, color: String = COLOR_TEXT, animated: Boolean = false) {
        handler.post {
            val ssb = SpannableStringBuilder()
            if (logView.text.isNotEmpty()) ssb.append("\n")
            ssb.append(text)
            ssb.setSpan(
                ForegroundColorSpan(Color.parseColor(color)),
                0, ssb.length,
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
            )
            logView.append(ssb)
            scrollView.post { scrollView.fullScroll(View.FOCUS_DOWN) }
        }
        if (animated) Thread.sleep((text.length * 18 + 100).toLong())
    }

    private fun clearLog() {
        handler.post {
            logView.text = ""
            scrollView.post { scrollView.fullScroll(View.FOCUS_DOWN) }
        }
    }

    private fun askInput(prompt: String): String {
        val latch = CountDownLatch(1)
        inputLatch = latch
        inputResult = null
        inputBuffer.setLength(0)
        inputActive = true

        handler.post {
            inputDisplay.hint = prompt
            inputDisplay.setText("")
            inputDisplay.visibility = View.VISIBLE
        }

        latch.await()
        handler.post { inputDisplay.visibility = View.GONE }
        return inputResult ?: ""
    }

    private fun showUsbOnly() {
        handler.post {
            actionBar.visibility = View.VISIBLE
            btnUsb.visibility = View.VISIBLE
            btnCancel.visibility = View.GONE
        }
    }

    private fun showCancelOnly() {
        handler.post {
            actionBar.visibility = View.VISIBLE
            btnUsb.visibility = View.GONE
            btnCancel.visibility = View.VISIBLE
        }
    }

    private fun hideActionBar() {
        handler.post { actionBar.visibility = View.GONE }
    }

    private fun waitUsb(): Boolean {
        val latch = CountDownLatch(1)
        val result = AtomicBoolean(false)
        handler.post {
            showUsbOnly()
            btnUsb.setOnClickListener {
                audio.play("usb_ok")
                result.set(true)
                latch.countDown()
            }
        }
        latch.await()
        showCancelOnly()
        return result.get()
    }

    private fun gameLoop() {
        audio.startAmbient()
        while (true) {
            clearLog()
            nodeStatus = "BOOT_SEQUENCE"
            boot()
            nodeStatus = "AUTH_PROTOCOL"
            val isOrg = auth()
            if (isOrg) {
                organizerSetup()
                continue
            }
            connectLoop()
        }
    }

    private fun boot() {
        appendLine("UNIX System V Release 4.0 (tty1)", animated = true)
        Thread.sleep(300)
        for ((idx, line) in listOf(
            "[    0.00 ] UNIX Kernel version 4.0.1-release",
            "[    0.85 ] usb: host controller initialized",
            "[    1.50 ] fs: mounting root filesystem... done",
            "[    2.00 ] services: daemon started",
        ).withIndex()) {
            if (idx % 2 == 0) audio.play("boot_tick") else audio.play("tick_low")
            appendLine(line)
            Thread.sleep(200)
        }
    }

    private fun auth(): Boolean {
        while (true) {
            appendLine("\nВведите пароль:", animated = true)
            val pwd = askInput("password: ")
            appendLine("password: ${"*".repeat(pwd.length)}")

            if (pwd == ORG_PASSWORD) {
                audio.play("access_org")
                appendLine("\n[ ACCESS GRANTED: ORGANIZER MODE ]", animated = true)
                return true
            }
            if (pwd == PASSWORD) {
                audio.play("access_ok")
                appendLine("\nWelcome. Secure connection ready.", animated = true)
                return false
            }
            audio.play("access_fail")
            appendLine("\nPassword incorrect. Try again.\n", COLOR_ERR, animated = true)
            Thread.sleep(800)
        }
    }

    private fun organizerSetup() {
        while (true) {
            clearLog()
            divider("=")
            appendLine("  VALHALLA  ::  ПАНЕЛЬ АДМИНИСТРАТОРА")
            divider("=")
            appendLine("")
            appendLine("  1. ВРЕМЯ КОПИРОВАНИЯ      [ ${fmtCopyTime()} ]")
            appendLine("  2. РАУНДОВ В МИНИГРЕ       [ $sigRounds ]")
            appendLine("  3. ШИРИНА ПРИЦЕЛА          [ $sigZone ]")
            appendLine("  4. НАЧАЛЬНАЯ СКОРОСТЬ      [ %.3f сек/тик ]".format(sigSpeed))
            appendLine("  5. ДОПУСТИМО ПРОМАХОВ      [ $sigMaxErrors ]")
            appendLine("  6. ПОЗИЦИЯ МИНИГРЫ         [ ${fmtLockPoint()} ]")
            appendLine("")
            appendLine("  0. ВЫЙТИ ИЗ НАСТРОЕК")
            divider("=")

            val choice = askInput("  ВЫБОР: ").trim()
            if (choice.isNotEmpty()) audio.play("menu_cycle")

            when (choice) {
                "0" -> {
                    audio.play("menu_exit")
                    appendLine("\nВЫХОД ИЗ РЕЖИМА НАСТРОЙКИ...", animated = true)
                    Thread.sleep(800)
                    return
                }
                "1" -> {
                    val m = askFloat("  ВРЕМЯ (МИН, 0.5–60): ", 5.0, 0.5, 60.0)
                    val count = maxOf(20, (m * 24).toInt())
                    fakeFiles = mutableListOf()
                    for (i in 1..count) fakeFiles.add("SEC_DATA_BLOCK_%03d.DAT".format(i))
                    fakeFiles.add("ENCRYPTED_CORE.BIN")
                    fakeFiles.add("LOG_FINAL.DAT")
                    fileDelayMs = (m * 60 * 1000 / fakeFiles.size).toLong()
                    appendLine("  OK: ${fakeFiles.size} файлов, ~$m мин")
                }
                "2" -> sigRounds = askInt("  РАУНДОВ (1–5): ", sigRounds, 1, 5)
                "3" -> sigZone = askInt("  ШИРИНА ПРИЦЕЛА (2–12): ", sigZone, 2, 12)
                "4" -> sigSpeed = askFloat("  СКОРОСТЬ (0.02=быстро, 0.2=медленно): ", sigSpeed, 0.02, 0.2)
                "5" -> sigMaxErrors = askInt("  МАКС ПРОМАХОВ (0–5): ", sigMaxErrors, 0, 5)
                "6" -> {
                    val v = askInt("  ПОЗИЦИЯ % (0–95, 0=случайно): ", 0, 0, 95)
                    lockPointOverride = if (v > 0) v else null
                    appendLine("  OK: ${if (v > 0) "$v%" else "случайно"}")
                }
            }
            Thread.sleep(600)
        }
    }

    private fun fmtCopyTime(): String {
        val totalSec = fileDelayMs * fakeFiles.size / 1000.0
        return "%.1f мин".format(totalSec / 60.0)
    }

    private fun fmtLockPoint(): String = lockPointOverride?.let { "$it%" } ?: "случайно"

    private fun askInt(prompt: String, default: Int, lo: Int, hi: Int): Int {
        val raw = askInput(prompt)
        val v = raw.toIntOrNull()
        if (v == null) {
            appendLine("  ! Неверный формат, оставлено: $default", COLOR_WARN)
            return default
        }
        if (v < lo || v > hi) {
            appendLine("  ! Вне диапазона [$lo..$hi], оставлено: $default", COLOR_WARN)
            return default
        }
        return v
    }

    private fun askFloat(prompt: String, default: Double, lo: Double, hi: Double): Double {
        val raw = askInput(prompt)
        val v = raw.replace(',', '.').toDoubleOrNull()
        if (v == null) {
            appendLine("  ! Неверный формат, оставлено: $default", COLOR_WARN)
            return default
        }
        if (v < lo || v > hi) {
            appendLine("  ! Вне диапазона [$lo..$hi], оставлено: $default", COLOR_WARN)
            return default
        }
        return v
    }

    private fun connectLoop() {
        appendLine(">>> Connecting to $TARGET_IP...", animated = true)
        Thread.sleep(800)
        nodeStatus = "VALHALLA_CORE"
        appendLine(">>> Session authorized. Remote shell active.", animated = true)
        Thread.sleep(600)

        appendLine("╔════════════════════════════════════════════════════════════╗")
        appendLine("   V  A  L  H  A  L  L  A    S  E  R  V  E  R    C  O  R  E   ")
        appendLine("╚════════════════════════════════════════════════════════════╝")
        Thread.sleep(200)
        mainMenuLoop()
    }

    private fun mainMenuLoop() {
        while (true) {
            divider("-")
            appendLine("1. КОПИРОВАТЬ ДАННЫЕ НА НОСИТЕЛЬ")
            appendLine("2. СКАНЕР СЕТЕВОГО ОКРУЖЕНИЯ")
            appendLine("3. ПРОСМОТР СИСТЕМНЫХ ЛОГОВ")
            appendLine("4. ПЕРЕЗАГРУЗКА СИСТЕМЫ")
            divider("-")

            val choice = askInput("root:~# ").trim()
            appendLine("root:~# $choice")
            if (choice.isNotEmpty()) audio.play("menu_cycle")

            when (choice) {
                "1" -> cmdCopy()
                "2" -> cmdScan()
                "3" -> cmdLogs()
                "4" -> {
                    appendLine("\n>>> ИНИЦИАЛИЗАЦИЯ ПЕРЕЗАГРУЗКИ...", COLOR_ERR, animated = true)
                    audio.play("menu_exit")
                    Thread.sleep(1200)
                    hideActionBar()
                    return
                }
            }
        }
    }

    private fun cmdCopy() {
        cancelRequested.set(false)

        appendLine(">>> ПРОВЕРКА USB_SLOTS...", animated = true)
        appendLine(">>> ОЖИДАНИЕ НОСИТЕЛЯ (ВСТАВЬТЕ USB)...", COLOR_WARN)
        waitUsb()
        appendLine("[ OK ] УСТРОЙСТВО USB0 ИДЕНТИФИЦИРОВАНО.\n")
        audio.play("file_start")

        val lockPoint = lockPointOverride ?: Random.nextInt(30, 71)
        var lockDone = false

        for ((i, filename) in fakeFiles.withIndex()) {
            if (cancelRequested.get()) {
                finishCancel()
                return
            }

            val progress = (i + 1) * 100 / fakeFiles.size

            if (progress >= lockPoint && !lockDone) {
                audio.play("alert")
                appendLine("")
                appendLine("[ ВНИМАНИЕ ] ШИФРОВАНИЕ БЛОКА $progress% — ТРЕБУЕТСЯ СИНХРОНИЗАЦИЯ КЛЮЧА", COLOR_WARN)
                appendLine("[ ЗАХВАТИТЕ СИГНАЛ ДЛЯ ПРОДОЛЖЕНИЯ ПЕРЕДАЧИ ]", COLOR_WARN)
                appendLine("")

                val passed = signalLockGame()
                if (!passed) {
                    lockout()
                    return
                }
                audio.play("sync_ok")
                appendLine("[ OK ] КЛЮЧ СИНХРОНИЗИРОВАН. ПРОДОЛЖЕНИЕ ПЕРЕДАЧИ...\n")
                lockDone = true
                showCancelOnly()
            }

            val filled = progress / 5
            val bar = "#".repeat(filled) + ".".repeat(20 - filled)
            appendLine("[$bar] $progress% ЗАПИСЬ: $filename")
            audio.play("file_progress")
            Thread.sleep(fileDelayMs)
        }

        appendLine("\n[ OK ] SECURITY LOCK FILE GENERATED.", animated = true)
        audio.play("file_done")
        appendLine("\n[ УСПЕХ ] ПЕРЕДАЧА ЗАВЕРШЕНА.", animated = true)

        hideActionBar()
    }

    private fun finishCancel() {
        audio.play("cancel_beep")
        appendLine("")
        appendLine("[ ОТМЕНЕНО ] ПЕРЕДАЧА ПРЕРВАНА ПОЛЬЗОВАТЕЛЕМ.", COLOR_ERR)
        appendLine("[ ] НЕЗАВЕРШЁННЫЕ БЛОКИ НЕ СОХРАНЕНЫ.", COLOR_WARN)
        appendLine("[ ] КЛЮЧ ШИФРОВАНИЯ ОСТАЛСЯ АКТИВЕН — ПОВТОРИТЕ ПЕРЕДАЧУ.\n", COLOR_WARN)
        hideActionBar()
    }

    private fun signalLockGame(): Boolean {
        appendLine("")
        appendLine("  ┌─────────────────────────────────┐", COLOR_WARN)
        appendLine("    VALHALLA :: БЛОКИРОВКА СИГНАЛА   ", COLOR_WARN)
        appendLine("      ОТКРЫТО ОКНО СИНХРОНИЗАЦИИ     ", COLOR_WARN)
        appendLine("  └─────────────────────────────────┘", COLOR_WARN)
        appendLine("")

        val resultLatch = CountDownLatch(1)
        val success = AtomicBoolean(false)

        handler.post {
            val dialog = Dialog(this)
            dialog.setContentView(R.layout.dialog_minigame)
            dialog.setCancelable(false)
            dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
            dialog.window?.setLayout(
                (resources.displayMetrics.widthPixels * 0.75).toInt(),
                (resources.displayMetrics.heightPixels * 0.55).toInt()
            )

            val dlgScale = dialog.findViewById<TextView>(R.id.dlgScale)
            val dlgHits = dialog.findViewById<TextView>(R.id.dlgHits)
            val dlgEnter = dialog.findViewById<Button>(R.id.dlgEnter)
            val dlgCancel = dialog.findViewById<Button>(R.id.dlgCancel)

            val W = 22
            val ZONE = sigZone

            var markerPos = 0
            var markerDir = 1
            var speed = sigSpeed
            val cursorPos = (W - ZONE) / 2
            var errors = 0
            var hits = 0
            var started = false

            val tickHandler = Handler(Looper.getMainLooper())
            var lastTick = System.currentTimeMillis()

            val tickRunnable = object : Runnable {
                override fun run() {
                    if (started) {
                        val now = System.currentTimeMillis()
                        if (now - lastTick >= (speed * 1000).toLong()) {
                            markerPos += markerDir
                            if (markerPos >= W - 1) markerDir = -1
                            else if (markerPos <= 0) markerDir = 1
                            lastTick = now
                        }
                        dlgScale.text = renderScale(W, ZONE, markerPos, cursorPos)
                    }
                    tickHandler.postDelayed(this, 30)
                }
            }

            fun updateHits() {
                dlgHits.text = "ПОПАДАНИЯ: $hits/$sigRounds     ПРОМАХИ: $errors/$sigMaxErrors"
            }

            fun closeDialog(ok: Boolean) {
                tickHandler.removeCallbacksAndMessages(null)
                dialog.dismiss()
                success.set(ok)
                resultLatch.countDown()
            }

            dlgEnter.setOnClickListener {
                if (!started) {
                    started = true
                    dlgEnter.text = "ENTER"
                    audio.play("boot_tick")
                    return@setOnClickListener
                }

                val captured = markerPos in cursorPos until (cursorPos + ZONE)
                if (captured) {
                    audio.play("signal_hit")
                    hits++
                    updateHits()
                    appendLine("  [ ЗАХВАТ $hits/$sigRounds ] СИГНАЛ ЗАФИКСИРОВАН")
                    if (hits >= sigRounds) {
                        closeDialog(true)
                    } else {
                        speed = maxOf(0.03, speed * 0.75)
                    }
                } else {
                    audio.play("signal_miss")
                    errors++
                    updateHits()
                    val bar = "X".repeat(errors) + "O".repeat((sigMaxErrors + 1 - errors).coerceAtLeast(0))
                    appendLine("  [!!] МИМО  [$bar]", COLOR_ERR)
                    if (errors > sigMaxErrors) {
                        closeDialog(false)
                    }
                }
            }

            dlgCancel.setOnClickListener {
                cancelRequested.set(true)
                appendLine("\n[ !! ] ЗАПРОС ПРЕРЫВАНИЯ...", COLOR_WARN)
                closeDialog(false)
            }

            updateHits()
            dlgScale.text = renderScale(W, ZONE, markerPos, cursorPos)
            audio.play("menu_open")
            dialog.show()
            tickHandler.post(tickRunnable)
        }

        resultLatch.await()
        return success.get()
    }

    private fun renderScale(width: Int, zone: Int, marker: Int, cursor: Int): String {
        val sb = StringBuilder("|")
        for (i in 0 until width) {
            val inZone = i in cursor until (cursor + zone)
            val isMarker = (i == marker)
            sb.append(
                when {
                    isMarker && inZone -> "*"
                    isMarker -> "O"
                    i == cursor -> "["
                    i == cursor + zone - 1 -> "]"
                    inZone -> " "
                    else -> "."
                }
            )
        }
        sb.append("|")
        return sb.toString()
    }

    private fun lockout() {
        nodeStatus = "!!! INTRUSION DETECTED !!!"
        audio.play("lockout")
        Thread.sleep(400)
        clearLog()
        Thread.sleep(200)

        appendLine("", COLOR_ERR)
        appendLine("  ██╗███╗   ██╗████████╗██████╗ ██╗   ██╗███████╗██╗ ██████╗ ███╗   ██╗", COLOR_ERR)
        appendLine("  ██║████╗  ██║╚══██╔══╝██╔══██╗██║   ██║╚════██║██║██╔═══██╗████╗  ██║", COLOR_ERR)
        appendLine("  ██║██╔██╗ ██║   ██║   ██████╔╝██║   ██║    ██╔╝██║██║   ██║██╔██╗ ██║", COLOR_ERR)
        appendLine("  ██║██║╚██╗██║   ██║   ██╔══██╗██║   ██║   ██╔╝ ██║██║   ██║██║╚██╗██║", COLOR_ERR)
        appendLine("  ██║██║ ╚████║   ██║   ██║  ██║╚██████╔╝   ██║  ██║╚██████╔╝██║ ╚████║", COLOR_ERR)
        appendLine("  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝", COLOR_ERR)
        appendLine("", COLOR_ERR)
        appendLine("  ВЫЯВЛЕНА ПОПЫТКА НЕСАНКЦИОНИРОВАННОГО ВТОРЖЕНИЯ", COLOR_ERR)
        appendLine("  ИНИЦИИРОВАНА АВАРИЙНАЯ ПЕРЕЗАГРУЗКА СИСТЕМЫ", COLOR_ERR)
        appendLine("  ДАННЫЕ ИНЦИДЕНТА ПЕРЕДАНЫ В СЛУЖБУ БЕЗОПАСНОСТИ", COLOR_ERR)
        appendLine("", COLOR_ERR)

        Thread.sleep(800)
        for (i in 5 downTo 1) {
            appendLine("  $i...", COLOR_ERR)
            audio.play("countdown")
            Thread.sleep(850)
        }
        audio.beep(200, 1000)
        hideActionBar()
    }

    private fun cmdScan() {
        appendLine(">>> Scanning subnet...", animated = true)
        repeat(5) {
            val ip = "192.168.1.${Random.nextInt(2, 255)}"
            audio.play("boot_tick")
            appendLine("Node found: $ip [ONLINE]")
            Thread.sleep(400)
        }
    }

    private fun cmdLogs() {
        appendLine(">>> Reading system.log...", animated = true)
        val fmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
        repeat(10) {
            val ts = fmt.format(Date())
            val result = if (Random.nextBoolean()) "granted" else "denied"
            appendLine("LOG: $ts - Access $result", COLOR_LOG)
            audio.play("tick_low")
            Thread.sleep(80)
        }
    }

    private fun divider(char: String = "-", width: Int = 60) {
        appendLine(char.repeat(width))
    }

    override fun onDestroy() {
        audio.stopAmbient()
        audio.release()
        super.onDestroy()
    }
}