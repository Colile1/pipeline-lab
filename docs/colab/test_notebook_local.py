"""Run main_colab.ipynb's code cells in order, outside Colab.

Used to test the notebook before handing it over. The cells detect that
they are not in Colab (PIPELAB_LOCAL=1), skip the Drive mount and the
pip install, and read the bundle from PIPELAB_BUNDLE. Everything else,
including the engine self-test, the run, merge, comparison, analyses,
figures and packaging, runs exactly as it would on Colab.

Usage:
  PIPELAB_LOCAL=1 PIPELAB_BUNDLE=<bundle dir> PIPELAB_WORK=<work dir> \
  PIPELAB_PROFILE=smoke python test_notebook_local.py <notebook>
"""
import json
import sys
import time
import types

nb = json.load(open(sys.argv[1], encoding="utf-8"))

try:
    import IPython.display  # noqa: F401
except ImportError:          # stand-in so the figure cell can run headless
    ip = types.ModuleType("IPython")
    disp = types.ModuleType("IPython.display")
    disp.Image = lambda filename=None, width=None: f"<image {filename}>"
    disp.Markdown = lambda text: text
    disp.display = lambda obj: print("  [display]", obj)
    ip.display = disp
    sys.modules["IPython"], sys.modules["IPython.display"] = ip, disp

scope = {"__name__": "__main__"}
code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
for i, cell in enumerate(code_cells, 1):
    src = "".join(cell["source"])
    head = src.strip().splitlines()[0][:70]
    print(f"\n######## cell {i}/{len(code_cells)}: {head}", flush=True)
    t = time.time()
    exec(compile(src, f"<cell {i}>", "exec"), scope)
    print(f"######## cell {i} finished in {time.time() - t:.1f} s", flush=True)
print("\nALL CELLS RAN")
