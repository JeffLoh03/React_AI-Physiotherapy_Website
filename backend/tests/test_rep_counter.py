import unittest

try:
    from main import (
        REP_PROFILES,
        exercise_key,
        expected_class_for_exercise,
        plan_target_for_exercise,
        rep_update,
    )
except (ImportError, ModuleNotFoundError):
    REP_PROFILES = None
    exercise_key = None
    expected_class_for_exercise = None
    plan_target_for_exercise = None
    rep_update = None


@unittest.skipIf(rep_update is None, "backend pose runtime dependencies are not installed")
class RepCounterTests(unittest.TestCase):
    CASES = {
        "Shoulder Abduction": (20.0, 90.0, 20.0),
        "Shoulder V-W Exercise": (170.0, 85.0, 170.0),
        "Inclined Push-Up": (170.0, 85.0, 170.0),
        "Hip Abduction": (175.0, 120.0, 175.0),
        "Forward Lunge": (175.0, 95.0, 175.0),
        "Squat": (175.0, 95.0, 175.0),
    }

    @staticmethod
    def run_angles(label, values):
        state = {
            "stage": "waiting_start",
            "phase_frames": 0,
            "reps": 0,
            "last_rep_time": 0.0,
            "angle_buffer": [],
        }
        for value in values:
            rep_update(label, value, state)
        return state

    def test_every_exercise_counts_one_complete_cycle(self):
        self.assertEqual(len(REP_PROFILES), 6)
        for label, (start, active, returned) in self.CASES.items():
            with self.subTest(label=label):
                state = self.run_angles(label, [start] * 4 + [active] * 6 + [returned] * 6)
                self.assertEqual(state["reps"], 1)
                self.assertEqual(state["stage"], "ready")

    def test_both_cycle_directions_count(self):
        for label, (first, opposite, _) in self.CASES.items():
            with self.subTest(label=label):
                state = self.run_angles(
                    label,
                    [opposite] * 4 + [first] * 6 + [opposite] * 6,
                )
                self.assertEqual(state["reps"], 1)
                self.assertEqual(state["stage"], "ready")

    def test_partial_cycle_does_not_count(self):
        for label, (start, active, _) in self.CASES.items():
            with self.subTest(label=label):
                state = self.run_angles(label, [start] * 4 + [active] * 6)
                self.assertEqual(state["reps"], 0)
                self.assertEqual(state["stage"], "active")

    def test_small_motion_does_not_fake_a_rep(self):
        cases = {
            "Shoulder Abduction": [45.0] * 4 + [58.0] * 5 + [45.0] * 5,
            "Shoulder V-W Exercise": [140.0] * 4 + [126.0] * 5 + [140.0] * 5,
            "Squat": [160.0] * 4 + [140.0] * 5 + [160.0] * 5,
        }
        for label, angles in cases.items():
            with self.subTest(label=label):
                self.assertEqual(self.run_angles(label, angles)["reps"], 0)

    def test_labels_map_to_six_distinct_profiles(self):
        keys = {exercise_key(label) for label in self.CASES}
        self.assertEqual(keys, set(REP_PROFILES))
        classes = {expected_class_for_exercise(label) for label in self.CASES}
        self.assertEqual(classes, {"Ex1", "Ex2", "Ex3", "Ex4", "Ex5", "Ex6"})

    def test_model_name_resolves_plan_target(self):
        target = {"name": "V-W", "targetReps": 12, "targetSets": 3}
        resolved = plan_target_for_exercise({"V-W": target}, "Shoulder V-W Exercise")
        self.assertIs(resolved, target)


if __name__ == "__main__":
    unittest.main()
