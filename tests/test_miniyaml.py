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

    def test_a_hash_inside_quotes_is_not_a_comment(self):
        self.assertEqual(miniyaml.loads('key: "a#b"')["key"], "a#b")

    def test_tabs_are_refused(self):
        with self.assertRaises(miniyaml.YAMLError):
            miniyaml.loads("a:\n\tb: 1")

    def test_dumps_round_trips(self):
        data = {"profile": "local", "model": {"provider": "fake", "n": 2, "on": True, "note": None},
                "list": [{"a": 1, "b": "x"}, "y"], "quoted": "has: colon"}
        self.assertEqual(miniyaml.loads(miniyaml.dumps(data)), data)


if __name__ == "__main__":
    unittest.main()
