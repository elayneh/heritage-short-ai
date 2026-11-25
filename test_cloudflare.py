
import os
import requests
import base64
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
api_token = os.environ["CLOUDFLARE_API_TOKEN"]

model = "@cf/black-forest-labs/flux-1-schnell"

url = (
    f"https://api.cloudflare.com/client/v4/"
    f"accounts/{account_id}/ai/run/{model}"
)

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json"
}

payload = {
    "prompt": (
        "A beautiful Ethiopian highland village "
        "at sunrise, cinematic lighting, "
        "warm colors, traditional houses"
    ),
    "steps": 4
}

start = time.perf_counter()

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=120
)

response.raise_for_status()

data = response.json()
image = base64.b64decode(data["result"]["image"])

Path("outputs/images").mkdir(
    parents=True, exist_ok=True
)

output = "outputs/images/test.jpg"

with open(output, "wb") as f:
    f.write(image)

latency = time.perf_counter() - start

print(f"Image saved to: {output}")
print(f"Latency: {latency:.2f} seconds")
