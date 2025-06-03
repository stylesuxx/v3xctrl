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
    const $container = $('#service_status_container');
    $container.empty();

    if (data.services && data.services.length > 0) {
      var $tableWrapper = $('<table />', {
        class: 'table table-striped',
      });
      var $tableHead = $('<thead><tr><th>Service</th><th>Type</th><th>Status</th><th></th><th></th></tr></thead>');
      $tableWrapper.append($tableHead);
      var $table = $('<tbody />');

      data.services.forEach(service => {
        var $row = $('<tr />', {
          'data-name': service.name,
        });
        if(service.name === 'v3xctrl-control') {
          if(!service.active_state) {
            $('.service-warning').addClass('hidden');
            $('.calibration-content').removeClass('hidden');
          }
        }

        let stateLabel = "Failed";
        let success = false;
        if(service.type === 'oneshot') {
          if(
            service.result === 'success' &&
            ['active', 'activating'].includes(service.state)
          ) {
            success = true;

            stateLabel = "Ran";
            if(service.state == 'activating') {
              stateLabel = "Running";
            }
          }
        }

        if(service.type === 'simple') {
          stateLabel  = "Inactive";
          if(
            service.result === 'success' &&
            service.state === 'active'
          ) {
            success = true;
            stateLabel = "Active";
          }
        }

        const statusClass = success ? 'text-success' : 'text-danger';
        const $line = $('<p />', {'data-name': service.name})
        $line.append(`<strong>${service.name} (${service.type})</strong>: <span class="${statusClass}">${service.state}</span>`)

        $row.append(`<td><strong>${service.name}</strong></td>`);
        $row.append(`<td>${service.type}</td>`);
        $row.append(`<td><span class="${statusClass}">${stateLabel}</span></td>`);

        $button = $('<td />');
        $row.append($button);

        if(service.type === 'simple') {
          if(success) {
            $button.append('<button class="service-stop btn btn-primary">Stop</button>');
          } else {
            $button.append('<button class="service-start btn btn-primary">Start</button>');
          }
        }

        if(service.type === 'oneshot') {
          if(
            service.result === 'success' &&
            ['active', 'activating'].includes(service.state)
          ) {
            if(service.state == 'activating') {
              $button.append('<button class="service-stop btn btn-primary">Stop</button>');
            } else {
              $button.append('<button class="service-restart btn btn-primary">Restart</button>');
            }
          } else {
            $button.append('<button class="service-restart btn btn-primary">Restart</button>');
          }
        }

        $row.append('<td><button class="service-log btn btn-secondary">Show logs</button></td>');

        $table.append($row);
      });

      $tableWrapper.append($table);
      $container.append($tableWrapper);

      // Register click handlers for start/stop
      $('button.service-start').on('click', function(e) {
        e.preventDefault();

        var $this = $(this);
        var $row = $this.closest('tr');
        var name = $row.data('name');

        startService(name);
      });

      $('button.service-stop').on('click', function(e) {
        e.preventDefault();

        var $this = $(this);
        var $row = $this.closest('tr');
        var name = $row.data('name');

        stopService(name);
      });

      $('button.service-restart').on('click', function(e) {
        e.preventDefault();

        var $this = $(this);
        var $row = $this.closest('tr');
        var name = $row.data('name');

        restartService(name);
      });

      $('button.service-log').on('click', function(e) {
        e.preventDefault();

        var $this = $(this);
        var $row = $this.closest('tr');
        var name = $row.data('name');

        getServiceLog(name);
      });
    } else {
      $container.text('No service info available.');
    }
  });
}

function startService(name) {
  $.ajax({
    url: '/service/start',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      name: name
    }),
    success: function(res) {
      checkServices();
    }
  });
}

function stopService(name) {
  $.ajax({
    url: '/service/stop',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      name: name
    }),
    success: function(res) {
      checkServices();
    }
  });
}

function restartService(name) {
  $.ajax({
    url: '/service/restart',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      name: name
    }),
    success: function(res) {
      checkServices();
    }
  });
}

function getServiceLog(name) {
  $.ajax({
    url: '/service/log',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      name: name
    }),
    success: function(res) {
      var $log = $("#service-log")
      $log.val(res.log);
      $log.removeClass("hidden");
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

function get(path, callback) {
  $.ajax({
    method: 'GET',
    url: path,
    success: callback,
  });
}

function getDmesg() {
  get('/dmesg', function(res) {
    $("#dmesg").val(res.log);
  });
}

function getAllowedBands() {
  get('/modem/bands', function(res) {
    console.log(res);
    var bands = JSON.parse(res);
    console.log(bands);

    $("#modem-tab p").text('Allowed bands: ' + bands.join(', '));
  });
}