import { describe, it, expect } from 'vitest'
import { adaptSchemaForRjsf, buildUiSchema, pruneHiddenProperties } from '@/lib/schemaUtils'

describe('adaptSchemaForRjsf', () => {
  it('converts enum + enum_titles to oneOf', () => {
    const schema = {
      type: 'string',
      enum: ['a', 'b'],
      options: { enum_titles: ['Alpha', 'Beta'] },
    }
    const adapted = adaptSchemaForRjsf(schema)
    expect(adapted.oneOf).toEqual([
      { const: 'a', title: 'Alpha' },
      { const: 'b', title: 'Beta' },
    ])
    expect(adapted.enum).toBeUndefined()
  })

  it('strips HTML from descriptions', () => {
    const schema = {
      type: 'object',
      description: 'Some <strong>bold</strong> and <i>italic</i> text',
      properties: {},
    }
    const adapted = adaptSchemaForRjsf(schema)
    expect(adapted.description).toBe('Some bold and italic text')
  })

  it('removes propertyOrder', () => {
    const schema = {
      type: 'object',
      propertyOrder: 10,
      properties: {
        a: { type: 'string', propertyOrder: 1 },
      },
    }
    const adapted = adaptSchemaForRjsf(schema)
    expect(adapted.propertyOrder).toBeUndefined()
    expect(adapted.properties.a.propertyOrder).toBeUndefined()
  })

  it('cleans up JSONEditor-specific options', () => {
    const schema = {
      type: 'object',
      options: {
        disable_collapse: true,
        disable_edit_json: true,
        disable_properties: true,
        collapsed: true,
      },
      properties: {},
    }
    const adapted = adaptSchemaForRjsf(schema)
    expect(adapted.options).toBeUndefined()
  })
})

describe('buildUiSchema', () => {
  it('builds ui:order from propertyOrder', () => {
    const schema = {
      type: 'object',
      properties: {
        b: { type: 'string', propertyOrder: 20 },
        a: { type: 'string', propertyOrder: 10 },
        c: { type: 'string', propertyOrder: 30 },
      },
    }
    const uiSchema = buildUiSchema(schema)
    expect(uiSchema['ui:order']).toEqual(['a', 'b', 'c', '*'])
  })

  it('maps format checkbox to ui:widget', () => {
    const schema = {
      type: 'object',
      properties: {
        enabled: { type: 'boolean', format: 'checkbox', propertyOrder: 1 },
      },
    }
    const uiSchema = buildUiSchema(schema)
    expect(uiSchema.enabled['ui:widget']).toBe('checkbox')
  })

  it('recurses into nested objects', () => {
    const schema = {
      type: 'object',
      properties: {
        nested: {
          type: 'object',
          propertyOrder: 1,
          properties: {
            b: { type: 'string', propertyOrder: 20 },
            a: { type: 'string', propertyOrder: 10 },
          },
        },
      },
    }
    const uiSchema = buildUiSchema(schema)
    expect(uiSchema.nested['ui:order']).toEqual(['a', 'b', '*'])
  })
})

describe('pruneHiddenProperties', () => {
  // Mirrors the real control section: the selector sits next to the mixer object, so the groups it
  // gates are one level deeper than the field deciding their visibility.
  const controlSchema = {
    type: 'object',
    properties: {
      mixerType: { type: 'string', enum: ['ackermann', 'differential'] },
      mixer: {
        type: 'object',
        properties: {
          ackermann: {
            type: 'object',
            options: { collapsed: true, showWhen: { field: 'mixerType', equals: 'ackermann' } },
            properties: { steering: { type: 'object' } },
          },
          differential: {
            type: 'object',
            options: { collapsed: true, showWhen: { field: 'mixerType', equals: 'differential' } },
            properties: { motor: { type: 'object' } },
          },
        },
      },
    },
  }

  it('keeps the matching branch and drops the other', () => {
    const pruned = pruneHiddenProperties(controlSchema, { mixerType: 'differential' })

    expect(Object.keys(pruned.properties.mixer.properties)).toEqual(['differential'])
  })

  it('resolves the condition field against the section data, not the holding object', () => {
    const pruned = pruneHiddenProperties(controlSchema, { mixerType: 'ackermann' })

    expect(Object.keys(pruned.properties.mixer.properties)).toEqual(['ackermann'])
  })

  it('resolves a dotted condition field path', () => {
    const schema = {
      type: 'object',
      properties: {
        modem: {
          type: 'object',
          options: { showWhen: { field: 'routing.mode', equals: 'modem' } },
          properties: { model: { type: 'string' } },
        },
      },
    }

    expect(pruneHiddenProperties(schema, { routing: { mode: 'wlan' } }).properties).toEqual({})
    expect(pruneHiddenProperties(schema, { routing: { mode: 'modem' } })).toBe(schema)
  })

  it('returns the identical reference when no property declares showWhen', () => {
    const schema = {
      type: 'object',
      properties: {
        routing: { type: 'string' },
        modem: { type: 'object', properties: { model: { type: 'string' } } },
      },
    }

    expect(pruneHiddenProperties(schema, { routing: 'wlan' })).toBe(schema)
  })

  it('does not mutate the input schema', () => {
    pruneHiddenProperties(controlSchema, { mixerType: 'ackermann' })

    expect(Object.keys(controlSchema.properties.mixer.properties)).toEqual(['ackermann', 'differential'])
  })

  it('keeps untouched subtrees by reference', () => {
    const pruned = pruneHiddenProperties(controlSchema, { mixerType: 'ackermann' })

    expect(pruned.properties.mixer.properties.ackermann).toBe(controlSchema.properties.mixer.properties.ackermann)
  })

  it('drops a conditional property when section data is missing', () => {
    const pruned = pruneHiddenProperties(controlSchema, undefined)

    expect(Object.keys(pruned.properties.mixer.properties)).toEqual([])
  })

  it('passes through schemas without properties', () => {
    const schema = { type: 'string' }

    expect(pruneHiddenProperties(schema, 'value')).toBe(schema)
  })
})
