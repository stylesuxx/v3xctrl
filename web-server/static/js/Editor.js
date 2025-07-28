class Editor {
  constructor(selector, schema, startval, modems) {
    this.modems = modems;
    this.initialized = false;
    this.previousModel = startval?.network?.modem?.model || null;

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
      theme: 'bootstrap3',
      show_errors: "change",
      disable_edit_json: true,
      disable_properties: true
    });

    this.editor.on('ready', () => {
      this.registerClickHandlers();

      this.initialized = true;
    });

    this.editor.on('change', () => {
      const that = this;

      const modelEditor = this.editor.getEditor('root.network.modem.model');
      const bandsEditor = this.editor.getEditor('root.network.modem.allowedBands');
      const currentModel = modelEditor.getValue();

      const $container = $(bandsEditor.container);
      const $selects = $container.find('select');

      const validBands = this.modems[currentModel]?.validBands || this.modems.generic.validBands;

      // Disable bands not supported on the current model
      $selects.each(function () {
        const $select = $(this);

        $select.find('option').each(function () {
          const $option = $(this);
          const val = parseInt($option.val(), 10);
          const isValid = validBands.includes(val);
          $option.prop('disabled', !isValid);
        });
      });

      if (
        !modelEditor ||
        !bandsEditor ||
        currentModel === this.previousModel
      ) {
        return;
      }

      // Select all valid bands for newly selected model
      this.previousModel = currentModel;
      $selects.each(function () {
        const $select = $(this);
        const selectedValues = [];

        $select.find('option').each(function () {
          const $option = $(this);
          const val = parseInt($option.val(), 10);
          const isValid = validBands.includes(val);
          $option.prop('selected', isValid);

          if (isValid) {
            selectedValues.push(val);
          }
        });

        const values = that.getValue();
        values.network.modem.allowedBands = selectedValues;
        that.setValue(values);
      });
    });
  }

  getValue() {
    return this.editor.getValue();
  }

  setValue(values) {
    this.editor.setValue(values);
  }

  validate() {
    return this.editor.validate();
  }

  save() {
    const updatedData = this.getValue();
    const errors = this.validate();

    if (errors.length === 0) {
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