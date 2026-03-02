#include <jni.h>
#include <stdlib.h>
#include <android/log.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <gst/gst.h>
#include <gst/video/videooverlay.h>
#include <gst/net/gstnetaddressmeta.h>
#include <gio/gio.h>

#define LOG_TAG "GstViewer"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)

typedef struct {
    GstElement *pipeline;
    GstElement *video_sink;
    GMainLoop *main_loop;
    ANativeWindow *native_window;
    gboolean initialized;
    gint video_port;
} GstViewerData;

static GstViewerData gst_data = {0};

/* Diagnostic counters (accessed from pad probe + JNI) */
static volatile gint64 stats_udpsrc_packets = 0;
static volatile gint64 stats_udpsrc_bytes = 0;
static gchar stats_last_source[64] = {0};
static GMutex stats_mutex;

static GstPadProbeReturn
udpsrc_probe_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    GstBuffer *buf = GST_PAD_PROBE_INFO_BUFFER(info);
    if (!buf) return GST_PAD_PROBE_OK;

    g_atomic_int_add((volatile gint *)&stats_udpsrc_packets, 1);
    g_atomic_int_add((volatile gint *)&stats_udpsrc_bytes,
                     (gint)gst_buffer_get_size(buf));

    GstNetAddressMeta *meta = gst_buffer_get_net_address_meta(buf);
    if (meta && meta->addr) {
        GInetSocketAddress *inet_addr =
            G_INET_SOCKET_ADDRESS(meta->addr);
        if (inet_addr) {
            GInetAddress *ip = g_inet_socket_address_get_address(inet_addr);
            guint16 port = g_inet_socket_address_get_port(inet_addr);
            gchar *ip_str = g_inet_address_to_string(ip);

            g_mutex_lock(&stats_mutex);
            g_snprintf(stats_last_source, sizeof(stats_last_source),
                       "%s:%u", ip_str, port);
            g_mutex_unlock(&stats_mutex);

            g_free(ip_str);
        }
    }

    return GST_PAD_PROBE_OK;
}

static void on_error(GstBus *bus, GstMessage *msg, gpointer data) {
    GError *err;
    gchar *debug_info;
    gst_message_parse_error(msg, &err, &debug_info);
    LOGE("Error: %s", err->message);
    if (debug_info) {
        LOGD("Debug info: %s", debug_info);
    }
    g_clear_error(&err);
    g_free(debug_info);
    g_main_loop_quit(gst_data.main_loop);
}

static void on_eos(GstBus *bus, GstMessage *msg, gpointer data) {
    LOGI("End of stream");
    g_main_loop_quit(gst_data.main_loop);
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
    g_mutex_init(&stats_mutex);
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

    /* Reset diagnostic counters */
    stats_udpsrc_packets = 0;
    stats_udpsrc_bytes = 0;
    g_mutex_lock(&stats_mutex);
    stats_last_source[0] = '\0';
    g_mutex_unlock(&stats_mutex);

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
        // RTP H264 receiver pipeline with software decoder
        pipeline_str = g_strdup_printf(
            "udpsrc name=src port=%d caps=\"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000\" ! "
            "rtpjitterbuffer latency=0 drop-on-latency=true ! "
            "rtph264depay ! "
            "h264parse ! "
            "avdec_h264 ! "
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

    /* Attach pad probe to udpsrc for diagnostics */
    if (port != 0) {
        GstElement *udpsrc = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), "src");
        if (udpsrc) {
            GstPad *srcpad = gst_element_get_static_pad(udpsrc, "src");
            if (srcpad) {
                gst_pad_add_probe(srcpad, GST_PAD_PROBE_TYPE_BUFFER,
                                  udpsrc_probe_cb, NULL, NULL);
                gst_object_unref(srcpad);
            }
            gst_object_unref(udpsrc);
        }
    }

    // Get video sink and set native window
    gst_data.video_sink = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), "videosink");
    if (gst_data.video_sink) {
        gst_video_overlay_set_window_handle(
            GST_VIDEO_OVERLAY(gst_data.video_sink),
            (guintptr)gst_data.native_window
        );
    }

    // Set up bus watch
    GstBus *bus = gst_element_get_bus(gst_data.pipeline);
    gst_bus_add_signal_watch(bus);
    g_signal_connect(bus, "message::error", G_CALLBACK(on_error), NULL);
    g_signal_connect(bus, "message::eos", G_CALLBACK(on_eos), NULL);
    g_signal_connect(bus, "message::state-changed", G_CALLBACK(on_state_changed), NULL);
    gst_object_unref(bus);

    // Create main loop
    gst_data.main_loop = g_main_loop_new(NULL, FALSE);

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

    // Run main loop in a separate thread
    pthread_t thread;
    pthread_create(&thread, NULL, gst_main_loop_thread, NULL);
    pthread_detach(thread);
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeStopPipeline(JNIEnv *env, jclass clazz) {
    LOGI("Stopping pipeline");

    if (gst_data.main_loop) {
        g_main_loop_quit(gst_data.main_loop);
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

    gst_data.video_port = 0;
    LOGI("Pipeline stopped");
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetStats(JNIEnv *env, jclass clazz) {
    gchar source_copy[64];

    g_mutex_lock(&stats_mutex);
    g_strlcpy(source_copy, stats_last_source, sizeof(source_copy));
    g_mutex_unlock(&stats_mutex);

    /* Pipeline state */
    const gchar *state_str = "NULL";
    gint local_port = gst_data.video_port;
    if (gst_data.pipeline) {
        GstState current = GST_STATE_NULL;
        gst_element_get_state(gst_data.pipeline, &current, NULL, 0);
        state_str = gst_element_state_get_name(current);
    }

    /* RTP jitterbuffer stats */
    gint64 jb_pushed = -1, jb_lost = -1, jb_late = -1;
    if (gst_data.pipeline) {
        GstElement *jb = gst_bin_get_by_name(GST_BIN(gst_data.pipeline),
                                              "rtpjitterbuffer0");
        if (jb) {
            GstStructure *jb_stats = NULL;
            g_object_get(jb, "stats", &jb_stats, NULL);
            if (jb_stats) {
                guint64 val;
                if (gst_structure_get_uint64(jb_stats, "num-pushed", &val))
                    jb_pushed = (gint64)val;
                if (gst_structure_get_uint64(jb_stats, "num-lost", &val))
                    jb_lost = (gint64)val;
                if (gst_structure_get_uint64(jb_stats, "num-late", &val))
                    jb_late = (gint64)val;
                gst_structure_free(jb_stats);
            }
            gst_object_unref(jb);
        }
    }

    gchar *stats = g_strdup_printf(
        "%lld|%lld|%s|%s|%d|%lld|%lld|%lld",
        (long long)stats_udpsrc_packets,
        (long long)stats_udpsrc_bytes,
        source_copy,
        state_str,
        local_port,
        (long long)jb_pushed,
        (long long)jb_lost,
        (long long)jb_late
    );

    jstring result = (*env)->NewStringUTF(env, stats);
    g_free(stats);
    return result;
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeFinalize(JNIEnv *env, jclass clazz) {
    Java_com_v3xctrl_viewer_GstViewer_nativeStopPipeline(env, clazz);
    gst_data.initialized = FALSE;
    LOGI("GStreamer finalized");
}
