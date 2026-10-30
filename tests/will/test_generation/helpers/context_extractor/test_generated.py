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
