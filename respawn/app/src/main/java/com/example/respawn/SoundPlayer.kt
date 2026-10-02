package com.example.respawn

import android.content.Context
import android.media.SoundPool

enum class GameSound(val resId: Int) {
    START(R.raw.start),
    WAVE_RELEASE(R.raw.wave_release),
    GAME_OVER(R.raw.game_over),
    CLICK(R.raw.click),
    CLICK_DOWN(R.raw.click_down),
    OK(R.raw.ok),
    DEATH(R.raw.death),
    RESPAWN_CANCEL(R.raw.respawn_cancel),
    PAUSE(R.raw.pause),
    RESUME(R.raw.resume)
}

class SoundPlayer(context: Context) {

    private val pool = SoundPool.Builder()
        .setMaxStreams(4)
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