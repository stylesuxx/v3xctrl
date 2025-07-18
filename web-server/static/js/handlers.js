/**
 * Click handlers for static UI elements
 */

const registerClickHandlers = (editor) => {
  $('a.reboot').on('click', function(e) {
    e.preventDefault();
    $(this).prop('disabled', true);

    const countdown = 45;

    const html = `
      <p><strong>Rebooting...</strong></p>
      <p><span class="modal-countdown">${countdown}</span> seconds</p>
    `;

    const modal = new Modal(
      'Rebooting',
      html,
      countdown,
      () => location.reload()
    );
    modal.show();

    try {
      API.reboot();
    } catch(err) {
      console.warn(err);
    }
  });

  $('a.shutdown').on('click', function(e) {
    e.preventDefault();
    $(this).prop('disabled', true);

    const countdown = 30;

    const html = `
      <p><strong>Shutting down...</strong></p>
      <p><span class="modal-countdown">${countdown}</span> seconds</p>
    `;

    const modal = new Modal('Shutting down', html, countdown, () => {
      modal.update('Shutdown complete', '<p><strong>It is safe to turn off now.</strong></p>');
    });

    try {
      API.shutdown();
    } catch(err) {
      console.warn(err);
    }
  });

  $('button.save-steering-calibration').on('click', function(e) {
    const $calibration = $('#calibration');
    const min = parseInt($calibration.find('.steering.min input').val());
    const max = parseInt($calibration.find('.steering.max input').val());
    const trim = parseInt($calibration.find('.steering.trim input').val());

    const values = editor.getValue();
    values.controls.steering.min = min;
    values.controls.steering.max = max;
    values.controls.steering.trim = trim;

    editor.setValue(values);
    editor.save();
  });

  $('button.save-throttle-calibration').on('click', function(e) {
    const $calibration = $('#calibration');
    const min = parseInt($calibration.find('.throttle.min input').val());
    const max = parseInt($calibration.find('.throttle.max input').val());
    const idle = parseInt($calibration.find('.throttle.idle input').val());

    const values = editor.getValue();
    values.controls.throttle.min = min;
    values.controls.throttle.max = max;
    values.controls.throttle.idle = idle;

    editor.setValue(values);
    editor.save();
  });

  $('form.steering button').on('click', function(e) {
    e.preventDefault();

    const $this = $(this);
    const $form = $this.closest('form');
    const $input = $form.find('input');
    let value = parseInt($input.val());

    if($this.hasClass('increase')) {
      value += 10;
    }

    if($this.hasClass('decrease')) {
      value -= 10;
    }
    $input.val(value);

    if($form.hasClass('trim')) {
      const min = parseInt($('.steering.min input').val());
      const max = parseInt($('.steering.max input').val());

      const base = min + ((max - min) / 2);
      value = base + value;
    }

    const values = editor.getValue();
    const gpio = parseInt(values.controls.gpio.steering);
    API.setPwm(gpio, value);
  });

  $('form.throttle button').on('click', function(e) {
    e.preventDefault();

    const $this = $(this);
    const $form = $this.closest('form');
    const $input = $form.find('input');
    let value = parseInt($input.val());

    if($this.hasClass('increase')) {
      value += 10;
    }

    if($this.hasClass('decrease')) {
      value -= 10;
    }
    $input.val(value);

    const values = editor.getValue();
    const gpio = parseInt(values.controls.gpio.throttle);
    API.setPwm(gpio, value);
  });

  $('button.dmesg-refresh').on('click', function(e) {
    getDmesg();
  });
};