/**
 * Converts a JSONEditor schema to RJSF-compatible format.
 * Transforms enum_titles to oneOf, strips JSONEditor-specific options.
 */
export function adaptSchemaForRjsf(schema) {
  const adapted = structuredClone(schema)
  delete adapted.title // Already shown by section tabs
  walkSchema(adapted)
  return adapted
}

function walkSchema(node) {
  if (!node || typeof node !== 'object') {
    return
  }

  // Convert enum + enum_titles to oneOf
  if (node.enum && node.options?.enum_titles) {
    node.oneOf = node.enum.map((val, i) => ({
      const: val,
      title: node.options.enum_titles[i] || String(val),
    }))
    delete node.enum
    delete node.options.enum_titles
  }

  // Strip HTML from descriptions
  if (node.description && typeof node.description === 'string') {
    node.description = node.description.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
  }

  // Clean up JSONEditor-specific options
  if (node.options) {
    delete node.options.disable_collapse
    delete node.options.disable_edit_json
    delete node.options.disable_properties
    delete node.options.collapsed
    delete node.options.enum_titles
    if (Object.keys(node.options).length === 0) {
      delete node.options
    }
  }
  delete node.propertyOrder

  // Convert per-property "required": true to standard JSON Schema required array, and recurse
  if (node.properties) {
    const requiredFields = []
    for (const [key, prop] of Object.entries(node.properties)) {
      if (prop.required === true) {
        requiredFields.push(key)
        delete prop.required
      }
      walkSchema(prop)
    }
    if (requiredFields.length > 0) {
      node.required = requiredFields
    }
  }
  if (node.items) {
    walkSchema(node.items)
  }
}

/**
 * Builds a RJSF uiSchema from the original JSONEditor schema.
 * Extracts propertyOrder into ui:order and format:checkbox into ui:widget.
 */
export function buildUiSchema(schema) {
  if (!schema || schema.type !== 'object') {
    return {}
  }

  const uiSchema = {}
  const properties = schema.properties || {}

  // Build ui:order from propertyOrder
  const ordered = Object.entries(properties)
    .filter(([, prop]) => prop.propertyOrder != null)
    .sort(([, a], [, b]) => a.propertyOrder - b.propertyOrder)
    .map(([key]) => key)

  if (ordered.length > 0) {
    uiSchema['ui:order'] = [...ordered, '*']
  }

  for (const [key, prop] of Object.entries(properties)) {
    uiSchema[key] = {}

    // Handle format: "checkbox" -> checkbox widget
    if (prop.format === 'checkbox' && prop.type === 'boolean') {
      uiSchema[key]['ui:widget'] = 'checkbox'
    }

    // Handle collapsed sections
    if (prop.options?.collapsed) {
      uiSchema[key]['ui:options'] = {
        ...uiSchema[key]['ui:options'],
        collapsed: true,
      }
    }

    // Recurse into nested objects
    if (prop.type === 'object') {
      const nested = buildUiSchema(prop)
      Object.assign(uiSchema[key], nested)
    }

    // Clean up empty ui schema entries
    if (Object.keys(uiSchema[key]).length === 0) {
      delete uiSchema[key]
    }
  }

  return uiSchema
}
