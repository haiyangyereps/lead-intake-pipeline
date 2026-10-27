"""Legacy entry path; use the dedicated application documented in README."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import main
if __name__ == "__main__": main()
