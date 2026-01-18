/**
 * File for miscellaneous helper functions
 */

function setCalibrationValues(editor) {
  editor.editor.on('ready', () => {
    const editorValues = editor.getValue();

    const steeringMin = editorValues.control.steering.min;
    const steeringMax = editorValues.control.steering.max;
    const steeringTrim = editorValues.control.steering.trim;

    const throttleMin = editorValues.control.throttle.min;
    const throttleMax = editorValues.control.throttle.max;
    const throttleIdle = editorValues.control.throttle.idle;

    $('input.steering-min').val(steeringMin);
    $('input.steering-max').val(steeringMax);
    $('input.steering-trim').val(steeringTrim);

    $('input.throttle-min').val(throttleMin);
    $('input.throttle-max').val(throttleMax);
    $('input.throttle-idle').val(throttleIdle);
  });
};
