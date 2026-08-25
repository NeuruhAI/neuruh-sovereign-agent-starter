import json
import unittest

from neuruh_agent_run_manifest import canonical_json
from neuruh_sovereign_agent_starter.organism import projection as P
from neuruh_sovereign_agent_starter.organism.court import AGENT_ID, WORLD_ID, demo_seed
from neuruh_sovereign_agent_starter.organism.world import instantiate

AT = "2026-08-24T00:00:01Z"


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.w = instantiate(demo_seed(), world_id=WORLD_ID, created_at=AT, creator="t")
        self.w.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")

    def test_projection_is_reversible(self):
        files = P.project(self.w)
        self.assertEqual(sorted(p.rsplit("/", 1)[-1][:-3] for p in files if p.endswith(".md")), sorted(P.SECTIONS))
        self.assertEqual(canonical_json(P.parse(files)), canonical_json(P.sections(self.w)))
        self.assertTrue(P.roundtrip_ok(self.w))

    def test_one_json_block_per_file_and_index(self):
        files = P.project(self.w)
        for path, text in files.items():
            if path.endswith(".md"):
                self.assertEqual(text.count("\n```json\n"), 1, path)
        idx = json.loads(files[f"Worlds/{WORLD_ID}/PROJECTION.json"])
        self.assertEqual(idx["state_digest"], self.w.state_digest())
        self.assertEqual(len(idx["files"]), len(P.SECTIONS))

    def test_markdown_is_projection_not_state(self):
        files = P.project(self.w)
        edited = {k: (v.replace("- **mode**: synthetic", "- **mode**: live") if k.endswith("WORLD.md") else v) for k, v in files.items()}
        self.assertEqual(P.parse(edited)["WORLD"]["world_mode"], "synthetic")   # prose edits never change canonical data


if __name__ == "__main__":
    unittest.main()
