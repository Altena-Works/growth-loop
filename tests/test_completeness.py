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


if __name__ == "__main__":
    unittest.main()
