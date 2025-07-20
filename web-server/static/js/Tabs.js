class Tabs {
  constructor(container) {
    this.hash = window.location.hash;
    this.$container = $(container);
    this.$menu = this.$container.find('ul.nav');
    this.$panes = this.$container.find('.tab-pane');

    this.registerTabHandler();
    this.activateTabFromHash();
  }

  registerTabHandler() {
    this.$menu.find('li a').on('click', (e) => {
      e.preventDefault();

      const $target = $(e.currentTarget)
      const target = $target.attr('href');

      this.$menu.find('li').removeClass('active');
      $target.parent().addClass('active');

      this.$panes.hide();
      this.$container.find(target).show();

      history.replaceState(null, null, target);

      // Load tab content
      switch(target) {
        case '#services': {
          API.getServices().then((services) => {
            const $container = $('#services .container');
            $container.empty();

            if (services && services.length > 0) {
              const $table = $('<table />', {
                class: 'table table-striped',
              });
              const $tableHead = $('<thead><tr><th>Service</th><th>Type</th><th>Status</th><th></th><th></th></tr></thead>');
              const $tbody = $('<tbody />');

              $table.append($tableHead);
              $table.append($tbody);
              $container.append($table);

              services.forEach((service) => {
                var $row = $('<tr />', {
                  'data-name': service.name,
                });

                let stateLabel = 'Failed';
                let success = false;

                switch(service.type) {
                  case 'oneshot': {
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
                  } break;

                  case 'forking': {
                    stateLabel  = "Failed";
                    if(
                      service.result === 'success' &&
                      service.state === 'active'
                    ) {
                      success = true;
                      stateLabel = "Active";
                    }
                  } break;

                  case 'simple': {
                    stateLabel  = "Inactive";
                    if(
                      service.result === 'success' &&
                      service.state === 'active'
                    ) {
                      success = true;
                      stateLabel = "Active";
                    }
                  } break;
                }

                const statusClass = success ? 'text-success' : 'text-danger';
                const $line = $('<p />', {'data-name': service.name})
                $line.append(`<strong>${service.name} (${service.type})</strong>: <span class="${statusClass}">${service.state}</span>`)

                $row.append(`<td><strong>${service.name}</strong></td>`);
                $row.append(`<td>${service.type}</td>`);
                $row.append(`<td><span class="${statusClass}">${stateLabel}</span></td>`);

                const $button = $('<td />');
                $row.append($button);

                if(
                  service.type === 'simple' ||
                  service.type === 'forking'
                ) {
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

                $tbody.append($row);
              });

              const getName = function(e) {
                e.preventDefault();

                const $target = $(e.currentTarget);
                const name = $target.closest('tr').data('name');

                return name;
              }

              $('button.service-start').on('click', (e) => {
                const name = getName(e);
                API.startService(name).then(() => {
                  this.$menu.find(`a[href="#services"]`).click();
                });
              });

              $('button.service-stop').on('click', (e) => {
                const name = getName(e);
                API.stopService(name).then(() => {
                  this.$menu.find(`a[href="#services"]`).click();
                });
              });

              $('button.service-restart').on('click', (e) => {
                const name = getName(e);
                API.restartService(name).then(() => {
                  this.$menu.find(`a[href="#services"]`).click();
                });
              });

              $('button.service-log').on('click', (e) => {
                const name = getName(e);
                API.getServiceLog(name).then((log) => {
                  const $log = $("#service-log")
                  $log.val(log);
                  $log.removeClass("hidden");
                });
              });
            } else {
              $container.text('No service info available.');
            }

          });
        } break;

        case '#dmesg': {
          API.getDmesg().then((log) => {
            this.$panes.filter('#dmesg').find('textarea').val(log);
          });
        } break;

        case '#modem': {
          Tabs.renderModemInfo();
        } break;

        case '#calibration': {
          API.getServices().then((services) => {
            services.forEach((service) => {
              if(service.name === 'v3xctrl-control') {
                if(!service.active_state) {
                  $('.service-warning').addClass('hidden');
                  $('.calibration-content').removeClass('hidden');
                }
              }
            });
          });
        } break;

        default: {
          console.warn(`No handler for tab ${target}`);
        }
      }
    });

    window.addEventListener("hashchange", () => {
      this.hash = window.location.hash;
      this.activateTabFromHash();
    });
  }

  static async renderModemInfo() {
    const info = await API.getModemInfo();

    const $table = $("<table />", {
      class: "table"
    });

    const $tbody = $("<tbody />");
    $table.append($tbody);

    var $row = $("<tr />");
    $row.append(`<td>Version</td>`);
    $row.append(`<td>${info["version"]}</td>`);
    $tbody.append($row);

    $row = $("<tr />");
    $row.append(`<td>SIM Status</td>`);
    $row.append(`<td>${info["status"]}</td>`);
    $tbody.append($row);

    $row = $("<tr />");
    $row.append(`<td>Allowed Bands</td>`);
    $row.append(`<td>${info["allowedBands"].join(", ")}</td>`);
    $tbody.append($row);

    $row = $("<tr />");
    $row.append(`<td>Active Band</td>`);
    $row.append(`<td>${info["activeBand"]}</td>`);
    $tbody.append($row);

    $row = $("<tr />");
    $row.append(`<td>Carrier</td>`);
    $row.append(`<td>${info["carrier"]}</td>`);
    $tbody.append($row);

    for(var i = 0; i < info["contexts"].length; i += 1) {
      var current = info["contexts"][i];

      $row = $("<tr />");
      $row.append(`<td>Context ${current.id}</td>`);
      $row.append(`<td>${current.type}: ${current.value} (${current.apn})</td>`);
      $tbody.append($row);
    }

    $("#modem p").html($table);
  }

  activateTabFromHash() {
    let $tabLink = this.$menu.find(`a[href="${this.hash}"]`);
    if($tabLink.length == 0) {
      $tabLink = this.$menu.find('a').first();
    }

    $tabLink.click();
  }
}