function setCalibrationValues(editor) {
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
}

function checkServices() {
  $.get('/services', function(data) {
    const container = $('#service_status_container');
    container.empty();

    if (data.services && data.services.length > 0) {
      data.services.forEach(service => {
        if(service.name === 'rc-control') {
          if(!service.active) {
            $('.service-warning').addClass('hidden');
            $('.calibration-content').removeClass('hidden');
          }
        }

        const statusClass = service.active ? 'text-success' : 'text-danger';
        container.append(
          `<p><strong>${service.name} (${service.type})</strong>: <span class="${statusClass}">${service.active ? 'Active' : 'Inactive'}</span></p>`
        );
      });
    } else {
      container.text('No service info available.');
    }
  });
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