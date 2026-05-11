# Arena Android App

Open this folder in Android Studio (Hedgehog or newer) and click Run, or build from the command line:

    ./gradlew assembleDebug

The signed-debug APK appears at:
    app/build/outputs/apk/debug/app-debug.apk

The app is a native Kotlin WebView wrapping the polished Arena UI in app/src/main/assets/index.html.
You can also host index.html on any static host — it's a fully installable PWA on Android (Chrome ▸ Add to Home screen).
