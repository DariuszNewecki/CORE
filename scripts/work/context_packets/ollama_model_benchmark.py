import time
import json
import requests

# REMOTE SERVER
OLLAMA_BASE = "http://192.168.20.100:11434"

# UPDATED: Using exact names from your curl output
MODELS = [
    "qwen2.5-coder:1.5b-instruct-q8_0",
    "qwen2.5-coder:3b-instruct-q4_k_m"
]

TEST_CODE = """
def reconfigure_log_level(level: str) -> bool:
    try:
        configure_root_logger(level=level)
        getLogger(__name__).info("Log level reconfigured to %s", level.upper())
        return True
    except ValueError:
        return False
"""

PROMPT = f"Analyze this Python code and provide a one-sentence description: {TEST_CODE}"

def run_test(model_name):
    print(f"\n--- Testing: {model_name} ---")
    url = f"{OLLAMA_BASE}/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "format": "json"
    }

    try:
        start = time.perf_counter()
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        duration = time.perf_counter() - start

        data = response.json()
        eval_count = data.get("eval_count", 0)
        # Calculate Tokens Per Second (TPS)
        tps = eval_count / (data.get("eval_duration", 1) / 1e9)

        print(f"✅ Success: {tps:.2f} tokens/sec (Total time: {duration:.2f}s)")
        return tps
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0

if __name__ == "__main__":
    results = {}
    for model in MODELS:
        results[model] = run_test(model)

    print("\n" + "="*40)
    print("GTX 1050 2GB HARDWARE ANALYSIS")
    print("="*40)

    m1_speed = results.get(MODELS[0], 0)
    m2_speed = results.get(MODELS[1], 0)

    if m2_speed > 0 and m2_speed < 10:
        print(f"RESULT: 3B is too slow ({m2_speed:.1f} tps).")
        print(f"VERDICT: Use {MODELS[0]}. It is optimized for your 2GB VRAM.")
    elif m2_speed >= 10:
        print(f"RESULT: 3B is performing well ({m2_speed:.1f} tps).")
        print(f"VERDICT: Use {MODELS[1]} for better quality descriptions.")
    else:
        print("Run failed. Ensure server is reachable.")
