import unittest

from _path import *  # noqa

from skynet_plus.core import miniyaml


class TheYamlSubsetReads(unittest.TestCase):
    def test_nested_maps_lists_and_scalars(self):
        text = """
# a comment
profile: local
model:
  provider: litellm
  model: "gpt-4o-mini"   # trailing comment
  temperature: 0.2
  retries: 3
  stream: false
  tags: [a, b, 3]
tools:
  - name: crm
    timeout: 5
  - name: jira
  - plain
empty:
"""
        data = miniyaml.loads(text)
        self.assertEqual(data["profile"], "local")
        self.assertEqual(data["model"]["model"], "gpt-4o-mini")
        self.assertEqual(data["model"]["temperature"], 0.2)
        self.assertEqual(data["model"]["retries"], 3)
        self.assertIs(data["model"]["stream"], False)
        self.assertEqual(data["model"]["tags"], ["a", "b", 3])
        self.assertEqual(data["tools"][0], {"name": "crm", "timeout": 5})
        self.assertEqual(data["tools"][1], {"name": "jira"})
        self.assertEqual(data["tools"][2], "plain")
        self.assertIsNone(data["empty"])

    def test_one_line_flow_maps_as_the_readme_writes_them(self):
        data = miniyaml.loads('agent-runtime: {provider: langgraph}\n'
                              'model:         {provider: litellm, model: ${SKYNET_MODEL:gpt-4o-mini}, n: 2}\n'
                              'nested: {a: [1, {b: "x, y"}], c: {}}\n')
        self.assertEqual(data["agent-runtime"], {"provider": "langgraph"})
        self.assertEqual(data["model"], {"provider": "litellm", "model": "${SKYNET_MODEL:gpt-4o-mini}", "n": 2})
        self.assertEqual(data["nested"], {"a": [1, {"b": "x, y"}], "c": {}})

    def test_a_list_item_that_is_a_flow_map(self):
        self.assertEqual(miniyaml.loads("- {a: 1}\n- [x]\n"), [{"a": 1}, ["x"]])

    def test_unsupported_constructs_name_the_line(self):
        for text in ("a: &anchor 1", "a: |\n  block", "a: {b: 1", "a: *ref"):
            with self.assertRaises(miniyaml.YAMLError) as cm:
                miniyaml.loads("x: 1\n" + text)
            self.assertIn("line 2", str(cm.exception))

    def test_a_hash_inside_quotes_is_not_a_comment(self):
        self.assertEqual(miniyaml.loads('key: "a#b"')["key"], "a#b")

    def test_tabs_are_refused(self):
        with self.assertRaises(miniyaml.YAMLError):
            miniyaml.loads("a:\n\tb: 1")

    def test_dumps_round_trips_including_values_with_comment_markers(self):
        data = {"profile": "local", "model": {"provider": "fake", "n": 2, "on": True, "note": None,
                                             "prompt": "Answer as agent #1", "flow": {"x": 1}},
                "list": [{"a": 1, "b": "x"}, "y", "a, b"], "quoted": "has: colon"}
        self.assertEqual(miniyaml.loads(miniyaml.dumps(data)), data)


class SetKeyEditsInPlace(unittest.TestCase):
    TEXT = ("# keep me\nprofile: local\n\nmodel:\n  provider: fake   # the model\n  temperature: 0.2\n"
            "decision: {provider: fake, threshold: 0.7}\nmemory: fake\n")

    def test_block_section_keeps_other_keys_comments_and_order(self):
        out = miniyaml.set_key(self.TEXT, "model", "provider", "litellm")
        self.assertIn("# keep me", out)
        self.assertIn("  provider: litellm   # the model", out)
        self.assertIn("  temperature: 0.2", out)
        self.assertEqual(miniyaml.loads(out)["model"], {"provider": "litellm", "temperature": 0.2})
        self.assertLess(out.index("profile"), out.index("model:"))

    def test_flow_section_keeps_its_other_keys(self):
        out = miniyaml.set_key(self.TEXT, "decision", "provider", "praxis")
        self.assertEqual(miniyaml.loads(out)["decision"], {"provider": "praxis", "threshold": 0.7})

    def test_shorthand_section_becomes_a_block(self):
        out = miniyaml.set_key(self.TEXT, "memory", "provider", "mem0")
        self.assertEqual(miniyaml.loads(out)["memory"], {"provider": "mem0"})

    def test_a_missing_section_is_appended(self):
        out = miniyaml.set_key(self.TEXT, "telemetry", "provider", "fake")
        self.assertEqual(miniyaml.loads(out)["telemetry"], {"provider": "fake"})
        self.assertEqual(miniyaml.loads(out)["model"]["temperature"], 0.2)

    def test_a_missing_key_is_added_to_the_block(self):
        out = miniyaml.set_key(self.TEXT, "model", "max_tokens", 100)
        self.assertEqual(miniyaml.loads(out)["model"]["max_tokens"], 100)


if __name__ == "__main__":
    unittest.main()
