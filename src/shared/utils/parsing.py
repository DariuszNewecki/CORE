# src/shared/utils/parsing.py
"""
Parsing utility functions for the CORE system.
"""
import re
from typing import Dict


def parse_write_blocks(llm_output: str) -> Dict[str, str]:
    """
    Extracts all [[write:...]] blocks from LLM output.

    This function is robust and handles both [[end]] and [[/write]] as valid terminators
    to accommodate different LLM habits.

    Args:
        llm_output (str): The raw text output from a language model.

    Returns:
        A dictionary mapping file paths to their corresponding code content.
    """

    pattern = r"\[\[write:\s*(.+?)\]\](.*?)(?:\[\[end\]\]|\[\[/write\]\])"
    matches = re.findall(pattern, llm_output, re.DOTALL)
    return {path.strip(): code.strip() for path, code in matches}


# def extract_json_from_response(text: str) -> str:
#    """
#    Extracts a JSON object or array from a raw text response.
#    Handles both markdown ```json code blocks and raw JSON strings.#
#        Args:
#        text (str): The raw text output from a language model.#
#    Returns:
#        A string containing the extracted JSON, or an empty string if not found.
#    """
#    match = re.search(r"```json\n([\s\S]*?)\n```", text, re.DOTALL)
#    if match:
#        return match.group(1).strip()
#    match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
#    if match:
#        return match.group(0).strip()
#    return ""
