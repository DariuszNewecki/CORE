from __future__ import annotations


# ID: 745d539e-89f5-48c9-abe0-19c8a7b1dd08
def test_NormalizedOutput():
    from will.test_generation.llm_output import NormalizedOutput

    output = NormalizedOutput(code="print('hi')", method="fenced_block")

    assert output.code == "print('hi')"
    assert output.method == "fenced_block"
