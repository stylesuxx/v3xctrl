#include <jni.h>
#include <stdlib.h>
#include <android/log.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <gst/gst.h>
#include <gst/video/videooverlay.h>

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
        // RTP H264 receiver pipeline with software decoder
        pipeline_str = g_strdup_printf(
            "udpsrc port=%d caps=\"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000\" ! "
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

JNIEXPORT void JNICALL
Java_com_v3xctrl_viewer_GstViewer_nativeFinalize(JNIEnv *env, jclass clazz) {
    Java_com_v3xctrl_viewer_GstViewer_nativeStopPipeline(env, clazz);
    gst_data.initialized = FALSE;
    LOGI("GStreamer finalized");
}
