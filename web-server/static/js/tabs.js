const registerTabHandler = () => {
  $('#custom-tabs a').on('click', function(e) {
    e.preventDefault();

    const target = $(this).attr('href');

    $('#custom-tabs li').removeClass('active');
    $(this).parent().addClass('active');

    $('.tab-pane').hide();
    $(target).show();

    history.replaceState(null, null, target);

    // Load service status if needed
    if ($(this).attr('href') === '#services-tab') {
      checkServices();
    }

    if ($(this).attr('href') === '#dmesg-tab') {
      getDmesg();
    }

    if ($(this).attr('href') === '#modem-tab') {
      getAllowedBands();
    }
  });
};

const activateTabFromHash = () => {
  const hash = window.location.hash;
  if (hash && $(hash).length && $(`#custom-tabs a[href="${hash}"]`).length) {
    $(`#custom-tabs a[href="${hash}"]`).trigger('click');
  } else {
    $('#custom-tabs a').first().trigger('click');
  }
};