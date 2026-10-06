"""Absolute-path launcher; host cwd does not need to be the package checkout."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from guarded_agent.cli import main
raise SystemExit(main())
