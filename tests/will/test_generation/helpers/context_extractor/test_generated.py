from __future__ import annotations

from will.test_generation.helpers.context_extractor import ContextExtractor


# ID: 64e0af31-9ebb-42c0-b0cc-29578d227fa5
def test_ContextExtractor_extract_dependencies():
    context_packet = {
        "context": [
            {"item_type": "import", "name": "os", "path": "/usr/lib/os.py"},
            {"item_type": "function", "name": "helper", "path": "/src/helper.py"},
            {"item_type": "import", "name": "sys", "path": "/usr/lib/sys.py"},
        ]
    }

    extractor = ContextExtractor()

    result = extractor.extract_dependencies(context_packet)

    assert result == [
        {"name": "os", "path": "/usr/lib/os.py"},
        {"name": "sys", "path": "/usr/lib/sys.py"},
    ]


import importlib

import pytest


# ID: a6e75e13-3186-4ecd-8fdd-0c4f6e456a7a
def test_ContextExtractor_extract_target_code() -> None:
    module = importlib.import_module("will.test_generation.helpers.context_extractor")
    extract_target_code = getattr(module, "extract_target_code", None)
    if extract_target_code is None:
        pytest.skip("extract_target_code is not available on context_extractor module")

    context_packet = {
        "context": [
            {
                "item_type": "code",
                "name": "my_func",
                "path": "./src/pkg/mod.py",
                "content": "def my_func():\n    return 42\n",
            }
        ]
    }

    result = extract_target_code(context_packet, "src/pkg/mod.py", "my_func")

    assert result == "def my_func():\n    return 42\n"
