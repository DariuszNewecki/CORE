"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/security_evaluator.py
- Symbol: SecurityEvaluator
- Status: 15 tests passed, some failed
- Passing tests: test_security_evaluator_initialization, test_check_secrets_api_key, test_check_secrets_password, test_check_sql_injection, test_check_insecure_deserialization, test_check_weak_crypto, test_calculate_score, test_assess_risk, test_execute_with_no_vulnerabilities, test_execute_with_vulnerabilities, test_execute_with_custom_scope, test_execute_without_code_content, test_multiple_pattern_matches, test_case_insensitive_password_check, test_severity_escalation_logic
- Generated: 2026-01-11 03:27:29
"""

import pytest
from body.evaluators.security_evaluator import SecurityEvaluator

@pytest.mark.asyncio
async def test_security_evaluator_initialization():
    """Test that SecurityEvaluator initializes correctly."""
    evaluator = SecurityEvaluator()
    assert evaluator.phase.name == 'AUDIT'
    assert hasattr(evaluator, 'component_id')
    assert evaluator.PATTERNS is not None
    assert isinstance(evaluator.PATTERNS, dict)

@pytest.mark.asyncio
async def test_check_secrets_api_key():
    """Test detection of hardcoded API keys."""
    evaluator = SecurityEvaluator()
    code_with_key = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz12345678"'
    vulnerabilities = evaluator._check_secrets(code_with_key, '/test/path.py')
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]['type'] == 'secrets_exposure'
    assert vulnerabilities[0]['severity'] == 'critical'
    assert vulnerabilities[0]['message'] == 'Hardcoded API key detected'
    assert vulnerabilities[0]['file_path'] == '/test/path.py'
    assert 'remediation' in vulnerabilities[0]

@pytest.mark.asyncio
async def test_check_secrets_password():
    """Test detection of hardcoded passwords."""
    evaluator = SecurityEvaluator()
    code_with_password = 'PASSWORD = "secret123"'
    vulnerabilities = evaluator._check_secrets(code_with_password, '/test/path.py')
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]['type'] == 'secrets_exposure'
    assert vulnerabilities[0]['severity'] == 'critical'
    assert vulnerabilities[0]['message'] == 'Hardcoded password detected'
    assert vulnerabilities[0]['file_path'] == '/test/path.py'

@pytest.mark.asyncio
async def test_check_sql_injection():
    """Test detection of SQL injection vulnerabilities."""
    evaluator = SecurityEvaluator()
    unsafe_sql = 'cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)'
    vulnerabilities = evaluator._check_sql_injection(unsafe_sql, '/test/sql.py')
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]['type'] == 'sql_injection'
    assert vulnerabilities[0]['severity'] == 'critical'
    assert vulnerabilities[0]['message'] == 'Potential SQL injection vulnerability'
    assert vulnerabilities[0]['file_path'] == '/test/sql.py'

@pytest.mark.asyncio
async def test_check_insecure_deserialization():
    """Test detection of insecure deserialization."""
    evaluator = SecurityEvaluator()
    unsafe_code = 'result = eval(user_input)'
    vulnerabilities = evaluator._check_insecure_deserialization(unsafe_code, '/test/deserialize.py')
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]['type'] == 'insecure_deserialization'
    assert vulnerabilities[0]['severity'] == 'high'
    assert 'eval' in vulnerabilities[0]['message']

@pytest.mark.asyncio
async def test_check_weak_crypto():
    """Test detection of weak cryptographic algorithms."""
    evaluator = SecurityEvaluator()
    weak_code = 'hash = hashlib.md5(data.encode()).hexdigest()'
    vulnerabilities = evaluator._check_weak_crypto(weak_code, '/test/crypto.py')
    assert len(vulnerabilities) == 1
    assert vulnerabilities[0]['type'] == 'weak_crypto'
    assert vulnerabilities[0]['severity'] == 'high'
    assert 'md5' in vulnerabilities[0]['message']

@pytest.mark.asyncio
async def test_calculate_score():
    """Test security score calculation."""
    evaluator = SecurityEvaluator()
    score = evaluator._calculate_score([])
    assert score == 1.0
    vulns = [{'severity': 'critical'}]
    score = evaluator._calculate_score(vulns)
    assert score == 0.6
    vulns = [{'severity': 'critical'}, {'severity': 'high'}, {'severity': 'medium'}]
    score = evaluator._calculate_score(vulns)
    assert score == 0.3
    vulns = [{'severity': 'critical'} for _ in range(10)]
    score = evaluator._calculate_score(vulns)
    assert score == 0.0

@pytest.mark.asyncio
async def test_assess_risk():
    """Test risk assessment."""
    evaluator = SecurityEvaluator()
    risk = evaluator._assess_risk([])
    assert risk == 'none'
    vulns = [{'severity': 'critical'}]
    risk = evaluator._assess_risk(vulns)
    assert risk == 'critical'
    vulns = [{'severity': 'high'}]
    risk = evaluator._assess_risk(vulns)
    assert risk == 'high'
    vulns = [{'severity': 'medium'}]
    risk = evaluator._assess_risk(vulns)
    assert risk == 'medium'
    vulns = [{'severity': 'low'}]
    risk = evaluator._assess_risk(vulns)
    assert risk == 'low'

@pytest.mark.asyncio
async def test_execute_with_no_vulnerabilities():
    """Test execute method with clean code."""
    evaluator = SecurityEvaluator()
    clean_code = '\ndef safe_function():\n    return "This is safe code"\n'
    result = await evaluator.execute(file_path='/test/clean.py', code_content=clean_code, check_scope=['secrets_exposure', 'sql_injection'])
    assert result.ok == True
    assert result.confidence == 1.0
    assert result.data['security_score'] == 1.0
    assert result.data['risk_level'] == 'none'
    assert len(result.data['vulnerabilities']) == 0
    assert result.next_suggested is None

@pytest.mark.asyncio
async def test_execute_with_vulnerabilities():
    """Test execute method with vulnerable code."""
    evaluator = SecurityEvaluator()
    vulnerable_code = '\napi_key = "sk-test123456789012345678901234567890"\ncursor.execute("SELECT * FROM users WHERE id = " + user_id)\n'
    result = await evaluator.execute(file_path='/test/vulnerable.py', code_content=vulnerable_code, check_scope=['secrets_exposure', 'sql_injection'])
    assert result.ok == False
    assert result.confidence < 1.0
    assert len(result.data['vulnerabilities']) >= 2
    assert result.data['risk_level'] == 'critical'
    assert result.next_suggested == 'security_remediation'

@pytest.mark.asyncio
async def test_execute_with_custom_scope():
    """Test execute method with specific check scope."""
    evaluator = SecurityEvaluator()
    code_with_secret = 'password = "secret"'
    result = await evaluator.execute(file_path='/test/scope.py', code_content=code_with_secret, check_scope=['secrets_exposure'])
    assert len(result.data['vulnerabilities']) == 1
    assert result.data['check_scope'] == ['secrets_exposure']
    result2 = await evaluator.execute(file_path='/test/scope2.py', code_content=code_with_secret, check_scope=[])
    assert len(result2.data['vulnerabilities']) == 1
    assert len(result2.data['check_scope']) > 0

@pytest.mark.asyncio
async def test_execute_without_code_content():
    """Test execute method without code content."""
    evaluator = SecurityEvaluator()
    result = await evaluator.execute(file_path='/test/empty.py')
    assert result.ok == True
    assert result.data['security_score'] == 1.0
    assert len(result.data['vulnerabilities']) == 0

@pytest.mark.asyncio
async def test_multiple_pattern_matches():
    """Test detection of multiple pattern matches in same code."""
    evaluator = SecurityEvaluator()
    code = '\nkey1 = "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\nkey2 = "ghp_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"\nPASSWORD = "test123"\n'
    vulnerabilities = evaluator._check_secrets(code, '/test/multi.py')
    assert len(vulnerabilities) >= 3
    for vuln in vulnerabilities:
        assert vuln['type'] == 'secrets_exposure'
        assert vuln['severity'] == 'critical'

@pytest.mark.asyncio
async def test_case_insensitive_password_check():
    """Test that password check is case insensitive."""
    evaluator = SecurityEvaluator()
    code1 = 'password = "secret"'
    vulns1 = evaluator._check_secrets(code1, '/test/case1.py')
    code2 = 'PASSWORD = "secret"'
    vulns2 = evaluator._check_secrets(code2, '/test/case2.py')
    code3 = 'Password = "secret"'
    vulns3 = evaluator._check_secrets(code3, '/test/case3.py')
    assert len(vulns1) == 1
    assert len(vulns2) == 1
    assert len(vulns3) == 1

@pytest.mark.asyncio
async def test_severity_escalation_logic():
    """Test that blocking vulnerabilities correctly mark result as not ok."""
    evaluator = SecurityEvaluator()
    code_medium = 'hashlib.sha1(data)'
    result = await evaluator.execute(file_path='/test/severity.py', code_content='some clean code')
    assert result.ok == True
    code_critical = 'api_key = "sk-test123456789012345678901234567890"'
    result_critical = await evaluator.execute(file_path='/test/critical.py', code_content=code_critical)
    assert result_critical.ok == False
