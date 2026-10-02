package com.example.valhalla

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlin.math.PI
import kotlin.math.sin
import kotlin.random.Random

class AudioEngine {

    private val RATE = 44100
    private val cache = mutableMapOf<String, AudioTrack>()
    private var ambient: AudioTrack? = null

    init { buildAll() }

    private fun shortToBytes(arr: ShortArray): ByteArray {
        val out = ByteArray(arr.size * 2)
        for (i in arr.indices) {
            out[i * 2]     = (arr[i].toInt() and 0xFF).toByte()
            out[i * 2 + 1] = ((arr[i].toInt() shr 8) and 0xFF).toByte()
        }
        return out
    }

    private fun makeTrack(arr: ShortArray): AudioTrack {
        val bytes = shortToBytes(arr)
        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(RATE)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(bytes.size)
            .setTransferMode(AudioTrack.MODE_STATIC)
            .build()
        track.write(bytes, 0, bytes.size)
        return track
    }

    private fun square(freq: Double, durMs: Int, vol: Double = 0.6, duty: Double = 0.1): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        val arr = ShortArray(n)
        for (i in 0 until n) {
            val t = i.toDouble() / RATE
            val phase = (t * freq) % 1.0
            val v = if (phase < duty) 1.0 else -1.0
            arr[i] = (v * vol * 32767).toInt().coerceIn(-32767, 32767).toShort()
        }
        return arr
    }

    private fun detuned(f1: Double, f2: Double, durMs: Int, vol: Double = 0.55): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        val arr = ShortArray(n)
        for (i in 0 until n) {
            val t = i.toDouble() / RATE
            val p1 = (t * f1) % 1.0
            val p2 = (t * f2) % 1.0
            val v1 = if (p1 < 0.12) 1.0 else -1.0
            val v2 = if (p2 < 0.12) 1.0 else -1.0
            val mix = (v1 + v2) * 0.5
            arr[i] = (mix * vol * 32767).toInt().coerceIn(-32767, 32767).toShort()
        }
        return arr
    }

    private fun crushed(freq: Double, durMs: Int, vol: Double = 0.7, bits: Int = 2): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        val arr = ShortArray(n)
        val levels = (1 shl bits) - 1
        for (i in 0 until n) {
            val t = i.toDouble() / RATE
            val s = sin(2 * PI * freq * t) * 1.4
            val clipped = s.coerceIn(-1.0, 1.0)
            val q = Math.round((clipped + 1) / 2 * levels).toDouble() / levels * 2 - 1
            arr[i] = (q * vol * 32767).toInt().coerceIn(-32767, 32767).toShort()
        }
        return arr
    }

    private fun noise(durMs: Int, vol: Double = 0.3): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        return ShortArray(n) { (Random.nextDouble(-1.0, 1.0) * vol * 32767).toInt().toShort() }
    }

    private fun zap(durMs: Int, vol: Double = 0.7): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        val arr = ShortArray(n)
        var phase = 0.0
        for (i in 0 until n) {
            val freq = 2000.0 * (1.0 - i.toDouble() / n) + 200.0
            phase += freq / RATE
            if (phase > 1.0) phase -= 1.0
            val sq = if (phase < 0.15) 1.0 else -1.0
            val ns = Random.nextDouble(-1.0, 1.0)
            arr[i] = ((sq * 0.7 + ns * 0.3) * vol * 32767).toInt().coerceIn(-32767, 32767).toShort()
        }
        return arr
    }

    private fun siren(f0: Double, f1: Double, durMs: Int, vol: Double = 0.65): ShortArray {
        val n = (RATE * durMs / 1000.0).toInt()
        val arr = ShortArray(n)
        var phase = 0.0
        for (i in 0 until n) {
            val f = f0 + (f1 - f0) * i / n
            phase += f / RATE
            if (phase > 1.0) phase -= 1.0
            val sq = if (phase < 0.1) 1.0 else -1.0
            val ns = Random.nextDouble(-0.3, 0.3)
            arr[i] = ((sq + ns) * vol * 32767).toInt().coerceIn(-32767, 32767).toShort()
        }
        return arr
    }

    private fun silence(durMs: Int): ShortArray {
        return ShortArray((RATE * durMs / 1000.0).toInt())
    }

    private fun concat(vararg arrays: ShortArray): ShortArray {
        val total = arrays.sumOf { it.size }
        val out = ShortArray(total)
        var pos = 0
        for (a in arrays) {
            System.arraycopy(a, 0, out, pos, a.size)
            pos += a.size
        }
        return out
    }

    private fun buildAll() {

        cache["access_ok"] = makeTrack(concat(
            detuned(880.0, 890.0, 60, 0.55),
            detuned(1320.0, 1335.0, 100, 0.6)
        ))

        cache["access_org"] = makeTrack(concat(
            detuned(1000.0, 1008.0, 40, 0.6),
            detuned(1500.0, 1512.0, 40, 0.6),
            detuned(2000.0, 2016.0, 60, 0.65),
            detuned(2500.0, 2520.0, 100, 0.7)
        ))

        cache["access_fail"] = makeTrack(concat(
            crushed(180.0, 120, 0.75, 2), noise(30, 0.25),
            crushed(140.0, 140, 0.8, 2),  noise(30, 0.25),
            siren(120.0, 60.0, 350, 0.8)
        ))

        cache["key_press"] = makeTrack(concat(
            noise(6, 0.35), square(2200.0, 10, 0.45, 0.08)
        ))
        cache["key_back"] = makeTrack(concat(
            noise(5, 0.3), square(900.0, 18, 0.45, 0.08),
            noise(5, 0.25), square(500.0, 20, 0.45, 0.08)
        ))
        cache["key_ok"] = makeTrack(concat(
            detuned(1400.0, 1410.0, 25, 0.5),
            detuned(1900.0, 1915.0, 50, 0.55)
        ))

        cache["usb_ok"] = makeTrack(concat(
            noise(15, 0.4), square(1400.0, 25, 0.5, 0.1),
            noise(10, 0.3), zap(120, 0.7)
        ))

        cache["signal_hit"] = makeTrack(concat(
            detuned(1600.0, 1616.0, 40, 0.7),
            detuned(2200.0, 2224.0, 70, 0.75)
        ))
        cache["signal_miss"] = makeTrack(concat(
            crushed(200.0, 100, 0.85, 2), noise(60, 0.35),
            siren(180.0, 90.0, 180, 0.8)
        ))
        cache["alert"] = makeTrack(concat(
            detuned(1200.0, 1212.0, 70, 0.75), silence(15),
            detuned(1200.0, 1212.0, 70, 0.75), silence(15),
            detuned(1200.0, 1212.0, 70, 0.8), silence(15),
            siren(1800.0, 2400.0, 200, 0.85)
        ))
        cache["sync_ok"] = makeTrack(concat(
            detuned(1000.0, 1008.0, 40, 0.65),
            detuned(1500.0, 1512.0, 40, 0.65),
            detuned(2000.0, 2016.0, 90, 0.7)
        ))

        cache["boot_tick"] = makeTrack(concat(
            noise(8, 0.35), square(2800.0, 8, 0.35, 0.08)
        ))
        cache["tick_low"] = makeTrack(concat(
            noise(6, 0.3), square(1400.0, 8, 0.3, 0.08)
        ))

        cache["menu_open"] = makeTrack(concat(
            noise(15, 0.35), siren(700.0, 1600.0, 110, 0.7)
        ))
        cache["menu_cycle"] = makeTrack(concat(
            noise(5, 0.4), square(2000.0, 14, 0.45, 0.08)
        ))
        cache["menu_exit"] = makeTrack(concat(
            noise(10, 0.3), siren(1600.0, 500.0, 100, 0.7)
        ))

        cache["file_start"] = makeTrack(concat(
            detuned(800.0, 806.0, 25, 0.55),
            detuned(1200.0, 1208.0, 25, 0.6),
            detuned(1600.0, 1610.0, 50, 0.65)
        ))
        cache["file_progress"] = makeTrack(concat(
            noise(4, 0.4), square(3000.0, 6, 0.3, 0.06)
        ))
        cache["file_done"] = makeTrack(concat(
            detuned(1200.0, 1210.0, 40, 0.65),
            detuned(1600.0, 1612.0, 40, 0.7),
            detuned(2200.0, 2216.0, 40, 0.75),
            detuned(2800.0, 2820.0, 100, 0.8)
        ))
        cache["cancel_beep"] = makeTrack(concat(
            crushed(800.0, 80, 0.8, 2), square(600.0, 80, 0.7, 0.1),
            crushed(400.0, 120, 0.85, 2), noise(60, 0.35)
        ))

        cache["lockout"] = makeTrack(concat(
            crushed(220.0, 150, 0.9, 2), noise(50, 0.4),
            crushed(160.0, 150, 0.9, 2), noise(50, 0.4),
            siren(400.0, 150.0, 250, 0.9),
            crushed(80.0, 600, 1.0, 2)
        ))
        cache["countdown"] = makeTrack(concat(
            noise(8, 0.4), crushed(700.0, 80, 0.85, 2)
        ))

        val fan = noise(3000, 0.06)
        val hum = square(45.0, 3000, 0.035, 0.5)
        val hiss = noise(3000, 0.03)
        val amb = ShortArray(fan.size) { i ->
            val crackle = if (Random.nextInt(500) == 0) Random.nextInt(-30000, 30000) else 0
            (fan[i].toInt() + hum[i].toInt() + hiss[i].toInt() + crackle)
                .coerceIn(-32767, 32767).toShort()
        }
        ambient = makeTrack(amb)
    }

    fun play(name: String) {
        val track = cache[name] ?: return
        try {
            track.stop()
            track.reloadStaticData()
            track.play()
        } catch (_: Exception) {}
    }

    fun beep(freq: Int, durMs: Int, vol: Double = 0.7) {
        val track = makeTrack(square(freq.toDouble(), durMs, vol, 0.1))
        try {
            track.play()
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                try { track.stop(); track.release() } catch (_: Exception) {}
            }, durMs.toLong() + 50)
        } catch (_: Exception) {}
    }

    fun startAmbient() {
        val track = ambient ?: return
        try {
            track.setLoopPoints(0, track.bufferSizeInFrames, -1)
            track.play()
        } catch (_: Exception) {}
    }

    fun stopAmbient() {
        try { ambient?.stop() } catch (_: Exception) {}
    }

    fun release() {
        cache.values.forEach { try { it.release() } catch (_: Exception) {} }
        try { ambient?.release() } catch (_: Exception) {}
        cache.clear()
    }
}