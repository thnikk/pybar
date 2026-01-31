#!/usr/bin/python3 -u
"""
Description: Schema system for settings validation and UI generation
Author: thnikk
"""


class FieldType:
    """Field type constants for schema definitions"""
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    BOOLEAN = 'boolean'
    CHOICE = 'choice'
    COLOR = 'color'
    FILE = 'file'
    LIST = 'list'


# Global config schema for bar-level settings
GLOBAL_SCHEMA = {
    'position': {
        'type': FieldType.CHOICE,
        'default': 'bottom',
        'label': 'Bar Position',
        'description': 'Position of the bar on screen',
        'choices': ['top', 'bottom']
    },
    'margin': {
        'type': FieldType.INTEGER,
        'default': 10,
        'label': 'Margin',
        'description': 'Margin around the bar in pixels',
        'min': 0,
        'max': 100
    },
    'spacing': {
        'type': FieldType.INTEGER,
        'default': 5,
        'label': 'Module Spacing',
        'description': 'Spacing between modules in pixels',
        'min': 0,
        'max': 50
    },
    'popover-autohide': {
        'type': FieldType.BOOLEAN,
        'default': True,
        'label': 'Popover Auto-hide',
        'description': 'Close popovers when clicking outside'
    },
    'popover-exclusive': {
        'type': FieldType.BOOLEAN,
        'default': False,
        'label': 'Exclusive Popovers',
        'description': 'Only allow one popover open at a time'
    },
    'namespace': {
        'type': FieldType.STRING,
        'default': 'pybar',
        'label': 'Window Namespace',
        'description': 'WM namespace for window rules'
    }
}


def get_field_value(config, key, schema_field):
    """Get value from config or fall back to schema default"""
    return config.get(key, schema_field.get('default'))


def validate_field(value, schema_field):
    """Validate a value against its schema field definition"""
    field_type = schema_field.get('type', FieldType.STRING)

    if value is None:
        return True  # None is allowed for optional fields

    if field_type == FieldType.STRING:
        return isinstance(value, str)

    elif field_type == FieldType.INTEGER:
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        min_val = schema_field.get('min')
        max_val = schema_field.get('max')
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    elif field_type == FieldType.FLOAT:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        min_val = schema_field.get('min')
        max_val = schema_field.get('max')
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    elif field_type == FieldType.BOOLEAN:
        return isinstance(value, bool)

    elif field_type == FieldType.CHOICE:
        choices = schema_field.get('choices', [])
        return value in choices

    elif field_type == FieldType.COLOR:
        # Basic hex color validation
        if not isinstance(value, str):
            return False
        if value.startswith('#') and len(value) in (4, 7, 9):
            return all(c in '0123456789abcdefABCDEF' for c in value[1:])
        return False

    elif field_type == FieldType.FILE:
        return isinstance(value, str)

    elif field_type == FieldType.LIST:
        return isinstance(value, list)

    return True


def validate_config_section(config, schema):
    """Validate a config section against a schema"""
    errors = []
    for key, field in schema.items():
        value = config.get(key)
        if value is not None and not validate_field(value, field):
            errors.append(f"Invalid value for '{key}': {value}")
    return errors


def get_module_schema(module_class):
    """Get schema from a module class, if defined"""
    return getattr(module_class, 'SCHEMA', {})
