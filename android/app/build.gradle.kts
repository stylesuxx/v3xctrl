import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kover)
}

val localProperties = Properties().apply {
    val localPropertiesFile = rootProject.file("local.properties")
    if (localPropertiesFile.exists()) {
        load(localPropertiesFile.inputStream())
    }
}
val gstDir = localProperties.getProperty("gst.dir") ?: "/home/chris/android-gst"

// Gradle always answers findProperty("version"), falling back to its own
// Project.DEFAULT_VERSION placeholder when -Pversion is absent.
val appVersion: String = project.findProperty("version")?.toString()
    ?.takeIf { it.isNotEmpty() && it != Project.DEFAULT_VERSION }
    ?: providers.exec { commandLine("git", "rev-parse", "--short", "HEAD") }
        .standardOutput.asText.get().trim().ifEmpty { "dev" }

// Android refuses to install an APK whose versionCode is lower than the installed
// one, so a semantic version maps to a monotonically increasing integer:
// 1.2.3 -> 10203. This requires minor and patch to stay below 100. Versions that
// are not semantic (a git hash for a dev build) resolve to 1.
fun resolveVersionCode(version: String): Int {
    val explicitVersionCode = project.findProperty("versionCode")?.toString()?.takeIf { it.isNotEmpty() }
    if (explicitVersionCode != null) {
        return explicitVersionCode.toInt()
    }

    val semanticVersion = Regex("""^(\d+)\.(\d+)\.(\d+)""").find(version)
    if (semanticVersion == null) {
        return 1
    }

    val (major, minor, patch) = semanticVersion.destructured

    return major.toInt() * 10000 + minor.toInt() * 100 + patch.toInt()
}

val appVersionCode: Int = resolveVersionCode(appVersion)

fun resolveSigningProperty(propertyName: String, environmentName: String): String? {
    val value = project.findProperty(propertyName)?.toString()
        ?: localProperties.getProperty(propertyName)
        ?: System.getenv(environmentName)

    return value?.takeIf { it.isNotEmpty() }
}

val releaseKeystorePath = resolveSigningProperty("keystorePath", "ANDROID_KEYSTORE_PATH")
val releaseKeystorePassword = resolveSigningProperty("keystorePassword", "ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = resolveSigningProperty("keyAlias", "ANDROID_KEY_ALIAS")
val releaseKeyPassword = resolveSigningProperty("keyPassword", "ANDROID_KEY_PASSWORD")

val hasReleaseSigningConfig = releaseKeystorePath != null &&
    releaseKeystorePassword != null &&
    releaseKeyAlias != null &&
    releaseKeyPassword != null

val signingConfigHelp = "Provide keystorePath, keystorePassword, keyAlias and keyPassword as " +
    "Gradle properties, in local.properties, or as ANDROID_KEYSTORE_PATH, " +
    "ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS and ANDROID_KEY_PASSWORD in the environment."

android {
    namespace = "com.v3xctrl.viewer"
    compileSdk = 36
    ndkVersion = "25.2.9519653"

    defaultConfig {
        applicationId = "com.v3xctrl.viewer"
        minSdk = 24
        targetSdk = 36
        versionCode = appVersionCode
        versionName = appVersion

        buildConfigField("String", "APP_VERSION", "\"$appVersion\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigningConfig) {
                storeFile = file(releaseKeystorePath!!)
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }

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
        buildConfig = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
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

// An unconfigured signing config packages an unsigned APK that no device installs,
// so stop before packaging instead.
tasks.matching { it.name == "packageRelease" }.configureEach {
    doFirst {
        if (!hasReleaseSigningConfig) {
            throw GradleException("Release signing is not configured. $signingConfigHelp")
        }
    }
}

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
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}