class Editor {
  constructor(selector, schema, startval) {
    this.$container = $(selector);
    this.$editor = $('<div />');
    this.$saveButton = $('<button />', {
      class: 'save btn btn-primary',
      text: 'Save',
    });

    this.$container.append(this.$editor);
    this.$container.append(this.$saveButton);

    this.editor = new JSONEditor(this.$editor[0], {
      schema: schema,
      startval: startval,
      theme: 'bootstrap3'
    });

    this.registerClickHandlers();
  };

  getValue() {
    return this.editor.getValue();
  }

  setValue(values) {
    this.editor.setValue(values);
  }

  save() {
    const updatedData = this.getValue();
    const errors = this.editor.validate();

    if(errors.length === 0) {
      const modal = new Modal('Saving', '<p>Saving configuration...</p>');
      modal.show();

      API.setConfig(updatedData).then(() => {
        modal.hide();
        modal.remove();
      });
    }
  }

  registerClickHandlers() {
    this.$saveButton.on('click', () => {
      this.save();
    });
  }
}