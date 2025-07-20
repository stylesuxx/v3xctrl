/**
 * Click handlers for static UI elements (not directly related to the tabs)
 */

const registerClickHandlers = () => {
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
    modal.show();

    try {
      API.shutdown();
    } catch(err) {
      console.warn(err);
    }
  });
};
