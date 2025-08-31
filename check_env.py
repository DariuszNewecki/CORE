import os
from dotenv import load_dotenv

print("--- Running Environment Variable Check ---")

# This line is important, it forces the .env file to be loaded
load_dotenv() 

# These are the exact variable names the program is looking for
keys_to_check = [
    "DEEPSEEK_CODER_API_URL",
    "DEEPSEEK_CODER_API_KEY",
    "DEEPSEEK_CODER_MODEL_NAME",
    "ANTHROPIC_CLAUDE_SONNET_API_KEY", # Let's check this one too
]

found_all = True
for key in keys_to_check:
    value = os.getenv(key)
    if value:
        # We only print the first 4 and last 4 characters to confirm it's loaded, keeping your key secret.
        print(f"✅ Found {key}: {value[:4]}...{value[-4:]}")
    else:
        print(f"❌ MISSING: {key}")
        found_all = False
        
print("----------------------------------------")

if not found_all:
    print("\n[Error] At least one variable was not found.")
    print("Please check your .env file for typos in the variable names shown as MISSING above.")
else:
    print("\n[Success] All checked variables were found by the script.")