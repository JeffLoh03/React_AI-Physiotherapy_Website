import json
import os
import unittest

try:
    from pose_features import FULL_WINDOW_FEATURE_NAMES, RealtimeFeatureExtractor
except ModuleNotFoundError:
    FULL_WINDOW_FEATURE_NAMES = None
    RealtimeFeatureExtractor = None


@unittest.skipIf(RealtimeFeatureExtractor is None, "pose runtime dependencies are not installed")
class PoseFeatureExtractorTests(unittest.TestCase):
    @staticmethod
    def landmarks():
        points = [{"x": 0.5, "y": 0.5, "visibility": 1.0} for _ in range(33)]
        coordinates = {
            0: (0.50, 0.10),
            11: (0.40, 0.25), 12: (0.60, 0.25),
            13: (0.35, 0.40), 14: (0.65, 0.40),
            15: (0.30, 0.55), 16: (0.70, 0.55),
            23: (0.45, 0.50), 24: (0.55, 0.50),
            25: (0.45, 0.70), 26: (0.55, 0.70),
            27: (0.45, 0.90), 28: (0.55, 0.90),
        }
        for index, (x, y) in coordinates.items():
            points[index].update(x=x, y=y)
        return points

    def test_feature_order_matches_saved_model_metadata(self):
        path = os.path.join(os.path.dirname(__file__), "..", "models", "feature_order.json")
        with open(path, encoding="utf-8") as file:
            saved_order = json.load(file)
        self.assertEqual(FULL_WINDOW_FEATURE_NAMES, saved_order)
        self.assertEqual(len(saved_order), 132)

    def test_first_window_contains_all_132_finite_features(self):
        extractor = RealtimeFeatureExtractor()
        row = None
        for _ in range(30):
            row = extractor.add(self.landmarks(), 640, 480)
        self.assertIsNotNone(row)
        self.assertEqual(list(row), FULL_WINDOW_FEATURE_NAMES)
        self.assertEqual(len(row), 132)


if __name__ == "__main__":
    unittest.main()
