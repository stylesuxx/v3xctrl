class Modal {
  constructor(title, html, countdownSeconds = null, onDone = null) {
    this.countdownSeconds = countdownSeconds;
    this.onDone = onDone;

    this.$modal = $('<div />', {
      id: 'genericModal',
      class: 'modal fade hidden',
      tabindex: '-1',
      role: 'dialog',
      'aria-hidden': 'true'
    });

    const $dialog = $('<div />', {
      class: 'modal-dialog modal-sm',
      role: 'document'
    });

    const $content = $('<div />', {
      class: 'modal-content text-center',
      style: 'padding: 20px;'
    });

    this.$title = $('<h2 />', {
      id: 'modal-title',
      text: title
    });

    this.$body = $('<div />', {
      id: 'modal-body',
      html: html
    });

    $content.append(this.$title);
    $content.append(this.$body);
    $dialog.append($content);
    this.$modal.append($dialog);

    this.$backdrop = $('<div />', {
      id: 'modal-backdrop',
      class: 'modal-backdrop fade hidden'
    });

    $('body').append(this.$backdrop);
    $('body').append(this.$modal);
  }

  show() {
    this.$modal.removeClass('hidden fade').addClass('in').css({
      display: 'block',
      opacity: 1
    });

    this.$backdrop.removeClass('hidden fade').addClass('in').css({
      display: 'block',
      opacity: 0.5
    });

    $('body').addClass('modal-open');

    if(this.countdownSeconds != null) {
      let secondsLeft = this.countdownSeconds;
      const $count = this.$body.find('.modal-countdown');

      $count.text(secondsLeft);
      this._timer = setInterval(() => {
        secondsLeft--;
        $count.text(secondsLeft);
        if(secondsLeft <= 0) {
          clearInterval(this._timer);
          this._timer = null;

          if(this.onDone) {
            this.onDone();
          }
        }
      }, 1000);
    }
  }

  update(title, html) {
    this.$title.text(title);
    this.$body.html(html);
  }

  hide() {
    this.$modal.addClass('hidden fade').removeClass('in').css({ display: 'none' });
    this.$backdrop.addClass('hidden fade').removeClass('in').css({ display: 'none' });
    $('body').removeClass('modal-open');

    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  remove() {
    this.$modal.remove();
    this.$backdrop.remove();

    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }
}