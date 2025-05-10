const initEditor = (schema, startval) => {
  return new JSONEditor(document.getElementById('editor_holder'), {
    schema: schema,
    startval: startval,
    theme: 'bootstrap3'
  });
};