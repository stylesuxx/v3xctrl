import json
import jsonschema
from pathlib import Path


def validate_os_list(schema_path, json_path):
    """Validate an OS list JSON file against the schema."""
    # Load schema
    with open(schema_path) as f:
        schema = json.load(f)

    # Load OS list
    with open(json_path) as f:
        os_list = json.load(f)

    # Validate
    try:
        jsonschema.validate(instance=os_list, schema=schema)
        print(f"✓ {json_path} is valid")
        return True
    except jsonschema.exceptions.ValidationError as e:
        print(f"✗ Validation error in {json_path}:")
        print(f"  Path: {'.'.join(str(p) for p in e.path)}")
        print(f"  Error: {e.message}")
        return False
    except jsonschema.exceptions.SchemaError as e:
        print(f"✗ Schema error: {e.message}")
        return False


# Usage
if __name__ == "__main__":
    validate_os_list(
        "./schema.json",
        "./v3xctrl_repo.json"
    )
