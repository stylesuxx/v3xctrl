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

function showModal(title, html, countdownSeconds = null, onDone = null) {
  const $modal = $('#genericModal');
  const $backdrop = $('#modal-backdrop');

  $('#modal-title').text(title);
  $('#modal-body').html(html);

  $modal.removeClass('hidden fade').addClass('in').css({
    display: 'block',
    opacity: 1
  });
  $backdrop.removeClass('hidden fade').addClass('in').css({
    display: 'block',
    opacity: 0.5
  });
  $('body').addClass('modal-open');

  if (countdownSeconds != null) {
    let secondsLeft = countdownSeconds;
    const $count = $('#modal-body').find('.modal-countdown');

    $count.text(secondsLeft);
    const timer = setInterval(() => {
      secondsLeft--;
      $count.text(secondsLeft);
      if (secondsLeft <= 0) {
        clearInterval(timer);
        if (onDone) {
          onDone();
        }
      }
    }, 1000);
  }
};

function hideModal() {
  $('#genericModal').addClass('hidden fade').removeClass('in').css({ display: 'none' });
  $('#modal-backdrop').addClass('hidden fade').removeClass('in').css({ display: 'none' });
  $('body').removeClass('modal-open');
};