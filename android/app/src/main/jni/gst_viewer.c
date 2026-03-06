#include <jni.h>
#include <stdlib.h>
#include <errno.h>
#include <pthread.h>
#include <sys/resource.h>
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
    GstElement *udpsrc;
    GstElement *jitterbuffer;
    GstElement *depay;
    GstElement *parser;
    GstElement *decodebin;
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

// Periodic stats logging - shows buffer counts per element to identify where data stops
static gboolean log_stats_cb(gpointer user_data) {
    if (!gst_data.pipeline) {
        return G_SOURCE_REMOVE;
    }

    LOGI("Pipeline stats: udpsrc=%d jbuf=%d depay=%d dec=%d sink=%d",
         count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);

    return G_SOURCE_CONTINUE;
}

static gulong add_element_src_probe(GstElement *element, GstPadProbeCallback cb) {
    gulong probe_id = 0;
    if (element) {
        GstPad *pad = gst_element_get_static_pad(element, "src");
        if (pad) {
            probe_id = gst_pad_add_probe(pad, GST_PAD_PROBE_TYPE_BUFFER, cb, NULL, NULL);
            gst_object_unref(pad);
        }
    }
    return probe_id;
}

static void remove_element_src_probe(GstElement *element, gulong probe_id) {
    if (element) {
        GstPad *pad = gst_element_get_static_pad(element, "src");
        if (pad) {
            gst_pad_remove_probe(pad, probe_id);
            gst_object_unref(pad);
        }
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

    probe_id_udpsrc = add_element_src_probe(gst_data.udpsrc, count_udpsrc_cb);
    probe_id_jitterbuffer = add_element_src_probe(gst_data.jitterbuffer, count_jitterbuffer_cb);
    probe_id_depay = add_element_src_probe(gst_data.depay, count_depay_cb);
    // Decoder probe is attached in on_decodebin_pad_added (dynamic pad)

    stats_timer_id = g_timeout_add_seconds(STATS_INTERVAL_SECS, log_stats_cb, NULL);
}

static void detach_stats_probes(void) {
    if (gst_data.pipeline) {
        if (probe_id_udpsrc) {
            remove_element_src_probe(gst_data.udpsrc, probe_id_udpsrc);
        }
        if (probe_id_jitterbuffer) {
            remove_element_src_probe(gst_data.jitterbuffer, probe_id_jitterbuffer);
        }
        if (probe_id_depay) {
            remove_element_src_probe(gst_data.depay, probe_id_depay);
        }
        // Decoder probe is on decodebin's dynamic src pad - remove via decodebin
        if (probe_id_decoder && gst_data.decodebin) {
            GstPad *src_pad = gst_element_get_static_pad(gst_data.decodebin, "src_0");
            if (src_pad) {
                gst_pad_remove_probe(src_pad, probe_id_decoder);
                gst_object_unref(src_pad);
            }
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

static void log_decodebin_decoder(GstElement *decodebin) {
    GstIterator *it = gst_bin_iterate_recurse(GST_BIN(decodebin));
    GValue item = G_VALUE_INIT;
    gboolean done = FALSE;

    while (!done) {
        switch (gst_iterator_next(it, &item)) {
        case GST_ITERATOR_OK: {
            GstElement *element = g_value_get_object(&item);
            GstElementFactory *factory = gst_element_get_factory(element);
            if (factory) {
                const gchar *klass = gst_element_factory_get_metadata(factory,
                    GST_ELEMENT_METADATA_KLASS);
                if (klass && g_strrstr(klass, "Decoder")) {
                    LOGI("Decoder selected by decodebin: %s (%s)",
                         GST_OBJECT_NAME(element),
                         gst_plugin_feature_get_name(GST_PLUGIN_FEATURE(factory)));
                }
            }
            g_value_reset(&item);
            break;
        }
        case GST_ITERATOR_RESYNC:
            gst_iterator_resync(it);
            break;
        case GST_ITERATOR_DONE:
        case GST_ITERATOR_ERROR:
        default:
            done = TRUE;
            break;
        }
    }

    g_value_unset(&item);
    gst_iterator_free(it);
}

static void on_decodebin_pad_added(GstElement *decodebin, GstPad *new_pad, gpointer user_data) {
    GstPad *sink_pad = gst_element_get_static_pad(gst_data.video_sink, "sink");

    if (gst_pad_is_linked(sink_pad)) {
        gst_object_unref(sink_pad);
        return;
    }

    GstCaps *caps = gst_pad_get_current_caps(new_pad);
    if (!caps) {
        caps = gst_pad_query_caps(new_pad, NULL);
    }

    GstStructure *structure = gst_caps_get_structure(caps, 0);
    const gchar *name = gst_structure_get_name(structure);

    if (g_str_has_prefix(name, "video/")) {
        GstPadLinkReturn ret = gst_pad_link(new_pad, sink_pad);
        if (ret != GST_PAD_LINK_OK) {
            LOGE("Failed to link decodebin to video sink: %d", ret);
        } else {
            LOGI("Linked decodebin to video sink (caps: %s)", name);
        }

        // Attach decoder probe on decodebin's output pad
        if (stats_enabled) {
            probe_id_decoder = gst_pad_add_probe(new_pad,
                GST_PAD_PROBE_TYPE_BUFFER, count_decoder_cb, NULL, NULL);
        }

        log_decodebin_decoder(decodebin);
    }

    gst_caps_unref(caps);
    gst_object_unref(sink_pad);
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
    // Raise thread priority for lower latency processing (-10 = audio/video priority)
    if (setpriority(PRIO_PROCESS, 0, -10) != 0) {
        LOGW("Failed to set GStreamer thread priority: %s", strerror(errno));
    }

    LOGI("Starting GStreamer main loop");
    g_main_loop_run(gst_data.main_loop);
    LOGI("GStreamer main loop ended");
    return NULL;
}

static gboolean create_test_pipeline(void) {
    GError *error = NULL;
    gchar *pipeline_str = g_strdup(
        "videotestsrc pattern=smpte ! "
        "videoconvert ! "
        "glimagesink name=videosink"
    );

    LOGI("Pipeline: %s", pipeline_str);
    gst_data.pipeline = gst_parse_launch(pipeline_str, &error);
    g_free(pipeline_str);

    if (error) {
        LOGE("Pipeline parse error: %s", error->message);
        g_error_free(error);
    }

    if (!gst_data.pipeline) {
        return FALSE;
    }

    gst_data.video_sink = gst_bin_get_by_name(GST_BIN(gst_data.pipeline), "videosink");
    return TRUE;
}

static gboolean create_rtp_pipeline(gint port) {
    gst_data.pipeline = gst_pipeline_new("viewer-pipeline");
    gst_data.udpsrc = gst_element_factory_make("udpsrc", "src");
    gst_data.jitterbuffer = gst_element_factory_make("rtpjitterbuffer", "jbuf");
    gst_data.depay = gst_element_factory_make("rtph264depay", "depay");
    gst_data.parser = gst_element_factory_make("h264parse", "parse");
    gst_data.decodebin = gst_element_factory_make("decodebin", "dec");
    gst_data.video_sink = gst_element_factory_make("glimagesink", "videosink");

    if (!gst_data.pipeline || !gst_data.udpsrc || !gst_data.jitterbuffer ||
        !gst_data.depay || !gst_data.parser || !gst_data.decodebin ||
        !gst_data.video_sink) {
        LOGE("Failed to create one or more pipeline elements");
        if (gst_data.pipeline) {
            gst_object_unref(gst_data.pipeline);
            gst_data.pipeline = NULL;
        }
        return FALSE;
    }

    // Configure udpsrc
    GstCaps *caps = gst_caps_from_string(
        "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000");
    g_object_set(gst_data.udpsrc, "port", port, "caps", caps, NULL);
    gst_caps_unref(caps);

    // Configure jitterbuffer for low latency
    g_object_set(gst_data.jitterbuffer, "latency", 0, "drop-on-latency", TRUE, NULL);

    // Configure video sink for low latency (no clock sync)
    g_object_set(gst_data.video_sink, "sync", FALSE, NULL);

    // Add all elements to the pipeline
    gst_bin_add_many(GST_BIN(gst_data.pipeline),
        gst_data.udpsrc, gst_data.jitterbuffer, gst_data.depay,
        gst_data.parser, gst_data.decodebin, gst_data.video_sink, NULL);

    // Link static chain: udpsrc -> jitterbuffer -> depay -> parser -> decodebin
    if (!gst_element_link_many(gst_data.udpsrc, gst_data.jitterbuffer,
                                gst_data.depay, gst_data.parser,
                                gst_data.decodebin, NULL)) {
        LOGE("Failed to link pipeline elements");
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        return FALSE;
    }

    // decodebin -> video_sink is linked dynamically when decodebin selects a decoder
    g_signal_connect(gst_data.decodebin, "pad-added",
        G_CALLBACK(on_decodebin_pad_added), NULL);

    LOGI("Pipeline: udpsrc port=%d ! rtpjitterbuffer ! rtph264depay ! h264parse ! decodebin ! glimagesink", port);
    return TRUE;
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

    gboolean created;
    if (port == 0) {
        created = create_test_pipeline();
    } else {
        created = create_rtp_pipeline(port);
    }

    if (!created) {
        LOGE("Failed to create pipeline");
        ANativeWindow_release(gst_data.native_window);
        gst_data.native_window = NULL;
        return;
    }

    // Set native window on video sink
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
            if (debug) {
                LOGD("Debug: %s", debug);
            }
            g_error_free(err);
            g_free(debug);
            gst_message_unref(msg);
        }
        gst_object_unref(err_bus);
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        gst_data.udpsrc = NULL;
        gst_data.jitterbuffer = NULL;
        gst_data.depay = NULL;
        gst_data.parser = NULL;
        gst_data.decodebin = NULL;
        gst_data.video_sink = NULL;
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

    // Elements are owned by the pipeline bin - just NULL out references
    gst_data.udpsrc = NULL;
    gst_data.jitterbuffer = NULL;
    gst_data.depay = NULL;
    gst_data.parser = NULL;
    gst_data.decodebin = NULL;
    gst_data.video_sink = NULL;

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
    if (!gst_data.pipeline || !gst_data.main_loop) {
        return;
    }

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
Java_com_v3xctrl_viewer_GstViewer_nativePausePipeline(JNIEnv *env, jclass clazz) {
    if (!gst_data.pipeline) {
        return;
    }

    LOGI("Pausing pipeline (surface lost)");

    // Detach glimagesink from the surface BEFORE pausing so its GL thread
    // stops rendering immediately, preventing "BufferQueue has been abandoned"
    // errors when Android destroys the surface.
    if (gst_data.video_sink) {
        gst_video_overlay_set_window_handle(
            GST_VIDEO_OVERLAY(gst_data.video_sink), (guintptr)0);
    }

    gst_element_set_state(gst_data.pipeline, GST_STATE_PAUSED);

    // Release the now-invalid native window
    if (gst_data.native_window) {
        ANativeWindow_release(gst_data.native_window);
        gst_data.native_window = NULL;
    }
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeResumePipeline(JNIEnv *env, jclass clazz, jobject surface) {
    if (!gst_data.pipeline || !gst_data.video_sink) {
        return;
    }

    // Acquire new native window
    gst_data.native_window = ANativeWindow_fromSurface(env, surface);
    if (!gst_data.native_window) {
        LOGE("Failed to get native window from new surface");
        return;
    }

    // Update the window handle on the video sink
    gst_video_overlay_set_window_handle(
        GST_VIDEO_OVERLAY(gst_data.video_sink),
        (guintptr)gst_data.native_window
    );

    // Resume playback
    gst_element_set_state(gst_data.pipeline, GST_STATE_PLAYING);

    // Force immediate re-render of last frame for instant video on rotation
    gst_video_overlay_expose(GST_VIDEO_OVERLAY(gst_data.video_sink));

    LOGI("Pipeline resumed with new surface");
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
