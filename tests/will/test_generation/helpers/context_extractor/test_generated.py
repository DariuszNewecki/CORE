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




# ID: 616fe35e-9ec5-45e0-89b2-484571c4253c
def test_ContextExtractor():
    context_packet = {
        "context": [
            {"item_type": "import", "name": "Path", "path": "pathlib"},
            {
                "item_type": "code",
                "name": "target_symbol",
                "path": "src/mod/thing.py",
                "content": "def target_symbol():\n    return 42\n",
            },
            {
                "item_type": "symbol",
                "name": "similar_symbol",
                "path": "src/mod/other.py",
                "content": "def similar_symbol():\n    return 99\n",
                "similarity": 0.95,
                "summary": "A similar symbol.",
            },
            {
                "item_type": "symbol",
                "name": "low_similarity_symbol",
                "path": "src/mod/other.py",
                "content": "def low_similarity_symbol():\n    return 1\n",
                "similarity": 0.2,
                "summary": "Not similar enough.",
            },
        ]
    }

    target_code = ContextExtractor.extract_target_code(
        context_packet, "./src/mod/thing.py", "target_symbol"
    )
    assert target_code == "def target_symbol():\n    return 42\n"

    fallback_code = ContextExtractor.extract_target_code(
        context_packet, "src/mod/thing.py", "nonexistent_symbol"
    )
    assert fallback_code == "def target_symbol():\n    return 42\n"

    missing_code = ContextExtractor.extract_target_code(
        context_packet, "src/other.py", "target_symbol"
    )
    assert missing_code == ""

    dependencies = ContextExtractor.extract_dependencies(context_packet)
    assert dependencies == [{"name": "Path", "path": "pathlib"}]

    similar_symbols = ContextExtractor.extract_similar_symbols(context_packet)
    assert len(similar_symbols) == 1
    assert similar_symbols[0]["name"] == "similar_symbol"
    assert similar_symbols[0]["code"] == "def similar_symbol():\n    return 99\n"
    assert similar_symbols[0]["summary"] == "A similar symbol."
