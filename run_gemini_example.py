\
import requests, json
from config.gemini_config import MODEL_ENDPOINT, get_api_key
key=get_api_key()
if not key: raise SystemExit("Set GOOGLE_API_KEY or put your key in config/api_key.txt")
url=f"{MODEL_ENDPOINT}?key={key}"
body={"contents":[{"parts":[{"text":"You are an NPC sage. Give one short tip."}]}]}
r=requests.post(url,json=body,timeout=10); print(r.status_code); print(r.text[:500])
