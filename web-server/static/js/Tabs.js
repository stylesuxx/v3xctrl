class Tabs {
  constructor(container, editor) {
    this.hash = window.location.hash;

    this.container = container;
    this.editor = editor;

    this.$container = $(this.container);
    this.$menu = this.$container.find('ul.nav');
    this.$panes = this.$container.find('.tab-pane');

    this.tabs = {
      "calibration": this.$panes.filter('#calibration'),
      "dmesg": this.$panes.filter('#dmesg'),
      "editor": this.$panes.filter('#editor'),
      "modem": this.$panes.filter('#modem'),
      "services": this.$panes.filter('#services'),
      "version": this.$panes.filter('#version'),
    };

    this.registerTabHandler();
    this.activateTabFromHash();
  }

  registerTabHandler() {
    const that = this;

    this.$menu.find('li a').on('click', (e) => {
      e.preventDefault();

      const $target = $(e.currentTarget)
      const target = $target.attr('href');

      that.$menu.find('li').removeClass('active');
      $target.parent().addClass('active');

      that.$panes.hide();
      that.$container.find(target).show();

      history.replaceState(null, null, target);

      // Render tab content
      switch(target) {
        case '#services': {
          that.renderServices();
        } break;

        case '#dmesg': {
          that.renderDmesg();
        } break;

        case '#modem': {
          that.renderModemInfo();
        } break;

        case '#calibration': {
          that.renderCalibration();
        } break;

        case '#version': {
          that.renderVersionInfo();
        } break;

        default: {
          console.warn(`No handler for tab ${target}`);
        }
      }
    });

    window.addEventListener("hashchange", () => {
      that.hash = window.location.hash;
      that.activateTabFromHash();
    });

    /**
     * Click handlers for static UI elements, related to the tabs
     */

    // Modem
    this.tabs.modem.find('button.reset').on('click', (e) => {
      const modal = new Modal('Resetting modem', '<p>This will take a couple seconds...</p>');
      modal.show();

      API.resetModem()
        .then(() => {
          that.renderModemInfo()
            .catch(() => {
              console.warn('Failed to fetch modem info.');
            })
            .finally(() => {
              modal.remove();
            });
        });
    });

    // dmesg
    this.tabs.dmesg.find('button.refresh').on('click', (e) => {
      that.renderDmesg();
    });

    // calibration
    this.tabs.calibration.find('button.save-steering-calibration').on('click', (e) => {
      e.preventDefault();

      const $calibration = that.tabs.calibration;
      const min = parseInt($calibration.find('.steering.min input').val());
      const max = parseInt($calibration.find('.steering.max input').val());
      const trim = parseInt($calibration.find('.steering.trim input').val());

      const values = that.editor.getValue();
      values.controls.steering.min = min;
      values.controls.steering.max = max;
      values.controls.steering.trim = trim;

      that.editor.setValue(values);
      that.editor.save();
    });

    this.tabs.calibration.find('button.save-throttle-calibration').on('click', (e) => {
      e.preventDefault();

      const $calibration = that.tabs.calibration;
      const min = parseInt($calibration.find('.throttle.min input').val());
      const max = parseInt($calibration.find('.throttle.max input').val());
      const idle = parseInt($calibration.find('.throttle.idle input').val());

      const values = that.editor.getValue();
      values.controls.throttle.min = min;
      values.controls.throttle.max = max;
      values.controls.throttle.idle = idle;

      that.editor.setValue(values);
      that.editor.save();
    });

    this.tabs.calibration.find('form.steering button').on('click', (e) => {
      e.preventDefault();

      const $this = $(e.target);
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

      const values = that.editor.getValue();
      const channel = parseInt(values.controls.pwm.steering);
      API.setPwm(channel, value);
    });

    this.tabs.calibration.find('form.throttle button').on('click', (e) => {
      e.preventDefault();

      const $this = $(e.target);
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

      const values = that.editor.getValue();
      const channel = parseInt(values.controls.pwm.throttle);
      API.setPwm(channel, value);
    });
  }

  async renderServices() {
    API.getServices().then((services) => {
      const $container = this.tabs.services.find('.container');
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
  }

  async renderDmesg() {
    const $content = this.tabs.dmesg;

    const log = await API.getDmesg();
    $content.find('textarea').val(log);
  }

  async renderCalibration() {
    const $warning = this.tabs.calibration.find('.service-warning');
    const $content = this.tabs.calibration.find('.calibration-content');

    const services = await API.getServices();
    services.forEach((service) => {
      if(service.name === 'v3xctrl-control') {
        if(service.state == 'inactive') {
          $warning.addClass('hidden');
          $content.removeClass('hidden');
        } else {
          $warning.removeClass('hidden');
          $content.addClass('hidden');
        }
      }
    });
  }

  async renderModemInfo() {
    const info = await API.getModemInfo();
    const $content = this.tabs.modem.find('p');

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

    for(var i = 0; i < info["addresses"].length; i += 1) {
      var current = info["addresses"][i];

      $row = $("<tr />");
      $row.append(`<td>Address ${current.id}</td>`);
      $row.append(`<td>${current.ip}</td>`);
      $tbody.append($row);
    }

    $("#modem p").html($table);
  }

  async renderVersionInfo() {
    const info = await API.getVersionInfo();
    const $content = this.tabs.version.find('p');

    const $table = $("<table />", {
      class: "table"
    });

    const $thead = $("<thead />");
    let $row = $("<tr />");
    $row.append("<th>Package</th>");
    $row.append("<th>Version</th>");
    $thead.append($row);
    $table.append($thead);

    const $tbody = $("<tbody />");
    $table.append($tbody);

    const keys = Object.keys(info);
    for(var i = 0; i < keys.length; i += 1) {
      const name = keys[i];
      const version = info[name];

      $row = $("<tr />");
      $row.append(`<td>${name}</td>`);
      $row.append(`<td>${version}</td>`);
      $tbody.append($row);
    }

    $content.html($table);
  }

  activateTabFromHash() {
    let $tabLink = this.$menu.find(`a[href="${this.hash}"]`);
    if($tabLink.length == 0) {
      $tabLink = this.$menu.find('a').first();
    }

    $tabLink.click();
  }
}