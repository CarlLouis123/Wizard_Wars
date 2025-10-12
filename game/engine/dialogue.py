\
# Make project root importable when running game/main.py directly
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import gemini_config as CFG

from game.config import gemini_config as CFG
class DialogueEngine:
    def __init__(self,use_gemini=False,model_name="gemini-2.5-pro"):
        self.use_gemini=use_gemini; self.model_name=model_name
    def npc_line(self, npc_prompt: str) -> str:
        npc_prompt=(npc_prompt or "Say hi.").strip()
        if not self.use_gemini: return self._local(npc_prompt)
        key=CFG.get_api_key()
        if not key: return "[Gemini] Missing API key. Put it in config/api_key.txt or set GOOGLE_API_KEY. "+self._local(npc_prompt)
        try:
            url=f"{CFG.MODEL_ENDPOINT}?key={key}"
            body={"contents":[{"parts":[{"text":f"You are an NPC in a cozy top-down RPG. {npc_prompt}"}]}]}
            r=requests.post(url,json=body,timeout=10); r.raise_for_status(); data=r.json()
            cands=data.get("candidates") or []
            if cands:
                parts=cands[0].get("content",{}).get("parts",[])
                texts=[p.get("text","") for p in parts if "text" in p]
                msg=" ".join(t.strip() for t in texts if t.strip())
                return msg or self._local(npc_prompt)
            return self._local(npc_prompt)
        except Exception as e:
            return f"[Gemini error: {e}] "+self._local(npc_prompt)
    def _local(self, prompt):
        arr=["If you get lost, follow the river.","Press 'E' to talk and 'G' for clever mode.","The shopkeeper loves blue berries.","Treasure lies past the old bridge."]
        return arr[sum(ord(c) for c in prompt)%len(arr)]
