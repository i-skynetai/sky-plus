from __future__ import annotations

import unittest

from _path import *  # noqa

from skynet_plus import ConfigError, Result, Task, Tool, tool
from skynet_plus.core.contracts import normalise_requirements


class ToolsWrapFunctions(unittest.TestCase):
    def test_invoke_passes_only_accepted_arguments(self):
        @tool
        def add(a: int, b: int = 1):
            """adds"""
            return a + b
        self.assertEqual(add.name, "add")
        self.assertEqual(add.description, "adds")
        self.assertEqual(add.invoke(a=2, b=3, ignored=9), 5)

    def test_parameters_are_a_json_schema_even_under_postponed_annotations(self):
        @tool
        def search(query: str, limit: int = 5, tags: list[str] | None = None, strict: bool = False):
            return query
        schema = search.parameters
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"]["query"], {"type": "string"})
        self.assertEqual(schema["properties"]["limit"], {"type": "integer", "default": 5})
        self.assertEqual(schema["properties"]["strict"], {"type": "boolean", "default": False})
        self.assertIn("anyOf", schema["properties"]["tags"])
        self.assertEqual(schema["required"], ["query"])

    def test_an_untyped_parameter_is_an_untyped_property(self):
        t = Tool.from_function(lambda a, b=2: a, name="f")
        self.assertEqual(t.parameters["properties"]["a"], {})
        self.assertEqual(t.parameters["properties"]["b"], {"default": 2})

    def test_var_kwargs_receive_everything(self):
        t = Tool.from_function(lambda **kw: sorted(kw), name="k")
        self.assertEqual(t.invoke(x=1, y=2), ["x", "y"])

    def test_task_of_wraps_strings(self):
        t = Task.of("hello")
        self.assertEqual(t.text, "hello")
        self.assertIs(Task.of(t), t)

    def test_result_ok_and_dict(self):
        r = Result("t", "out")
        self.assertTrue(r.ok)
        self.assertEqual(r.to_dict()["status"], "ok")


class RequirementsNormalise(unittest.TestCase):
    def test_flat_and_nested_forms_merge(self):
        out = normalise_requirements({"streaming": True, "memory": {"temporal": True}, "human_approval": False})
        self.assertEqual(out, {"agent-runtime": {"streaming": True, "hitl": False}, "memory": {"temporal": True}})

    def test_unknown_flag_and_unknown_capability_are_config_errors(self):
        with self.assertRaises(ConfigError):
            normalise_requirements({"streamng": True})
        with self.assertRaises(ConfigError) as cm:
            normalise_requirements({"memry": {"persistent": True}})
        self.assertIn("memry", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
