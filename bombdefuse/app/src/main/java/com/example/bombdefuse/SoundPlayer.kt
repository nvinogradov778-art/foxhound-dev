package com.example.bombdefuse

import android.content.Context
import android.media.SoundPool

enum class GameSound(val resId: Int) {
    CLICK(R.raw.click),
    ERROR(R.raw.error),
    UNLOCK(R.raw.unlock),
    ARM(R.raw.arm),
    DEFUSED(R.raw.defused),
    BOOM(R.raw.boom),
    TICK(R.raw.tick)
}

class SoundPlayer(context: Context) {

    private val pool = SoundPool.Builder()
        .setMaxStreams(6)
        .build()

    private val ids = mutableMapOf<GameSound, Int>()

    init {
        GameSound.values().forEach { sound ->
            ids[sound] = pool.load(context, sound.resId, 1)
        }
    }

    fun play(sound: GameSound) {
        ids[sound]?.let { id ->
            pool.play(id, 1f, 1f, 1, 0, 1f)
        }
    }

    fun release() {
        pool.release()
    }
}