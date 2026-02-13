import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

val localProperties = Properties().apply {
    val localPropertiesFile = rootProject.file("local.properties")
    if (localPropertiesFile.exists()) {
        load(localPropertiesFile.inputStream())
    }
}
val gstDir = localProperties.getProperty("gst.dir") ?: "/home/chris/android-gst"

android {
    namespace = "com.v3xctrl.viewer"
    compileSdk = 36
    ndkVersion = "25.2.9519653"

    defaultConfig {
        applicationId = "com.v3xctrl.viewer"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
    }
}

val ndkDir = android.ndkDirectory.absolutePath
val abiList = listOf("arm64-v8a", "armeabi-v7a", "x86_64")
val jniLibsDir = file("src/main/jniLibs")

val buildNativeLibs by tasks.registering {
    val jniDir = file("src/main/jni")
    inputs.files(fileTree(jniDir) { include("**/*.c", "**/*.h", "**/*.mk") })
    outputs.dir(jniLibsDir)

    doLast {
        abiList.forEach { abi ->
            exec {
                commandLine(
                    "$ndkDir/ndk-build",
                    "NDK_PROJECT_PATH=null",
                    "APP_BUILD_SCRIPT=${jniDir}/Android.mk",
                    "NDK_APPLICATION_MK=${jniDir}/Application.mk",
                    "APP_ABI=$abi",
                    "NDK_ALL_ABIS=$abi",
                    "APP_PLATFORM=android-24",
                    "NDK_OUT=${layout.buildDirectory.get()}/ndk/obj",
                    "NDK_LIBS_OUT=${layout.buildDirectory.get()}/ndk/libs",
                    "GSTREAMER_ROOT_ANDROID=$gstDir"
                )
                workingDir = projectDir
            }
            // Copy .so files to jniLibs
            val outDir = file("${layout.buildDirectory.get()}/ndk/libs/$abi")
            val destDir = file("$jniLibsDir/$abi")
            destDir.mkdirs()
            outDir.listFiles()?.filter { it.extension == "so" }?.forEach { so ->
                so.copyTo(File(destDir, so.name), overwrite = true)
            }
            // Copy libc++_shared.so required by APP_STL=c++_shared
            val triple = when (abi) {
                "arm64-v8a" -> "aarch64-linux-android"
                "armeabi-v7a" -> "arm-linux-androideabi"
                "x86_64" -> "x86_64-linux-android"
                else -> return@forEach
            }
            val stlLib = file("$ndkDir/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/$triple/libc++_shared.so")
            if (stlLib.exists()) {
                stlLib.copyTo(File(destDir, "libc++_shared.so"), overwrite = true)
            }
        }
    }
}

tasks.named("preBuild") { dependsOn(buildNativeLibs) }

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("org.msgpack:msgpack-core:0.9.8")
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}