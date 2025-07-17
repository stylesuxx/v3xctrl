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
      getModemInfo();
    }
  });
};

const activateTabFromHash = () => {
  const hash = window.location.hash;
  const $tabLink = $(`#custom-tabs a[href="${hash}"]`);

  if ($tabLink.length && $(hash).length) {
    $('#custom-tabs li').removeClass('active');
    $('.tab-pane').removeClass('active').hide();

    $tabLink.parent().addClass('active');
    $(hash).addClass('active').show();
  } else {
    $('#custom-tabs a').first().trigger('click');
  }
};