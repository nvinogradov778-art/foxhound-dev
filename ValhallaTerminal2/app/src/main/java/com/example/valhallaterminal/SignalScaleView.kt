package com.example.valhallaterminal

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View

class SignalScaleView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private var markerPos = 0f
    private var zoneStart = 0f
    private var zoneWidth = 0f

    private val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(40, 0, 255, 65)
        style = Paint.Style.FILL
    }
    private val markerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#00FF41")
        style = Paint.Style.FILL
    }
    private val zonePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(120, 0, 255, 65)
        style = Paint.Style.FILL
    }
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#00FF41")
        style = Paint.Style.STROKE
        strokeWidth = 1.5f
    }
    private val cellBorderPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(80, 0, 255, 65)
        style = Paint.Style.STROKE
        strokeWidth = 0.5f
    }

    fun update(marker: Int, zoneStart: Int, zoneWidth: Int, maxWidth: Int) {
        this.markerPos = marker.toFloat()
        this.zoneStart = zoneStart.toFloat()
        this.zoneWidth = zoneWidth.toFloat()
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        val padding = 20f
        val usableWidth = w - 2 * padding
        val step = usableWidth / 38f

        canvas.drawRoundRect(padding, 10f, w - padding, h - 10f, 10f, 10f, bgPaint)

        val zoneLeft = padding + zoneStart * step
        val zoneRight = padding + (zoneStart + zoneWidth) * step
        canvas.drawRect(zoneLeft, 10f, zoneRight, h - 10f, zonePaint)

        for (i in 0..38) {
            val x = padding + i * step
            if (i >= zoneStart && i <= zoneStart + zoneWidth) {
                canvas.drawLine(x, 10f, x, h - 10f, cellBorderPaint)
            } else {
                canvas.drawLine(x, 10f, x, h - 10f, gridPaint)
            }
        }

        canvas.drawRect(padding, 10f, w - padding, h - 10f, gridPaint)

        val markerX = padding + markerPos * step
        canvas.drawCircle(markerX, h / 2, 14f, markerPaint)
    }
}