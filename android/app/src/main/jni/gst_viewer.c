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
#include <gst/gl/gl.h>

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
    GstElement *decode_queue;
    GstElement *decodebin;     // NULL when using direct pipeline
    GstElement *h264parse;     // NULL when using decodebin pipeline
    GstElement *decoder;       // NULL when using decodebin pipeline
    GstElement *glupload;      // NULL when using decodebin pipeline
    GstElement *render_queue;
    GstElement *video_sink;
    GMainLoop *main_loop;
    ANativeWindow *native_window;
    gboolean initialized;
    gint video_port;
    pthread_t thread;
    gboolean thread_active;
    gboolean using_direct_pipeline;
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
static volatile gint count_queue_in = 0;

// Stats logging toggle (controlled from Java via JNI)
static volatile gboolean stats_enabled = FALSE;

// Probe IDs for diagnostic probes (0 = not attached)
static gulong probe_id_udpsrc = 0;
static gulong probe_id_jitterbuffer = 0;
static gulong probe_id_depay = 0;
static gulong probe_id_decoder = 0;
static guint stats_timer_id = 0;

// Decoder name discovered by decodebin (e.g. "amcviddec-omxgaborchardovideodecoderavc")
static gchar decoder_name[128] = "";

// Decoder output format discovered during caps negotiation (e.g. "NV12 (memory:AndroidHardwareBuffer)")
static gchar decoder_output_format[256] = "";

// GL API version (e.g. "gles2", "gles3", "opengl3")
static gchar gl_api[64] = "";

// Configurable render queue size (set from Java before pipeline creation)
static gint render_queue_size = 1;

// Sink frame interval tracking (microseconds)
#define FRAME_INTERVAL_WINDOW 60
static volatile gint64 sink_frame_interval_avg_us = 0;
static volatile gint64 sink_frame_interval_min_us = 0;
static volatile gint64 sink_frame_interval_max_us = 0;
static gint64 sink_last_frame_time_us = 0;
static gint64 frame_intervals[FRAME_INTERVAL_WINDOW];
static gint frame_interval_index = 0;
static gint frame_interval_count = 0;

// Jitter buffer stats
static volatile gint64 jbuf_num_pushed = 0;
static volatile gint64 jbuf_num_lost = 0;
static volatile gint64 jbuf_num_late = 0;
static volatile gint64 jbuf_num_duplicates = 0;

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

    // Track frame interval timing
    gint64 now = g_get_monotonic_time();
    if (sink_last_frame_time_us > 0) {
        gint64 interval = now - sink_last_frame_time_us;
        frame_intervals[frame_interval_index] = interval;
        frame_interval_index = (frame_interval_index + 1) % FRAME_INTERVAL_WINDOW;
        if (frame_interval_count < FRAME_INTERVAL_WINDOW) {
            frame_interval_count++;
        }

        // Compute min/max/avg over the window
        gint64 sum = 0;
        gint64 min_val = G_MAXINT64;
        gint64 max_val = 0;
        for (gint i = 0; i < frame_interval_count; i++) {
            gint64 v = frame_intervals[i];
            sum += v;
            if (v < min_val) {
                min_val = v;
            }
            if (v > max_val) {
                max_val = v;
            }
        }
        sink_frame_interval_avg_us = sum / frame_interval_count;
        sink_frame_interval_min_us = min_val;
        sink_frame_interval_max_us = max_val;
    }
    sink_last_frame_time_us = now;

    return GST_PAD_PROBE_OK;
}

static GstPadProbeReturn count_queue_in_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    count_queue_in++;
    return GST_PAD_PROBE_OK;
}

static void query_jitterbuffer_stats(void) {
    if (!gst_data.jitterbuffer) {
        return;
    }

    GstStructure *stats = NULL;
    g_object_get(gst_data.jitterbuffer, "stats", &stats, NULL);
    if (stats) {
        guint64 pushed = 0, lost = 0, late = 0, duplicates = 0;
        gst_structure_get_uint64(stats, "num-pushed", &pushed);
        gst_structure_get_uint64(stats, "num-lost", &lost);
        gst_structure_get_uint64(stats, "num-late", &late);
        gst_structure_get_uint64(stats, "num-duplicates", &duplicates);
        jbuf_num_pushed = (gint64)pushed;
        jbuf_num_lost = (gint64)lost;
        jbuf_num_late = (gint64)late;
        jbuf_num_duplicates = (gint64)duplicates;
        gst_structure_free(stats);
    }
}

// Periodic stats logging - shows buffer counts per element to identify where data stops
static gboolean log_stats_cb(gpointer user_data) {
    if (!gst_data.pipeline) {
        return G_SOURCE_REMOVE;
    }

    LOGI("Pipeline stats: udpsrc=%d jbuf=%d depay=%d dec=%d sink=%d",
         count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink);

    LOGI("Sink frame interval: avg=%" G_GINT64_FORMAT "us min=%" G_GINT64_FORMAT
         "us max=%" G_GINT64_FORMAT "us",
         sink_frame_interval_avg_us, sink_frame_interval_min_us, sink_frame_interval_max_us);

    query_jitterbuffer_stats();
    LOGI("Jitter buffer: pushed=%" G_GINT64_FORMAT " lost=%" G_GINT64_FORMAT
         " late=%" G_GINT64_FORMAT " duplicates=%" G_GINT64_FORMAT,
         jbuf_num_pushed, jbuf_num_lost, jbuf_num_late, jbuf_num_duplicates);

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

    // Reset all counters together so stats are consistent
    count_udpsrc = 0;
    count_jitterbuffer = 0;
    count_depay = 0;
    count_decoder = 0;
    count_sink = 0;
    count_queue_in = 0;

    probe_id_udpsrc = add_element_src_probe(gst_data.udpsrc, count_udpsrc_cb);
    probe_id_jitterbuffer = add_element_src_probe(gst_data.jitterbuffer, count_jitterbuffer_cb);
    probe_id_depay = add_element_src_probe(gst_data.depay, count_depay_cb);

    // Attach decoder probe: direct pipeline uses decoder element, decodebin uses dynamic pad
    if (gst_data.using_direct_pipeline && gst_data.decoder && !probe_id_decoder) {
        probe_id_decoder = add_element_src_probe(gst_data.decoder, count_decoder_cb);
    } else if (gst_data.decodebin && !probe_id_decoder) {
        GstPad *src_pad = gst_element_get_static_pad(gst_data.decodebin, "src_0");
        if (src_pad) {
            probe_id_decoder = gst_pad_add_probe(src_pad,
                GST_PAD_PROBE_TYPE_BUFFER, count_decoder_cb, NULL, NULL);
            gst_object_unref(src_pad);
        }
    }

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
        if (probe_id_decoder) {
            if (gst_data.using_direct_pipeline && gst_data.decoder) {
                remove_element_src_probe(gst_data.decoder, probe_id_decoder);
            } else if (gst_data.decodebin) {
                GstPad *src_pad = gst_element_get_static_pad(gst_data.decodebin, "src_0");
                if (src_pad) {
                    gst_pad_remove_probe(src_pad, probe_id_decoder);
                    gst_object_unref(src_pad);
                }
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
                const gchar *factory_name = gst_plugin_feature_get_name(
                    GST_PLUGIN_FEATURE(factory));
                const gchar *klass = gst_element_factory_get_metadata(factory,
                    GST_ELEMENT_METADATA_KLASS);
                LOGI("decodebin element: %s (factory=%s, klass=%s)",
                     GST_OBJECT_NAME(element), factory_name, klass ? klass : "");
                if (klass && g_strrstr(klass, "Decoder")) {
                    g_snprintf(decoder_name, sizeof(decoder_name), "%s (decodebin)", factory_name);
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

static void capture_decoder_output_format(GstCaps *caps) {
    GstStructure *structure = gst_caps_get_structure(caps, 0);
    const gchar *format = gst_structure_get_string(structure, "format");
    GstCapsFeatures *features = gst_caps_get_features(caps, 0);
    if (format) {
        if (features && !gst_caps_features_is_any(features)) {
            gchar *features_str = gst_caps_features_to_string(features);
            g_snprintf(decoder_output_format, sizeof(decoder_output_format),
                       "%s (%s)", format, features_str);
            g_free(features_str);
        } else {
            g_strlcpy(decoder_output_format, format, sizeof(decoder_output_format));
        }
        LOGI("Decoder output format: %s", decoder_output_format);
    }
}

static void log_sink_input_caps(void) {
    GstPad *render_queue_src = gst_element_get_static_pad(gst_data.render_queue, "src");
    if (render_queue_src) {
        GstCaps *sink_caps = gst_pad_get_current_caps(render_queue_src);
        if (sink_caps) {
            gchar *sink_caps_str = gst_caps_to_string(sink_caps);
            LOGI("render_queue -> glimagesink caps: %s", sink_caps_str);
            g_free(sink_caps_str);
            gst_caps_unref(sink_caps);
        } else {
            LOGI("render_queue -> glimagesink caps: not yet negotiated");
        }
        gst_object_unref(render_queue_src);
    }
}

static void on_decodebin_pad_added(GstElement *decodebin, GstPad *new_pad, gpointer user_data) {
    GstPad *render_queue_sink = gst_element_get_static_pad(gst_data.render_queue, "sink");

    if (gst_pad_is_linked(render_queue_sink)) {
        gst_object_unref(render_queue_sink);
        return;
    }

    GstCaps *caps = gst_pad_get_current_caps(new_pad);
    if (!caps) {
        caps = gst_pad_query_caps(new_pad, NULL);
    }

    GstStructure *structure = gst_caps_get_structure(caps, 0);
    const gchar *name = gst_structure_get_name(structure);

    if (g_str_has_prefix(name, "video/")) {
        gchar *caps_str = gst_caps_to_string(caps);
        LOGI("decodebin output caps: %s", caps_str);
        g_free(caps_str);

        GstPadLinkReturn ret = gst_pad_link(new_pad, render_queue_sink);
        if (ret != GST_PAD_LINK_OK) {
            LOGE("Failed to link decodebin to render queue: %d", ret);
        } else {
            LOGI("Linked decodebin -> render_queue -> glimagesink");
        }

        log_sink_input_caps();

        // Attach decoder probe on decodebin's output pad
        if (stats_enabled) {
            probe_id_decoder = gst_pad_add_probe(new_pad,
                GST_PAD_PROBE_TYPE_BUFFER, count_decoder_cb, NULL, NULL);
        }

        log_decodebin_decoder(decodebin);
    }

    gst_caps_unref(caps);
    gst_object_unref(render_queue_sink);
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
    pthread_setname_np(pthread_self(), "GstMainLoop");

    // Raise thread priority for lower latency processing (-10 = audio/video priority)
    if (setpriority(PRIO_PROCESS, 0, -10) != 0) {
        LOGW("Failed to set GStreamer thread priority: %s", strerror(errno));
    }

    LOGI("Starting GStreamer main loop");
    g_main_loop_run(gst_data.main_loop);
    LOGI("GStreamer main loop ended");
    return NULL;
}

// One-shot probe to capture decoder output format and GL API from the sink pad on first buffer
static GstPadProbeReturn capture_format_cb(GstPad *pad, GstPadProbeInfo *info, gpointer user_data) {
    GstCaps *caps = gst_pad_get_current_caps(pad);
    if (caps) {
        gchar *caps_str = gst_caps_to_string(caps);
        LOGI("Sink input caps: %s", caps_str);
        g_free(caps_str);
        capture_decoder_output_format(caps);
        gst_caps_unref(caps);
    }

    // Query GL API from the sink's GL context
    if (gst_data.video_sink) {
        GstGLContext *context = NULL;
        g_object_get(gst_data.video_sink, "context", &context, NULL);
        if (context) {
            GstGLAPI api = gst_gl_context_get_gl_api(context);
            gchar *api_str = gst_gl_api_to_string(api);
            gint major = 0, minor = 0;
            gst_gl_context_get_gl_version(context, &major, &minor);
            LOGI("GL API: %s %d.%d", api_str, major, minor);
            g_snprintf(gl_api, sizeof(gl_api), "%s %d.%d", api_str, major, minor);
            g_free(api_str);
            gst_object_unref(context);
        }
    }

    return GST_PAD_PROBE_REMOVE;
}

/**
 * Find an H.264 hardware video decoder in the GStreamer element registry.
 * Returns a newly created element or NULL if none found.
 */
static GstElement *find_h264_hw_decoder(void) {
    GList *factories = gst_element_factory_list_get_elements(
        GST_ELEMENT_FACTORY_TYPE_DECODER | GST_ELEMENT_FACTORY_TYPE_MEDIA_VIDEO,
        GST_RANK_MARGINAL);

    GstElement *decoder = NULL;

    for (GList *l = factories; l != NULL; l = l->next) {
        GstElementFactory *factory = (GstElementFactory *)l->data;
        const gchar *klass = gst_element_factory_get_metadata(factory,
            GST_ELEMENT_METADATA_KLASS);
        const gchar *factory_name = gst_plugin_feature_get_name(
            GST_PLUGIN_FEATURE(factory));

        // Only consider hardware decoders from the androidmedia plugin
        if (!klass || !g_strrstr(klass, "Hardware")) {
            continue;
        }

        // Check if this factory can handle H.264
        const GList *templates = gst_element_factory_get_static_pad_templates(factory);
        gboolean handles_h264 = FALSE;
        for (const GList *t = templates; t != NULL; t = t->next) {
            GstStaticPadTemplate *tmpl = (GstStaticPadTemplate *)t->data;
            if (tmpl->direction != GST_PAD_SINK) {
                continue;
            }
            GstCaps *tmpl_caps = gst_static_caps_get(&tmpl->static_caps);
            if (tmpl_caps) {
                for (guint i = 0; i < gst_caps_get_size(tmpl_caps); i++) {
                    GstStructure *s = gst_caps_get_structure(tmpl_caps, i);
                    if (g_str_equal(gst_structure_get_name(s), "video/x-h264")) {
                        handles_h264 = TRUE;
                        break;
                    }
                }
                gst_caps_unref(tmpl_caps);
            }
            if (handles_h264) {
                break;
            }
        }

        if (!handles_h264) {
            continue;
        }

        LOGI("Found H.264 HW decoder: %s (klass=%s)", factory_name, klass);
        decoder = gst_element_factory_create(factory, "hwdec");
        if (decoder) {
            g_snprintf(decoder_name, sizeof(decoder_name), "%s (direct)", factory_name);
            break;
        }
    }

    gst_plugin_feature_list_free(factories);
    return decoder;
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

static void configure_common_elements(gint port) {
    // Configure udpsrc
    GstCaps *caps = gst_caps_from_string(
        "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000");
    g_object_set(gst_data.udpsrc, "port", port, "caps", caps, NULL);
    gst_caps_unref(caps);

    // Configure jitterbuffer for packet reordering only (no dropping)
    g_object_set(gst_data.jitterbuffer, "latency", 20, NULL);

    // Configure video sink for low latency (no clock sync)
    g_object_set(gst_data.video_sink, "sync", FALSE, NULL);

    // Configure decode queue as backpressure indicator (non-leaky)
    g_object_set(gst_data.decode_queue, "max-size-buffers", 3,
                 "max-size-bytes", 0, "max-size-time", (guint64)0, NULL);

    // Configure render queue to prevent buffer buildup after decoder (leaky)
    g_object_set(gst_data.render_queue, "max-size-buffers", (guint)render_queue_size,
                 "leaky", 2 /* downstream */, NULL);
    LOGI("Render queue size: %d", render_queue_size);
}

/**
 * Direct pipeline bypassing decodebin:
 *   udpsrc -> jitterbuffer -> depay -> decode_queue -> h264parse -> [HW decoder]
 *     -> glupload -> render_queue -> glimagesink
 *
 * Bypasses decodebin's auto-negotiation overhead. The glupload element still
 * converts NV12->RGBA during texture upload, but this avoids the extra elements
 * and thread scheduling that decodebin introduces.
 */
static gboolean create_direct_rtp_pipeline(gint port) {
    GstElement *hw_decoder = find_h264_hw_decoder();
    if (!hw_decoder) {
        LOGI("No H.264 HW decoder found, cannot create direct pipeline");
        return FALSE;
    }

    gst_data.pipeline = gst_pipeline_new("viewer-pipeline");
    gst_data.udpsrc = gst_element_factory_make("udpsrc", "src");
    gst_data.jitterbuffer = gst_element_factory_make("rtpjitterbuffer", "jbuf");
    gst_data.depay = gst_element_factory_make("rtph264depay", "depay");
    gst_data.decode_queue = gst_element_factory_make("queue", "decode_queue");
    gst_data.h264parse = gst_element_factory_make("h264parse", "parser");
    gst_data.decoder = hw_decoder;
    gst_data.glupload = gst_element_factory_make("glupload", "upload");
    gst_data.render_queue = gst_element_factory_make("queue", "render_queue");
    gst_data.video_sink = gst_element_factory_make("glimagesink", "videosink");

    if (!gst_data.pipeline || !gst_data.udpsrc || !gst_data.jitterbuffer ||
        !gst_data.depay || !gst_data.decode_queue || !gst_data.h264parse ||
        !gst_data.decoder || !gst_data.glupload ||
        !gst_data.render_queue || !gst_data.video_sink) {
        LOGE("Failed to create one or more direct pipeline elements");
        if (gst_data.pipeline) {
            gst_object_unref(gst_data.pipeline);
            gst_data.pipeline = NULL;
        }
        return FALSE;
    }

    configure_common_elements(port);

    gst_bin_add_many(GST_BIN(gst_data.pipeline),
        gst_data.udpsrc, gst_data.jitterbuffer, gst_data.depay,
        gst_data.decode_queue, gst_data.h264parse, gst_data.decoder,
        gst_data.glupload, gst_data.render_queue, gst_data.video_sink, NULL);

    if (!gst_element_link_many(gst_data.udpsrc, gst_data.jitterbuffer,
                                gst_data.depay, gst_data.decode_queue,
                                gst_data.h264parse, gst_data.decoder,
                                gst_data.glupload, gst_data.render_queue,
                                gst_data.video_sink, NULL)) {
        LOGE("Failed to link direct pipeline elements");
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        return FALSE;
    }

    gst_data.using_direct_pipeline = TRUE;
    gst_data.decodebin = NULL;

    LOGI("Pipeline (direct): udpsrc port=%d ! rtpjitterbuffer ! rtph264depay ! "
         "decode_queue ! h264parse ! %s ! glupload ! render_queue ! glimagesink",
         port, decoder_name);
    return TRUE;
}

/**
 * Decodebin pipeline (fallback):
 *   udpsrc -> jitterbuffer -> depay -> decode_queue -> decodebin
 *     -> render_queue -> glimagesink
 */
static gboolean create_decodebin_rtp_pipeline(gint port) {
    gst_data.pipeline = gst_pipeline_new("viewer-pipeline");
    gst_data.udpsrc = gst_element_factory_make("udpsrc", "src");
    gst_data.jitterbuffer = gst_element_factory_make("rtpjitterbuffer", "jbuf");
    gst_data.depay = gst_element_factory_make("rtph264depay", "depay");
    gst_data.decode_queue = gst_element_factory_make("queue", "decode_queue");
    gst_data.decodebin = gst_element_factory_make("decodebin", "dec");
    gst_data.render_queue = gst_element_factory_make("queue", "render_queue");
    gst_data.video_sink = gst_element_factory_make("glimagesink", "videosink");

    if (!gst_data.pipeline || !gst_data.udpsrc || !gst_data.jitterbuffer ||
        !gst_data.depay || !gst_data.decode_queue ||
        !gst_data.decodebin || !gst_data.render_queue || !gst_data.video_sink) {
        LOGE("Failed to create one or more decodebin pipeline elements");
        if (gst_data.pipeline) {
            gst_object_unref(gst_data.pipeline);
            gst_data.pipeline = NULL;
        }
        return FALSE;
    }

    configure_common_elements(port);

    gst_bin_add_many(GST_BIN(gst_data.pipeline),
        gst_data.udpsrc, gst_data.jitterbuffer, gst_data.depay,
        gst_data.decode_queue, gst_data.decodebin,
        gst_data.render_queue, gst_data.video_sink, NULL);

    if (!gst_element_link_many(gst_data.udpsrc, gst_data.jitterbuffer,
                                gst_data.depay, gst_data.decode_queue,
                                gst_data.decodebin, NULL)) {
        LOGE("Failed to link decodebin pipeline elements");
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        return FALSE;
    }

    if (!gst_element_link(gst_data.render_queue, gst_data.video_sink)) {
        LOGE("Failed to link render queue to video sink");
        gst_object_unref(gst_data.pipeline);
        gst_data.pipeline = NULL;
        return FALSE;
    }

    g_signal_connect(gst_data.decodebin, "pad-added",
        G_CALLBACK(on_decodebin_pad_added), NULL);

    gst_data.using_direct_pipeline = FALSE;

    LOGI("Pipeline (decodebin): udpsrc port=%d ! rtpjitterbuffer ! rtph264depay ! "
         "decode_queue ! decodebin ! render_queue ! glimagesink", port);
    return TRUE;
}

static gboolean create_rtp_pipeline(gint port) {
    // Try direct pipeline first (bypasses decodebin's NV12->RGBA conversion)
    if (create_direct_rtp_pipeline(port)) {
        return TRUE;
    }

    LOGI("Falling back to decodebin pipeline");
    return create_decodebin_rtp_pipeline(port);
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeInit(JNIEnv *env, jclass clazz) {
    if (gst_data.initialized) {
        LOGI("GStreamer already initialized");
        return;
    }

    LOGI("Initializing GStreamer");

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

    // Sink and queue probes always attached (used by FPS counter and drop detection)
    count_sink = 0;
    count_queue_in = 0;
    if (gst_data.video_sink) {
        GstPad *sink_pad = gst_element_get_static_pad(gst_data.video_sink, "sink");
        if (sink_pad) {
            gst_pad_add_probe(sink_pad, GST_PAD_PROBE_TYPE_BUFFER, count_sink_cb, NULL, NULL);
            gst_object_unref(sink_pad);
        }
    }
    if (gst_data.render_queue) {
        GstPad *render_queue_sink = gst_element_get_static_pad(gst_data.render_queue, "sink");
        if (render_queue_sink) {
            gst_pad_add_probe(render_queue_sink, GST_PAD_PROBE_TYPE_BUFFER, count_queue_in_cb, NULL, NULL);
            gst_object_unref(render_queue_sink);
        }
    }

    // Capture decoder output format on first buffer reaching the sink.
    // For decodebin pipelines this is also done in on_decodebin_pad_added,
    // but this probe captures the final format after all conversions.
    if (gst_data.video_sink) {
        GstPad *sink_input = gst_element_get_static_pad(gst_data.video_sink, "sink");
        if (sink_input) {
            gst_pad_add_probe(sink_input, GST_PAD_PROBE_TYPE_BUFFER,
                capture_format_cb, NULL, NULL);
            gst_object_unref(sink_input);
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
        gst_data.decode_queue = NULL;
        gst_data.decodebin = NULL;
        gst_data.h264parse = NULL;
        gst_data.decoder = NULL;
        gst_data.glupload = NULL;
        gst_data.render_queue = NULL;
        gst_data.video_sink = NULL;
        gst_data.using_direct_pipeline = FALSE;
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
    gst_data.decode_queue = NULL;
    gst_data.decodebin = NULL;
    gst_data.h264parse = NULL;
    gst_data.decoder = NULL;
    gst_data.glupload = NULL;
    gst_data.render_queue = NULL;
    gst_data.video_sink = NULL;
    gst_data.using_direct_pipeline = FALSE;

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

    // Reset frame interval tracking
    sink_last_frame_time_us = 0;
    sink_frame_interval_avg_us = 0;
    sink_frame_interval_min_us = 0;
    sink_frame_interval_max_us = 0;
    frame_interval_index = 0;
    frame_interval_count = 0;

    // Reset jitter buffer stats
    jbuf_num_pushed = 0;
    jbuf_num_lost = 0;
    jbuf_num_late = 0;
    jbuf_num_duplicates = 0;

    // Reset decoder output format and GL API
    decoder_output_format[0] = '\0';
    gl_api[0] = '\0';

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
    gint dropped = count_queue_in - count_sink;
    if (dropped < 0) {
        dropped = 0;
    }
    g_snprintf(buf, sizeof(buf), "%d|%d|%d|%d|%d|%d",
               count_udpsrc, count_jitterbuffer, count_depay, count_decoder, count_sink, dropped);
    return (*env)->NewStringUTF(env, buf);
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetDecoderName(JNIEnv *env, jclass clazz) {
    return (*env)->NewStringUTF(env, decoder_name);
}

JNIEXPORT jint JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetDecodeQueueLevel(JNIEnv *env, jclass clazz) {
    if (!gst_data.decode_queue) {
        return 0;
    }
    guint level = 0;
    g_object_get(gst_data.decode_queue, "current-level-buffers", &level, NULL);
    return (jint)level;
}

JNIEXPORT jint JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetRenderQueueLevel(JNIEnv *env, jclass clazz) {
    if (!gst_data.render_queue) {
        return 0;
    }
    guint level = 0;
    g_object_get(gst_data.render_queue, "current-level-buffers", &level, NULL);
    return (jint)level;
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetFrameIntervalStats(JNIEnv *env, jclass clazz) {
    gchar buf[128];
    g_snprintf(buf, sizeof(buf), "%" G_GINT64_FORMAT "|%" G_GINT64_FORMAT "|%" G_GINT64_FORMAT,
               sink_frame_interval_avg_us, sink_frame_interval_min_us, sink_frame_interval_max_us);
    return (*env)->NewStringUTF(env, buf);
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetJitterBufferStats(JNIEnv *env, jclass clazz) {
    query_jitterbuffer_stats();
    gchar buf[128];
    g_snprintf(buf, sizeof(buf), "%" G_GINT64_FORMAT "|%" G_GINT64_FORMAT "|%" G_GINT64_FORMAT "|%" G_GINT64_FORMAT,
               jbuf_num_pushed, jbuf_num_lost, jbuf_num_late, jbuf_num_duplicates);
    return (*env)->NewStringUTF(env, buf);
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetDecoderOutputFormat(JNIEnv *env, jclass clazz) {
    return (*env)->NewStringUTF(env, decoder_output_format);
}

JNIEXPORT jstring JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetGlApi(JNIEnv *env, jclass clazz) {
    return (*env)->NewStringUTF(env, gl_api);
}

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeSetRenderQueueSize(JNIEnv *env, jclass clazz, jint size) {
    render_queue_size = size;
    LOGI("Render queue size set to %d", size);
}

JNIEXPORT jint JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeGetRenderQueueSize(JNIEnv *env, jclass clazz) {
    return render_queue_size;
}
