/**
 * File for miscellaneous helper functions
 */

function setCalibrationValues(editor) {
  editor.editor.on('ready', () => {
    const editorValues = editor.getValue();

    const steeringMin = editorValues.controls.steering.min;
    const steeringMax = editorValues.controls.steering.max;
    const steeringTrim = editorValues.controls.steering.trim;

    const throttleMin = editorValues.controls.throttle.min;
    const throttleMax = editorValues.controls.throttle.max;
    const throttleIdle = editorValues.controls.throttle.idle;

    $('input.steering-min').val(steeringMin);
    $('input.steering-max').val(steeringMax);
    $('input.steering-trim').val(steeringTrim);

    $('input.throttle-min').val(throttleMin);
    $('input.throttle-max').val(throttleMax);
    $('input.throttle-idle').val(throttleIdle);
  });
};
