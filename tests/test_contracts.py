import unittest
from _path import *  # noqa
from skynet_plus import Tool, tool, Result, Task
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
        self.assertEqual(add.parameters, {"a": "int", "b": "int"})

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

    def test_unknown_flag_is_an_error(self):
        with self.assertRaises(ValueError):
            normalise_requirements({"telepathy": True})


if __name__ == "__main__":
    unittest.main()
