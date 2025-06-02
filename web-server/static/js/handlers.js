const registerClickHandlers = (editor) => {
  $('#save').on('click', function() {
    $('#response').text("");
    const updatedData = editor.getValue();
    const errors = editor.validate();

    if(errors.length == 0) {
      $.ajax({
        url: '/save',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(updatedData),
        success: function(res) {
            $messageContainer = $('#response');
            $messageContainer.text(res.message);
            $messageContainer.stop(true, true)
              .fadeIn(200)
              .delay(2000)
              .fadeOut(600);
        }
      });
    }
  });

  $('a.reboot').on('click', function(e) {
    e.preventDefault();

    const $modal = $('#rebootModal');
    const $backdrop = $('#reboot-backdrop');
    const $countdown = $('#reboot-countdown');
    let secondsLeft = 45;

    $modal.removeClass('hidden fade').addClass('in').css({
      display: 'block',
      opacity: 1
    });
    $backdrop.removeClass('hidden fade').addClass('in').css({
      display: 'block',
      opacity: 0.5
    });
    $('body').addClass('modal-open');

    $countdown.text(secondsLeft);

    const countdownTimer = setInterval(function() {
      secondsLeft--;
      $countdown.text(secondsLeft);

      if (secondsLeft <= 0) {
        clearInterval(countdownTimer);
        location.reload();
      }
    }, 1000);

    $.post('/reboot').fail(function() {
      console.warn("Reboot POST failed — likely already rebooting.");
    });
  });

  $('button.save-steering-calibration').on('click', function(e) {
    const $calibration = $('#calibration-tab');
    const min = parseInt($calibration.find('.steering.min input').val());
    const max = parseInt($calibration.find('.steering.max input').val());
    const trim = parseInt($calibration.find('.steering.trim input').val());

    const values = editor.getValue();
    values.controls.steering.min = min;
    values.controls.steering.max = max;
    values.controls.steering.trim = trim;

    editor.setValue(values);

    $("#save").click();
  });

  $('button.save-throttle-calibration').on('click', function(e) {
    const $calibration = $('#calibration-tab');
    const min = parseInt($calibration.find('.throttle.min input').val());
    const max = parseInt($calibration.find('.throttle.max input').val());
    const idle = parseInt($calibration.find('.throttle.idle input').val());

    const values = editor.getValue();
    values.controls.throttle.min = min;
    values.controls.throttle.max = max;
    values.controls.throttle.idle = idle;

    editor.setValue(values);

    $("#save").click();
  });

  $('form.steering button').on('click', function(e) {
    e.preventDefault();

    $this = $(this);
    $form = $this.closest('form');
    $input = $form.find('input');
    value = parseInt($input.val());

    if($this.hasClass('increase')) {
      value += 10;
    }

    if($this.hasClass('decrease')) {
      value -= 10;
    }
    $input.val(value);

    if($form.hasClass('trim')) {
      min = parseInt($('.steering.min input').val());
      max = parseInt($('.steering.max input').val());

      base = min + ((max - min) / 2);
      value = base + value;
    }

    // TODO: read pin dynamically
    gpio = 13;
    setPwm(gpio, value);
  });

  $('form.throttle button').on('click', function(e) {
    e.preventDefault();

    $this = $(this);
    $form = $this.closest('form');
    $input = $form.find('input');
    value = parseInt($input.val());

    if($this.hasClass('increase')) {
      value += 10;
    }

    if($this.hasClass('decrease')) {
      value -= 10;
    }
    $input.val(value);

    // TODO: read pin dynamically
    gpio = 18;
    setPwm(gpio, value);
  });

  $('button.dmesg-refresh').on('click', function(e) {
    getDmesg();
  });
};