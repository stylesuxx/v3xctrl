const registerTabHandler = () => {
  $('#custom-tabs a').on('click', function(e) {
    e.preventDefault();

    $('#custom-tabs li').removeClass('active');
    $(this).parent().addClass('active');

    $('.tab-pane').hide();
    $($(this).attr('href')).show();

    // Load service status if needed
    if ($(this).attr('href') === '#services-tab') {
      checkServices();
    }

    if ($(this).attr('href') === '#dmesg-tab') {
      getDmesg();
    }
  });
};