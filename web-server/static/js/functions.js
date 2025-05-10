function setCalibrationValues(editor) {
  const editorValues = editor.getValue();

  const steeringMin = editorValues.controls.steering.min;
  const steeringMax = editorValues.controls.steering.max;
  const steeringTrim = editorValues.controls.steering.trim;

  $('input.steering-min').val(steeringMin);
  $('input.steering-max').val(steeringMax);
  $('input.steering-trim').val(steeringTrim);
}

function setPwm(gpio, value) {
  $.ajax({
    url: '/set-pwm',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      gpio,
      value
    }),
    success: function(res) {
      console.log("Done...")
    }
  });
}