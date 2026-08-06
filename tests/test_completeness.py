import unittest

from fixtures import EXPECTED_TREE, PLUGIN_ROOT


class TestCompleteness(unittest.TestCase):
    def test_tree_is_exactly_the_thirteen_files(self):
        found = {
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        missing = sorted(set(EXPECTED_TREE) - found)
        unexpected = sorted(found - set(EXPECTED_TREE))
        self.assertEqual((missing, unexpected), ([], []))

    def test_there_are_exactly_thirteen(self):
        self.assertEqual(len(EXPECTED_TREE), 13)

    def test_no_bytecode_cache_ships_inside_the_plugin(self):
        # The tree check above skips __pycache__, so it cannot see this.
        # `python3 -m py_compile growth-loop/bin/*` — step one of the spec's
        # own verification protocol — writes a __pycache__ next to the
        # scripts, which is three extra files inside a plugin that must
        # contain exactly thirteen. Syntax-check without writing instead:
        #   python3 -c 'import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]' growth-loop/bin/*
        caches = sorted(str(p.relative_to(PLUGIN_ROOT))
                        for p in PLUGIN_ROOT.rglob("__pycache__"))
        self.assertEqual(caches, [])


if __name__ == "__main__":
    unittest.main()
