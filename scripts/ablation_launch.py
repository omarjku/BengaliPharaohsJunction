"""Start a LOCAL backend for the Gemini on/off ablation. Usage: python scripts/ablation_launch.py 8801 --gemini on
                                                                python scripts/ablation_launch.py 8802 --gemini off
Nothing real is touched: fresh temporary DATA_DIR, dummy front-door keys, no reload. This script never reads a key.

--gemini off sets GEMINI_API_KEY to the EMPTY STRING in this process before the app is imported. Why not PowerShell
`$env:GEMINI_API_KEY=''`: PowerShell deletes a variable set to '', the variable is then absent, and backend/app/config.py
(load_dotenv, override=False) re-reads the real key from the repo-root .env. An existing empty value is kept by dotenv.
--gemini on leaves the environment alone: the app uses your own key from your own environment or .env.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMMY_AGENT_KEY = "ablation-agent-key"  # local dummy, only valid for this throwaway backend


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("port", type=int)
    ap.add_argument("--gemini", choices=["on", "off"], default="on")
    a = ap.parse_args()
    if a.gemini == "off":
        os.environ["GEMINI_API_KEY"] = ""  # empty string, set before config.py runs load_dotenv
    data_dir = tempfile.mkdtemp(prefix=f"ablation-{a.gemini}-")
    os.environ["DATA_DIR"] = data_dir
    os.environ["AGENT_KEYS"] = f"{DUMMY_AGENT_KEY}=lapland-kitchen"
    os.environ["APPROVER_KEYS"] = "ablation-approver-key=lapland-kitchen"
    paths = [str(ROOT / d) for d in ("contracts", "compiler", "profile", "decision")]
    os.environ["PYTHONPATH"] = os.pathsep.join(paths + [os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    sys.path[:0] = paths + [str(ROOT / "backend")]
    os.chdir(ROOT / "backend")
    import uvicorn  # imported after the environment is set
    print(f"ablation backend: gemini={a.gemini}, port={a.port}, DATA_DIR={data_dir}", flush=True)
    print("check: GET /api/health -> gemini_key_configured should be " + str(a.gemini == "on").lower(), flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
