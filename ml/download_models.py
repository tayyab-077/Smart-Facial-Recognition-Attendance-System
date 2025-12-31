import os
import requests

MODELS = {
    "arcface.onnx": "https://huggingface.co/tayyab-077/attendance-system-vision/resolve/main/arcface.onnx",
    "scrfd_2.5g_bnkps.onnx": "https://huggingface.co/tayyab-077/attendance-system-vision/resolve/main/scrfd_2.5g_bnkps.onnx"
}

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

def download_if_missing():
    for name, url in MODELS.items():
        path = os.path.join(MODEL_DIR, name)

        if os.path.exists(path) and os.path.getsize(path) > 5_000_000:
            print(f"✅ {name} already exists")
            continue

        print(f"⬇️ Downloading {name}...")
        r = requests.get(url, stream=True, timeout=300)
        r.raise_for_status()

        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"✅ Downloaded {name}")
