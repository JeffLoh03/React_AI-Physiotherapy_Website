import unittest

from session_manager import SessionManager


class SessionManagerTests(unittest.TestCase):
    def test_results_accumulate_across_exercises_and_end_once(self) -> None:
        manager = SessionManager()
        manager.start_session("plan-1", "assignment-1")
        manager.update("Squat", 3, 66.67, None, 2, 1)
        manager.update("Squat", 5, 80, "SLOW_DOWN", 4, 1)
        manager.update("Lunge", 2, 100, None, 2, 1)

        summary = manager.end_session()
        self.assertEqual(summary["totalReps"], 7)
        self.assertEqual(summary["speedWarningsCount"], 1)
        self.assertEqual(len(summary["exerciseResults"]), 2)
        self.assertEqual(summary["assignmentId"], "assignment-1")
        self.assertIsNone(manager.end_session())


if __name__ == "__main__":
    unittest.main()
