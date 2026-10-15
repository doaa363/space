"""
Root Stage 3 Runner
Executes src/stage3_edge_inference.py seamlessly.
"""
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import runpy

if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "stage3_edge_inference.py")
    runpy.run_path(script_path, run_name="__main__")
