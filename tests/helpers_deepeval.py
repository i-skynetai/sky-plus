"""A DeepEval metric that needs no judge, for offline tests."""
try:
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase

    class LengthMetric(BaseMetric):
        def __init__(self, threshold: float = 0.5, min_chars: int = 1):
            self.threshold, self.min_chars = threshold, min_chars
            self.score = None; self.reason = None; self.success = None; self.error = None

        def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            self.score = 1.0 if len(test_case.actual_output or "") >= self.min_chars else 0.0
            self.reason = f"{len(test_case.actual_output or '')} chars"
            self.success = self.score >= self.threshold
            return self.score

        async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return bool(self.success)

        @property
        def __name__(self):
            return "LengthMetric"
except ImportError:
    pass
