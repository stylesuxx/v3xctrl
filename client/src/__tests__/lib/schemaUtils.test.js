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
  const mixerSchema = {
    type: 'object',
    properties: {
      type: { type: 'string', enum: ['ackermann', 'differential'] },
      ackermann: {
        type: 'object',
        options: { collapsed: true, showWhen: { field: 'type', equals: 'ackermann' } },
        properties: { steering: { type: 'object' } },
      },
      differential: {
        type: 'object',
        options: { collapsed: true, showWhen: { field: 'type', equals: 'differential' } },
        properties: { motor: { type: 'object' } },
      },
    },
  }

  it('keeps the matching branch and drops the other', () => {
    const pruned = pruneHiddenProperties(mixerSchema, { type: 'differential' })

    expect(Object.keys(pruned.properties)).toEqual(['type', 'differential'])
  })

  it('resolves the condition field against the object holding the property', () => {
    const schema = {
      type: 'object',
      properties: {
        control: {
          type: 'object',
          properties: {
            mixer: mixerSchema,
          },
        },
      },
    }
    const pruned = pruneHiddenProperties(schema, { control: { mixer: { type: 'ackermann' } } })

    expect(Object.keys(pruned.properties.control.properties.mixer.properties)).toEqual(['type', 'ackermann'])
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
    pruneHiddenProperties(mixerSchema, { type: 'ackermann' })

    expect(Object.keys(mixerSchema.properties)).toEqual(['type', 'ackermann', 'differential'])
  })

  it('keeps untouched subtrees by reference', () => {
    const pruned = pruneHiddenProperties(mixerSchema, { type: 'ackermann' })

    expect(pruned.properties.ackermann).toBe(mixerSchema.properties.ackermann)
  })

  it('drops a conditional property when form data is missing', () => {
    const pruned = pruneHiddenProperties(mixerSchema, undefined)

    expect(Object.keys(pruned.properties)).toEqual(['type'])
  })

  it('passes through schemas without properties', () => {
    const schema = { type: 'string' }

    expect(pruneHiddenProperties(schema, 'value')).toBe(schema)
  })
})
