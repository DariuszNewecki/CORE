def sanitize_input(text: str, max_len: int = 100) -> str:
    """Sanitizes input text to ensure safe processing.
    
    Args:
        text: Raw input string to be sanitized
        max_len: Maximum allowed length (default: 100)
    
    Returns:
        str: Sanitized string with controlled length
    """
    return text.strip()[:max_len]