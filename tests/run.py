"""Run the whole growth-loop test suite: python3 tests/run.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "growth-loop"


def bytecode_caches():
    return sorted(str(p.relative_to(PLUGIN_ROOT))
                  for p in PLUGIN_ROOT.rglob("__pycache__"))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = result.wasSuccessful()

    # test_completeness checks this too, but discovery runs alphabetically,
    # so it runs before any test that could import a bin/ script and leave a
    # __pycache__ behind. Checking again here — after everything has run — is
    # what makes the 13-file guarantee hold for the run that breaks it,
    # rather than for the next one.
    strays = bytecode_caches()
    if strays:
        ok = False
        sys.stderr.write(
            "\nFAIL: the suite left bytecode caches inside the plugin, which "
            "must contain exactly 13 files:\n"
            + "".join("  growth-loop/%s\n" % s for s in strays)
            + "A test imported a bin/ script without suppressing bytecode. "
              "See load_script() in tests/fixtures.py.\n")

    sys.exit(0 if ok else 1)
