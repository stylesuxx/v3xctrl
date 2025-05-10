const registerTabHandler = () => {
  $('#custom-tabs a').on('click', function(e) {
    e.preventDefault();

    $('#custom-tabs li').removeClass('active');
    $(this).parent().addClass('active');

    $('.tab-pane').hide();
    $($(this).attr('href')).show();

    // Load service status if needed
    if ($(this).attr('href') === '#services-tab') {
      $.get('/services', function(data) {
        const container = $('#service_status_container');
        container.empty();

        if (data.services && data.services.length > 0) {
          data.services.forEach(service => {
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
  });
};