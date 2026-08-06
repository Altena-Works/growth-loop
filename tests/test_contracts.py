import json
import re
import unittest
from pathlib import Path

from fixtures import PLUGIN_ROOT

CONTRACTS = json.loads(
    (Path(__file__).resolve().parent.parent / "contracts" / "operations.json")
    .read_text(encoding="utf-8"))


def frontmatter(name):
    path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    return meta


class TestContractMatchesFrontmatter(unittest.TestCase):
    def test_every_skill_is_declared(self):
        declared = set(CONTRACTS["operations"])
        shipped = {p.parent.name for p in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(declared, shipped)

    def test_invokers_match_the_invocation_flag(self):
        # A contract that says a skill is user-only while the frontmatter
        # lets the model fire it is worse than no contract: it documents a
        # gate that is not there.
        for name, spec in CONTRACTS["operations"].items():
            user_only = spec["invokers"] == ["user"]
            flag = frontmatter(name).get("disable-model-invocation") == "true"
            self.assertEqual(user_only, flag,
                             "%s: contract says invokers=%s, frontmatter says "
                             "disable-model-invocation=%s"
                             % (name, spec["invokers"], flag))


class TestRoutingGraphIsClosed(unittest.TestCase):
    def test_every_route_lands_on_a_declared_operation(self):
        ops = CONTRACTS["operations"]
        for route in CONTRACTS["routes"]:
            self.assertIn(route["from"], ops, route)
            self.assertIn(route["to"], ops, route)

    def test_every_route_is_accepted_at_its_destination(self):
        # This is the journey->refine defect, mechanised. A route was added
        # from journey into refine for a merge, while refine's accept
        # clause still required a failure from the current session - so a
        # live model refused to take the documented route, correctly, and
        # two rounds of prose review had not caught it.
        #
        # Caveat on what a green run here actually proves: this only
        # discriminates for a destination with more than one accepted
        # evidence class. `recall`, `journey`, and `forget` each declare
        # exactly one, so any route landing on them is satisfied merely by
        # copying that single value - passing is necessary but not strong
        # evidence for those three. `refine` (four classes) and `profile`
        # (three) are where this assertion is actually doing discriminating
        # work.
        ops = CONTRACTS["operations"]
        for route in CONTRACTS["routes"]:
            accepted = ops[route["to"]]["accepts_evidence"]
            self.assertIn(route["evidence"], accepted,
                          "%s routes %r into %s, which accepts only %s"
                          % (route["from"], route["evidence"], route["to"],
                             accepted))

    def test_a_user_only_destination_says_so_at_every_source(self):
        # Routing into a skill the model cannot invoke is fine, but the
        # source has to say the model must stop and hand over. Three files
        # needed this sentence added by hand, one round apart each.
        #
        # A bare substring search for "cannot invoke"/"cannot call" anywhere
        # in the file would pass even if that phrase named a *different*
        # skill entirely - it has to be about route["to"] specifically, not
        # just present somewhere in a long document. Require the destination
        # name to appear near the phrase, not merely somewhere in the body.
        ops = CONTRACTS["operations"]
        window = 200
        for route in CONTRACTS["routes"]:
            if ops[route["to"]]["invokers"] != ["user"]:
                continue
            body = (PLUGIN_ROOT / "skills" / route["from"] / "SKILL.md").read_text()
            flattened = " ".join(body.split())
            name_pattern = re.compile(r"\b%s\b" % re.escape(route["to"]))
            found = False
            for phrase in ("cannot invoke", "cannot call"):
                for match in re.finditer(re.escape(phrase), flattened):
                    start = max(0, match.start() - window)
                    if name_pattern.search(flattened[start:match.start()]):
                        found = True
                        break
                if found:
                    break
            self.assertTrue(
                found,
                "%s routes into user-only %s without a sentence naming %s as "
                "something the model cannot invoke/call"
                % (route["from"], route["to"], route["to"]))


if __name__ == "__main__":
    unittest.main()
