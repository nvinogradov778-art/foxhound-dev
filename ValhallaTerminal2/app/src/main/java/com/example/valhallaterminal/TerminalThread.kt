package com.example.valhallaterminal

import kotlin.random.Random
import java.util.Date
import java.text.SimpleDateFormat
import java.util.Locale

class TerminalThread(private val activity: MainActivity) : Thread() {

    @Volatile var userInput: String? = null
    @Volatile var arrowKey: String? = null

    private val random = Random.Default

    private var sigRounds = 3
    private var sigZone = 5
    private var sigMaxErrors = 2
    private var sigSpeed = 0.09
    private var fileDelayMs = 120L
    private var fakeFiles = mutableListOf<String>()
    private var lockPointOverride: Int? = null

    private var startTime = System.currentTimeMillis()

    @Volatile
    private var minigameResult: Boolean? = null

    fun getUptimeString(): String {
        val elapsed = (System.currentTimeMillis() - startTime) / 1000
        val h = elapsed / 3600
        val m = (elapsed % 3600) / 60
        val s = elapsed % 60
        return String.format("%02d:%02d:%02d", h, m, s)
    }

    override fun run() {
        resetFakeFiles()
        while (true) {
            activity.clearLog()
            activity.updateHudNode("BOOT_SEQUENCE")
            bootSequence()
            activity.updateHudNode("AUTH_PROTOCOL")
            val isOrganizer = auth()
            if (isOrganizer) {
                organizerSetup()
                continue
            }
            mainMenuLoop()
        }
    }

    private fun resetFakeFiles() {
        fakeFiles = (1..20).map { String.format("SEC_DATA_BLOCK_%02d.DAT", it) }.toMutableList()
        fakeFiles.add("ENCRYPTED_CORE.BIN")
        fakeFiles.add("LOG_FINAL.DAT")
        fileDelayMs = 120
    }

    private fun waitInput(prompt: String = ""): String {
        userInput = null
        activity.enableInput(true, prompt)
        while (userInput == null) {
            sleep(100)
        }
        return userInput!!
    }

    private fun waitArrow(): String {
        arrowKey = null
        while (arrowKey == null) {
            sleep(30)
        }
        return arrowKey!!
    }

    private fun printLine(text: String, color: String = "#00FF41", animated: Boolean = false) {
        activity.appendLog(text, color)
        if (animated) sleep(text.length * 20L + 150)
    }

    private fun printRaw(text: String, color: String = "#00FF41") {
        activity.appendLog(text, color)
    }

    private fun divider(char: String = "-", width: Int = 60) {
        printRaw(char.repeat(width))
    }

    private fun askInt(prompt: String, default: Int, lo: Int, hi: Int): Int {
        val raw = waitInput(prompt)
        return try {
            val value = raw.toInt()
            if (value in lo..hi) value
            else {
                printRaw("  ! Вне диапазона [$lo..$hi], оставлено: $default", "#FFFF00")
                default
            }
        } catch (e: NumberFormatException) {
            printRaw("  ! Неверный формат, оставлено: $default", "#FFFF00")
            default
        }
    }

    private fun askFloat(prompt: String, default: Double, lo: Double, hi: Double): Double {
        val raw = waitInput(prompt).replace(',', '.')
        return try {
            val value = raw.toDouble()
            if (value in lo..hi) value
            else {
                printRaw("  ! Вне диапазона [$lo..$hi], оставлено: $default", "#FFFF00")
                default
            }
        } catch (e: NumberFormatException) {
            printRaw("  ! Неверный формат, оставлено: $default", "#FFFF00")
            default
        }
    }

    private fun bootSequence() {
        printRaw("VALHALLA System V Release 4.0 (tty1)")
        sleep(400)
        val lines = listOf(
            "[  +0.000000] VALHALLA Kernel version 4.0.1-release",
            "[  +0.041205] Network: IP 192.168.12.25 is connected",
            "[  +0.128491] fs: mounting root filesystem... done",
            "[  +0.482019] services: daemon started",
            "[  +0.510000] security: access control initialized",
            ">>> Введите пароль Администратора:"
        )
        for (line in lines) {
            activity.beep(1800.0, 30)
            printRaw(line)
            sleep(200)
        }
    }

    private fun auth(): Boolean {
        while (true) {
            val pwd = waitInput("Пароль: ").trim()
            when (pwd) {
                "145963278" -> {
                    activity.beep(1500.0, 100)
                    printLine("\n[ Доступ разрешен: Режим организатора ]", "#00FF41")
                    return true
                }
                "777" -> {
                    activity.beep(1200.0, 80)
                    printLine("\n ДОБРО ПОЖАЛОВАТЬ В СИСТЕМУ <<VALHALLA>>", "#00FF41")
                    return false
                }
                else -> {
                    activity.beep(300.0, 200)
                    printLine("\nОШИБКА! ПОВТОРИТЕ ПОПЫТКУ.\n", "#FF0000")
                    sleep(1000)
                }
            }
        }
    }

    private fun organizerSetup() {
        while (true) {
            activity.clearLog()
            divider("=")
            printRaw("  VALHALLA  ::  ПАНЕЛЬ АДМИНИСТРАТОРА", "#00FF41")
            divider("=")
            printRaw("")
            printRaw("  1. ВРЕМЯ КОПИРОВАНИЯ      [ ${formatCopyTime()} ]")
            printRaw("  2. РАУНДОВ В МИНИГРЕ       [ $sigRounds ]")
            printRaw("  3. ШИРИНА ПРИЦЕЛА          [ $sigZone ]")
            printRaw("  4. НАЧАЛЬНАЯ СКОРОСТЬ      [ ${"%.3f".format(sigSpeed)} сек/тик ]")
            printRaw("  5. ДОПУСТИМО ПРОМАХОВ      [ $sigMaxErrors ]")
            printRaw("  6. ПОЗИЦИЯ МИНИГРЫ         [ ${formatLockPoint()} ]")
            printRaw("")
            printRaw("  0. ВЫЙТИ ИЗ НАСТРОЕК")
            printRaw("")
            divider("=")

            when (val choice = waitInput("  ВЫБОР: ")) {
                "0" -> {
                    printLine("\nВЫХОД ИЗ РЕЖИМА НАСТРОЙКИ...", "#00FF41")
                    sleep(1000)
                    return
                }
                "1" -> {
                    val minutes = askFloat("  ВРЕМЯ (МИН, 0.5–60): ", 5.0, 0.5, 60.0)
                    val count = maxOf(22, (minutes * 24).toInt())
                    fakeFiles = (1..count).map { String.format("SEC_DATA_BLOCK_%03d.DAT", it) }.toMutableList()
                    fakeFiles.add("ENCRYPTED_CORE.BIN")
                    fakeFiles.add("LOG_FINAL.DAT")
                    fileDelayMs = ((minutes * 60 * 1000) / fakeFiles.size).toLong()
                    printRaw("  OK: ${fakeFiles.size} файлов, ~$minutes мин", "#FFFF00")
                }
                "2" -> sigRounds = askInt("  РАУНДОВ (1–5): ", sigRounds, 1, 5)
                "3" -> {
                    sigZone = askInt("  ШИРИНА ПРИЦЕЛА (2–12): ", sigZone, 2, 12)
                    printRaw("  OK: зона захвата = $sigZone симв.", "#FFFF00")
                }
                "4" -> sigSpeed = askFloat("  СКОРОСТЬ (0.02=быстро, 0.2=медленно): ", sigSpeed, 0.02, 0.2)
                "5" -> sigMaxErrors = askInt("  МАКС ПРОМАХОВ (0–5): ", sigMaxErrors, 0, 5)
                "6" -> {
                    printRaw("  Введите % прогресса копирования когда появится минигра,", "#FFFF00")
                    printRaw("  или 0 для случайного момента (30–70%).", "#FFFF00")
                    val value = askInt("  ПОЗИЦИЯ % (0–95): ", 0, 0, 95)
                    lockPointOverride = if (value > 0) value else null
                    val label = if (value > 0) "$value%" else "случайно"
                    printRaw("  OK: минигра появится в $label", "#FFFF00")
                }
            }
            sleep(800)
        }
    }

    private fun formatCopyTime(): String {
        val totalMs = fileDelayMs * fakeFiles.size
        val seconds = totalMs / 1000.0
        return String.format("%.1f мин", seconds / 60)
    }

    private fun formatLockPoint(): String {
        return lockPointOverride?.let { "$it%" } ?: "случайно"
    }

    private fun startMinigame(warning: String = "", instruction: String = ""): Boolean {
        minigameResult = null
        val title = if (warning.isNotEmpty()) warning else "ПЕРЕХВАТ СИГНАЛА"
        val subtitle = instruction
        activity.launchMinigame(sigRounds, sigZone, sigMaxErrors, sigSpeed, title, subtitle)
        return waitForMinigameResult()
    }

    private fun waitForMinigameResult(): Boolean {
        while (minigameResult == null) {
            sleep(100)
        }
        return minigameResult!!
    }

    fun onMinigameResult(success: Boolean) {
        minigameResult = success
    }

    private fun lockout() {
        activity.updateHudNode("!!! INTRUSION DETECTED !!!")
        activity.beep(500.0, 300)
        sleep(400)
        activity.clearLog()
        sleep(200)

        val headerLines = listOf(
            "  ========================================================",
            "  ========================================================",
            "  ====ВЫЯВЛЕНА ПОПЫТКА НЕСАНКЦИОНИРОВАННОГО ВТОРЖЕНИЯ=====",
            "  ========================================================",
            "  =======ИНИЦИИРОВАНА АВАРИЙНАЯ ПЕРЕЗАГРУЗКА СИСТЕМЫ======",
            "  =======ВСЕ АКТИВНЫЕ СЕССИИ ПРИНУДИТЕЛЬНО ЗАВЕРШЕНЫ======",
            "  ========================================================",
            "  ========================================================"
        )

        for (line in headerLines) {
            activity.appendLog(line, "#FF0000")
            sleep(100)
        }

        val now = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        val incidentId = "${(10000..99999).random()}-SEC"
        val msgs = listOf(
            "  [ $now ]  INCIDENT_ID: $incidentId",
            "  [ $now ]  SOURCE: 127.0.0.1",
            "  [ $now ]  THREAT_LEVEL: CRITICAL",
            "  [ $now ]  ACTION: EMERGENCY_REBOOT_SCHEDULED"
        )

        for (msg in msgs) {
            activity.appendLog(msg, "#FF0000")
            activity.beep(800.0, 80)
            sleep(300)
        }

        activity.appendLog("", "#FF0000")
        for (i in 5 downTo 1) {
            val dots = ".".repeat(6 - i)
            val line = "  Аварийная перезагрузка$dots"
            activity.appendLog(line, "#FF0000")
            activity.beep((600 + (5 - i) * 200).toDouble(), 150)
            sleep(800)
        }
        activity.appendLog("  Аварийная перезагрузка... ГОТОВО", "#FF0000")
        activity.beep(200.0, 1000)
        sleep(500)

        activity.clearLog()
        sleep(300)
    }

    private fun mainMenuLoop() {
        while (true) {
            divider()
            val items = listOf(
                "1. КОПИРОВАТЬ ДАННЫЕ НА НОСИТЕЛЬ",
                "2. СКАНЕР СЕТЕВОГО ОКРУЖЕНИЯ",
                "3. ПРОСМОТР СИСТЕМНЫХ ЛОГОВ",
                "4. ОЧИСТИТЬ ЭКРАН ТЕРМИНАЛА",
                "5. ПЕРЕЗАГРУЗКА ЛОКАЛЬНОЙ СИСТЕМЫ",
                "6. ЗАВЕРШИТЬ СЕТЕВОЙ СЕАНС"
            )
            for (item in items) printRaw(item)
            divider()

            when (val choice = waitInput("root@valhalla:~# ")) {
                "1" -> cmdCopy()
                "2" -> cmdScan()
                "3" -> cmdLogs()
                "4" -> activity.clearLog()
                "5" -> {
                    printLine("\n>>> ИНИЦИАЛИЗАЦИЯ ПЕРЕЗАГРУЗКИ...", "#FF0000")
                    sleep(1000)
                    return
                }
                "6" -> return
            }
        }
    }

    private fun cmdCopy() {
        printLine(">>> ЗАПРОС НА ПОДКЛЮЧЕНИЕ К СЕРВЕРУ...", "#00FF41")
        waitForServerConnection()
        printLine("[ OK ] СЕРВЕР ДОСТУПЕН.\n", "#00FF41")
        activity.beep(800.0, 150)

        val lockPoint = lockPointOverride ?: random.nextInt(30, 71)
        var lockDone = false
        val startCopyTime = System.currentTimeMillis()

        for ((i, filename) in fakeFiles.withIndex()) {
            val progress = ((i + 1) * 100 / fakeFiles.size)
            if (progress >= lockPoint && !lockDone) {
                activity.beep(900.0, 200)
                val warning = "[ ВНИМАНИЕ ] ШИФРОВАНИЕ БЛОКА $progress% — ТРЕБУЕТСЯ СИНХРОНИЗАЦИЯ КЛЮЧА"
                val instruction = "[ ЗАХВАТИТЕ СИГНАЛ ДЛЯ ПРОДОЛЖЕНИЯ ПЕРЕДАЧИ ]"
                val passed = startMinigame(warning, instruction)
                if (!passed) {
                    lockout()
                    return
                }
                activity.beep(1000.0, 100)
                lockDone = true
            }

            val filled = progress / 5
            val barColor = when {
                progress < 50 -> "#00FF41"
                progress < 80 -> "#FFFF00"
                else -> "#FF4444"
            }
            val bar = "█".repeat(filled) + "░".repeat(20 - filled)
            printRaw("[$bar] $progress% ПЕРЕДАЧА: $filename", barColor)
            sleep(fileDelayMs)
        }

        val endCopyTime = System.currentTimeMillis()
        val totalSeconds = (endCopyTime - startCopyTime) / 1000.0
        val fileCount = fakeFiles.size
        val avgSpeed = if (totalSeconds > 0) fileCount / totalSeconds else 0.0

        activity.beep(1200.0, 80)

        printLine("\n" + "=".repeat(60), "#00FF41")
        printLine("  ПЕРЕДАЧА УСПЕШНО ЗАВЕРШЕНА", "#00FF41")
        printLine("=".repeat(60), "#00FF41")
        printLine("  Файлов передано: $fileCount", "#00FF41")
        printLine("  Общее время:    ${String.format("%.2f", totalSeconds)} сек", "#00FF41")
        printLine("  Средняя скорость: ${String.format("%.2f", avgSpeed)} файл/сек", "#00FF41")

        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
        printLine("  Завершено:      ${dateFormat.format(Date())}", "#00FF41")
        printLine("  СОЕДИНЕНИЕ ЗАКРЫТО.", "#00FF41")
        printLine("=".repeat(60), "#00FF41")
    }

    private fun waitForServerConnection() {
        printLine(">>> УСТАНОВКА ЗАЩИЩЁННОГО СОЕДИНЕНИЯ С СЕРВЕРОМ...", "#00FF41")
        sleep(2000)
        printLine("[ OK ] ПОДКЛЮЧЕНИЕ УСТАНОВЛЕНО.", "#00FF41")
    }

    private fun cmdScan() {
        printLine(">>> Scanning subnet...", "#00FF41")
        for (i in 0 until 5) {
            val ip = "192.168.1.${random.nextInt(2, 255)}"
            activity.beep(1800.0, 30)
            printRaw("Node found: $ip [ONLINE]", "#888888")
            sleep(400)
        }
    }

    private fun cmdLogs() {
        printLine(">>> Reading system.log...", "#00FF41")
        for (i in 0 until 10) {
            val ts = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
            val result = listOf("granted", "denied").random()
            printRaw("LOG: $ts - Access $result", "#888888")
            sleep(100)
        }
    }
}