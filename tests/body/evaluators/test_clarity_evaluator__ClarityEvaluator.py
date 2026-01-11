"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/clarity_evaluator.py
- Symbol: ClarityEvaluator
- Status: 8 tests passed, some failed
- Passing tests: test_clarity_evaluator_equal_complexity, test_clarity_evaluator_worse_complexity, test_clarity_evaluator_zero_original_complexity, test_clarity_evaluator_empty_code, test_clarity_evaluator_syntax_error, test_clarity_evaluator_with_classes, test_clarity_evaluator_phase_property, test_clarity_evaluator_component_id
- Generated: 2026-01-11 03:24:27
"""

import pytest
import time
from body.evaluators.clarity_evaluator import ClarityEvaluator
from body.evaluators.clarity_evaluator import ComponentResult, ComponentPhase

@pytest.mark.asyncio
async def test_clarity_evaluator_equal_complexity():
    """Test when new code has same complexity as original."""
    evaluator = ClarityEvaluator()
    original_code = '\ndef func(a, b):\n    if a > b:\n        return a\n    else:\n        return b\n'
    new_code = '\ndef func(x, y):\n    if x > y:\n        return x\n    else:\n        return y\n'
    result = await evaluator.execute(original_code=original_code, new_code=new_code)
    assert result.ok == True
    assert result.data['original_cc'] == result.data['new_cc']
    assert result.data['is_better'] == True
    assert result.data['improvement_ratio'] == 0

@pytest.mark.asyncio
async def test_clarity_evaluator_worse_complexity():
    """Test when new code has higher complexity than original."""
    evaluator = ClarityEvaluator()
    original_code = '\ndef simple(x):\n    return x * 2\n'
    new_code = '\ndef complex(x):\n    if x > 0:\n        if x < 10:\n            return x * 2\n        else:\n            if x < 20:\n                return x * 3\n            else:\n                return x * 4\n    else:\n        return 0\n'
    result = await evaluator.execute(original_code=original_code, new_code=new_code)
    assert result.ok == True
    assert result.data['new_cc'] > result.data['original_cc']
    assert result.data['is_better'] == False
    assert result.data['improvement_ratio'] < 0

@pytest.mark.asyncio
async def test_clarity_evaluator_zero_original_complexity():
    """Test when original code has zero complexity (no branches)."""
    evaluator = ClarityEvaluator()
    original_code = '\ndef simple():\n    return 42\n'
    new_code = '\ndef still_simple():\n    return 42\n'
    result = await evaluator.execute(original_code=original_code, new_code=new_code)
    assert result.ok == True
    assert result.data['original_cc'] == 1
    assert result.data['improvement_ratio'] == 0

@pytest.mark.asyncio
async def test_clarity_evaluator_empty_code():
    """Test with empty code strings."""
    evaluator = ClarityEvaluator()
    result = await evaluator.execute(original_code='', new_code='')
    assert result.ok == True
    assert result.data['original_cc'] == 0
    assert result.data['new_cc'] == 0
    assert result.data['improvement_ratio'] == 0
    assert result.data['is_better'] == True

@pytest.mark.asyncio
async def test_clarity_evaluator_syntax_error():
    """Test when new code has syntax errors that break Radon."""
    evaluator = ClarityEvaluator()
    original_code = '\ndef valid():\n    return True\n'
    new_code = '\ndef invalid(\n    # Missing closing parenthesis and colon\n'
    result = await evaluator.execute(original_code=original_code, new_code=new_code)
    assert result.ok == False
    assert 'Radon analysis failed' in result.data['error']
    assert result.confidence == 0.0

@pytest.mark.asyncio
async def test_clarity_evaluator_with_classes():
    """Test with code containing classes and methods."""
    evaluator = ClarityEvaluator()
    original_code = '\nclass Calculator:\n    def add(self, a, b):\n        return a + b\n    \n    def complex_calc(self, x):\n        if x > 0:\n            if x < 100:\n                return x * 2\n            else:\n                return x * 3\n        return 0\n'
    new_code = '\nclass Calculator:\n    def add(self, a, b):\n        return a + b\n    \n    def complex_calc(self, x):\n        if x <= 0:\n            return 0\n        elif x < 100:\n            return x * 2\n        else:\n            return x * 3\n'
    result = await evaluator.execute(original_code=original_code, new_code=new_code)
    assert result.ok == True
    assert result.data['original_cc'] == result.data['new_cc']
    assert result.data['is_better'] == True

@pytest.mark.asyncio
async def test_clarity_evaluator_phase_property():
    """Test that the phase property returns correct value."""
    evaluator = ClarityEvaluator()
    assert evaluator.phase == ComponentPhase.AUDIT

@pytest.mark.asyncio
async def test_clarity_evaluator_component_id():
    """Test that component_id is accessible."""
    evaluator = ClarityEvaluator()
    result = await evaluator.execute(original_code='def f(): pass', new_code='def g(): pass')
    assert hasattr(result, 'component_id')
    assert result.component_id == evaluator.component_id
