package com.atena.mobile

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val status = findViewById<TextView>(R.id.statusText)
        val openPanel = findViewById<Button>(R.id.openPanelButton)

        status.text = "ATENA AGI Mobile inicializada."

        openPanel.setOnClickListener {
            val url = "https://github.com/AtenaAuto/ATENA-"
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        }
    }
}
