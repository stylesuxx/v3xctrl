#include <jni.h>
#include <stdlib.h>
#include <pthread.h>
#include <android/log.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <gst/gst.h>
#include <gst/video/videooverlay.h>

#define LOG_TAG "GstViewer"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

#define MAX_RESTARTS 5
#define RESTART_WINDOW_US (30 * G_USEC_PER_SEC)
#define STATS_INTERVAL_SECS 5

typedef struct {
    GstElement *pipeline;
    GstElement *video_sink;
    GMainLoop *main_loop;
    ANativeWindow *native_window;
    gboolean initialized;
    gint video_port;
    pthread_t thread;
    gboolean thread_active;
} GstViewerData;

static GstViewerData gst_data = {0};

// Pipeline auto-restart rate limiting
static gint restart_count = 0;
static gint64 restart_window_start = 0;

// Per-element buffer counters for diagnosing where data stops flowing
static volatile gint count_udpsrc = 0;
static volatile gint count_jitterbuffer = 0;
static volatile gint count_depay = 0;
static volatile gint count_decoder = 0;
static volatile gint count_sink = 0;

// Stats logging toggle (controlled from Java via JNI)
static volatile gboolean stats_enabled = FALSE;

// Probe IDs for diagnostic probes (0 = not attached)
static gulong probe_id_udpsrc = 0;
static gulong probe_id_jitterbuffer = 0;
static gulong probe_id_depay = 0;
static gulong probe_id_decoder = 0;
static guint stats_timer_id = 0;

static GstPadProbeReturn count_udpsrc_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_udpsrc++;
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn count_jitterbuffer_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_jitterbuffer++;
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn count_depay_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_depay++;
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn count_decoder_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_decoder++;
    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn count_sink_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_sink++;  // Always count sink frames (used by FPS counter)
    return GST_PAD_PROBE_OK;
}

// Periodic stats logging — shows buffer counts per element to identify where data stops
static gboolean log_stats_cb(gpointer user_data) {
    if (!gst_data.pipeline) {
        return G_SOURCE_REMOVE;
    }

    LOGI("Pipeline stats: udpsrc=%d jbuf=%d depay=%d dec=%d sink=%d",
         count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);

    return G_SOURCE_CONTINUE;
}

static gulong add_src_pad_probe(const gchar *element_name, GstPadProbeCallback cb) {
    gulong probe_id = 0;
    GstElement *el = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), element_name);
    if (el) {
        GstPad *pad = gst_element_get_static_pad(el, "src");
        if (pad) {
            probe_id = gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, cb, NULL, NULL);
            gst_object_unref(pad);
        }
        gst_object_unref(el);
    } else {
        LOGW("Could not find element '%s' for pad probe", element_name);
    }
    return probe_id;
}

static void remove_src_pad_probe(const gchar *element_name, gulong probe_id) {
    GstElement *el = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), element_name);
    if (el) {
        GstPad *pad = gst_element_get_static_pad(el, "src");
        if (pad) {
            gst_pad_remove_probe(pad, probe_id);
            gst_object_unref(pad);
        }
        gst_object_unref(el);
    }
}

static void attach_stats_probes(void) {
    if (!gst_data.pipeline || gst_data.video_port == 0) {
        return;
    }

    count_udpsrc = 0;
    count_jitterbuffer = 0;
    count_depay = 0;
    count_decoder = 0;

    probe_id_udpsrc = add_src_pad_probe("src", count_udpsrc_cb);
    probe_id_jitterbuffer = add_src_pad_probe("jbuf", count_jitterbuffer_cb);
    probe_id_depay = add_src_pad_probe("depay", count_depay_cb);
    probe_id_decoder = add_src_pad_probe("dec", count_decoder_cb);

    stats_timer_id = g_timeout_add_seconds(STATS_INTERVAL_SECS, log_stats_cb, NULL);
}

static void detach_stats_probes(void) {
    if (gst_data.pipeline) {
        if (probe_id_udpsrc) {
            remove_src_pad_probe("src", probe_id_udpsrc);
        }
        if (probe_id_jitterbuffer) {
            remove_src_pad_probe("jbuf", probe_id_jitterbuffer);
        }
        if (probe_id_depay) {
            remove_src_pad_probe("depay", probe_id_depay);
        }
        if (probe_id_decoder) {
            remove_src_pad_probe("dec", probe_id_decoder);
        }
    }
    probe_id_udpsrc = 0;
    probe_id_jitterbuffer = 0;
    probe_id_depay = 0;
    probe_id_decoder = 0;

    if (stats_timer_id) {
        g_source_remove(stats_timer_id);
        stats_timer_id = 0;
    }
}

static gboolean restart_pipeline_cb(gpointer user_data) {
    if (!gst_data.pipeline) {
        return G_SOURCE_REMOVE;
    }

    // Rate limit: max MAX_RESTARTS in RESTART_WINDOW_US
    gint64 now = g_get_monotonic_time();
    if (now - restart_window_start > RESTART_WINDOW_US) {
        restart_count = 0;
        restart_window_start = now;
    }
    restart_count++;

    if (restart_count > MAX_RESTARTS) {
        LOGE("Too many pipeline restarts (%d in 30s), giving up", MAX_RESTARTS);
        g_main_loop_quit(gst_data.main_loop);
        return G_SOURCE_REMOVE;
    }

    LOGI("Restarting pipeline (attempt %d/%d)", restart_count, MAX_RESTARTS);
    gst_element_set_state(gst_data.pipeline, GST_STATE_NULL);

    // Re-apply native window handle after NULL state
    if (gst_data.video_sink && gst_data.native_window) {
        gst_video_overlay_set_window_handle(
            GST_VIDEO_OVERLAY(gst_data.video_sink),
            (guintptr)gst_data.native_window
        );
    }

    GstStateChangeReturn ret = gst_element_set_state(gst_data.pipeline, GST_STATE_PLAYING);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        LOGE("Failed to restart pipeline");
        g_main_loop_quit(gst_data.main_loop);
    }

    return G_SOURCE_REMOVE;
}

static void on_error(GstBus *bus, GstMessage *msg, gpointer data) {
    GError *err;
    gchar *debug_info;
    gst_message_parse_error(msg, &err, &debug_info);
    LOGE("Error from %s: %s", GST_OBJECT_NAME(msg->src), err->message);
    if (debug_info) {
        LOGD("Debug info: %s", debug_info);
    }
    g_clear_error(&err);
    g_free(debug_info);

    LOGI("Pipeline stats at error: udpsrc=%d jbuf=%d depay=%d dec=%d sink=%d",
         count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);

    // Schedule pipeline restart instead of quitting
    g_idle_add(restart_pipeline_cb, NULL);
}

static void on_warning(GstBus *bus, GstMessage *msg, gpointer data) {
    GError *err;
    gchar *debug_info;
    gst_message_parse_warning(msg, &err, &debug_info);
    LOGW("Warning from %s: %s", GST_OBJECT_NAME(msg->src), err->message);
    if (debug_info) {
        LOGD("Debug info: %s", debug_info);
    }
    g_clear_error(&err);
    g_free(debug_info);
}

static void on_eos(GstBus *bus, GstMessage *msg, gpointer data) {
    LOGI("End of stream, restarting pipeline");
    g_idle_add(restart_pipeline_cb, NULL);
}

static void on_qos(GstBus *bus, GstMessage *msg, gpointer data) {
    gboolean live;
    guint64 running_time, stream_time, timestamp, duration;
    gint64 jitter;
    gdouble proportion;
    gint quality;

    gst_message_parse_qos(msg, &live, &running_time, &stream_time, &timestamp, &duration);
    gst_message_parse_qos_values(msg, &jitter, &proportion, &quality);

    LOGW("QoS from %s: jitter=%" G_GINT64_FORMAT "us proportion=%.2f quality=%d",
         GST_OBJECT_NAME(msg->src), jitter, proportion, quality);
}

static void on_state_changed(GstBus *bus, GstMessage *msg, gpointer data) {
    GstState old_state, new_state, pending_state;
    gst_message_parse_state_changed(msg, &old_state, &new_state, &pending_state);

    if (GST_MESSAGE_SRC(msg) == GST_OBJECT(gst_data.pipeline)) {
        LOGI("Pipeline state changed from %s to %s",
             gst_element_state_get_name(old_state),
             gst_element_state_get_name(new_state));
    }
}

static void *gst_main_loop_thread(void *arg) {
    LOGI("Starting GStreamer main loop");
    g_main_loop_run(gst_data.main_loop);
    LOGI("GStreamer main loop ended");
    return NULL;
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeInit(JNIEnv *env, jclass clazz) {
    if (gst_data.initialized) {
        LOGI("GStreamer already initialized");
        return;
    }

    LOGI("Initializing GStreamer");

    // Force GLES 2.0 for better emulator compatibility
    setenv("GST_GL_API", "gles2", 1);

    gst_init(NULL, NULL);
    gst_data.initialized = TRUE;
    LOGI("GStreamer initialized successfully");
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeStartPipeline(JNIEnv *env, jclass clazz, jobject surface, jint port) {
    if (!gst_data.initialized) {
        LOGE("GStreamer not initialized");
        return;
    }

    if (gst_data.pipeline) {
        LOGI("Pipeline already running");
        return;
    }

    // Get native window from surface
    gst_data.native_window = ANativeWindow_fromSurface(env, surface);
    if (!gst_data.native_window) {
        LOGE("Failed to get native window from surface");
        return;
    }

    gst_data.video_port = port;
    LOGI("Creating video receiver pipeline on port %d", port);

    // For debugging: use test source if port is 0, otherwise use RTP receiver
    GError *error = NULL;
    gchar *pipeline_str = NULL;

    if (port == 0) {
        // Test pipeline - same as original working code
        pipeline_str = g_strdup(
            "videotestsrc pattern=smpte ! "
            "videoconvert ! "
            "glimagesink name=videosink"
        );
    } else {
        // RTP H264 receiver pipeline — elements named for diagnostic pad probes
        pipeline_str = g_strdup_printf(
            "udpsrc name=src port=%d caps=\"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000\" ! "
            "rtpjitterbuffer name=jbuf latency=0 drop-on-latency=true ! "
            "rtph264depay name=depay ! "
            "h264parse name=parse ! "
            "avdec_h264 name=dec ! "
            "videoconvert ! "
            "glimagesink name=videosink sync=false",
            port
        );
    }

    LOGI("Pipeline: %s", pipeline_str);
    gst_data.pipeline = gst_parse_launch(pipeline_str, &error);
    g_free(pipeline_str);

    if (error) {
        LOGE("Pipeline parse error: %s", error->message);
        g_error_free(error);
    }

    if (!gst_data.pipeline) {
        LOGE("Failed to create pipeline");
        ANativeWindow_release(gst_data.native_window);
        gst_data.native_window = NULL;
        return;
    }

    // Get video sink and set native window
    gst_data.video_sink = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), "videosink");
    if (gst_data.video_sink) {
        gst_video_overlay_set_window_handle(
            GST_VIDEO_OVERLAY(gst_data.video_sink),
            (guintptr)gst_data.native_window
        );
    }

    // Sink probe always attached (used by FPS counter)
    count_sink = 0;
    if (gst_data.video_sink) {
        GstPad *sink_pad = gst_element_get_static_pad(gst_data.video_sink, "sink");
        if (sink_pad) {
            gst_pad_add_probe(sink_pad, GST_PAD_PROBE_TYPE_BUFFER, count_sink_cb, NULL, NULL);
            gst_object_unref(sink_pad);
        }
    }

    // Diagnostic probes only when stats are enabled
    if (stats_enabled) {
        attach_stats_probes();
    }

    // Set up bus watch
    GstBus *bus = gst_element_get_bus(gst_data.pipeline);
    gst_bus_add_signal_watch(bus);
    g_signal_connect(bus, "message::error", G_CALLBACK(on_error), NULL);
    g_signal_connect(bus, "message::warning", G_CALLBACK(on_warning), NULL);
    g_signal_connect(bus, "message::eos", G_CALLBACK(on_eos), NULL);
    g_signal_connect(bus, "message::qos", G_CALLBACK(on_qos), NULL);
    g_signal_connect(bus, "message::state-changed", G_CALLBACK(on_state_changed), NULL);
    gst_object_unref(bus);

    // Create main loop
    gst_data.main_loop = g_main_loop_new(NULL, FALSE);

    // Reset restart counter for new pipeline
    restart_count = 0;
    restart_window_start = 0;

    // Start playing
    GstStateChangeReturn ret = gst_element_set_state(gst_data.pipeline, GST_STATE_PLAYING);
    LOGI("State change returned: %d (0=FAILURE, 1=SUCCESS, 2=ASYNC, 3=NO_PREROLL)", ret);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        LOGE("Failed to start pipeline - state change failed");
        // Try to get more info about the failure
        GstBus *err_bus = gst_element_get_bus(gst_data.pipeline);
        GstMessage *msg = gst_bus_pop_filtered(err_bus, GST_MESSAGE_ERROR);
        if (msg) {
            GError *err = NULL;
            gchar *debug = NULL;
            gst_message_parse_error(msg, &err, &debug);
            LOGE("Pipeline error: %s", err->message);
            if (debug) LOGD("Debug: %s", debug);
            g_error_free(err);
            g_free(debug);
            gst_message_unref(msg);
        }
        gst_object_unref(err_bus);
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        ANativeWindow_release(gst_data.native_window);
        gst_data.native_window = NULL;
        return;
    }

    LOGI("Pipeline started successfully, waiting for video on port %d", port);

    // Run main loop in a separate thread (joinable, not detached)
    gst_data.thread_active = TRUE;
    pthread_create(&gst_data.thread, NULL, gst_main_loop_thread, NULL);
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeStopPipeline(JNIEnv *env, jclass clazz) {
    LOGI("Stopping pipeline");

    if (gst_data.main_loop) {
        g_main_loop_quit(gst_data.main_loop);
    }

    // Wait for main loop thread to exit before cleanup
    if (gst_data.thread_active) {
        pthread_join(gst_data.thread, NULL);
        gst_data.thread_active = FALSE;
    }

    if (gst_data.pipeline) {
        gst_element_set_state(gst_data.pipeline, GST_STATE_NULL);
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
    }

    if (gst_data.video_sink) {
        gst_object_unref(gst_data.video_sink);
        gst_data.video_sink = NULL;
    }

    if (gst_data.main_loop) {
        g_main_loop_unref(gst_data.main_loop);
        gst_data.main_loop = NULL;
    }

    if (gst_data.native_window) {
        ANativeWindow_release(gst_data.native_window);
        gst_data.native_window = NULL;
    }

    // Probes are removed with the pipeline; just reset IDs and timer
    probe_id_udpsrc = 0;
    probe_id_jitterbuffer = 0;
    probe_id_depay = 0;
    probe_id_decoder = 0;
    if (stats_timer_id) {
        g_source_remove(stats_timer_id);
        stats_timer_id = 0;
    }

    gst_data.video_port = 0;
    restart_count = 0;
    LOGI("Pipeline stopped");
}

JNIEXPORT jint JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetRestartCount(JNIEnv *env, jclass clazz) {
    return restart_count;
}

JNIEXPORT jint JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetFrameCount(JNIEnv *env, jclass clazz) {
    return count_sink;
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeRestartPipeline(JNIEnv *env, jclass clazz) {
    if (!gst_data.pipeline || !gst_data.main_loop) return;

    LOGI("Manual pipeline restart requested");
    LOGI("Pipeline stats at restart: udpsrc=%d jbuf=%d depay=%d dec=%d sink=%d",
         count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);

    gst_element_set_state(gst_data.pipeline, GST_STATE_NULL);

    if (gst_data.video_sink && gst_data.native_window) {
        gst_video_overlay_set_window_handle(
            GST_VIDEO_OVERLAY(gst_data.video_sink),
            (guintptr)gst_data.native_window
        );
    }

    gst_element_set_state(gst_data.pipeline, GST_STATE_PLAYING);
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeFinalize(JNIEnv *env, jclass clazz) {
    Java_com_v3xctrl_viewer_GstViewer_nativeStopPipeline(env, clazz);
    gst_data.initialized = FALSE;
    LOGI("GStreamer finalized");
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeSetStatsEnabled(JNIEnv *env, jclass clazz, jboolean enabled) {
    if (enabled && !stats_enabled) {
        stats_enabled = TRUE;
        attach_stats_probes();
    } else if (!enabled && stats_enabled) {
        stats_enabled = FALSE;
        detach_stats_probes();
    }
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetPipelineStats(JNIEnv *env, jclass clazz) {
    gchar buf[128];
    g_snprintf(buf, sizeof(buf), "%d|%d|%d|%d|%d",
               count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);
    return (*env)->NewStringUTF(env, buf);
}
