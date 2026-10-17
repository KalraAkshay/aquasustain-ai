from pathlib import Path
from dotenv import load_dotenv
# Local non-secret configuration. Cloud Run environment variables take precedence.
load_dotenv(Path(__file__).resolve().parents[1]/'.env.local', override=False)
