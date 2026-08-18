import os
import tempfile
import unittest

import database


PLAN = {
    "planId": "test_plan",
    "name": "Test Plan",
    "description": "Test",
    "difficulty": "Beginner",
    "durationWeeks": 1,
    "exercises": [
        {
            "name": "Squat",
            "targetReps": 2,
            "targetSets": 1,
            "restSeconds": 10,
            "notes": "Controlled",
            "order": 1,
        }
    ],
}


class DatabaseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        database.init_db()
        self.patient_id = database.create_user("patient-one", "password123", "patient")
        self.doctor_id = database.create_user("doctor-one", "password123", "doctor")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_authenticated_profiles_and_relationship_assignment(self) -> None:
        self.assertEqual(
            database.authenticate_user("PATIENT-ONE", "password123"), self.patient_id
        )
        self.assertTrue(database.create_care_relationship(self.doctor_id, self.patient_id))
        self.assertTrue(database.is_doctor_for_patient(self.doctor_id, self.patient_id))

        assignment = database.create_plan_assignment(
            self.doctor_id, self.patient_id, PLAN, "Complete slowly"
        )
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment["plan"]["planId"], "test_plan")
        self.assertEqual(len(database.get_doctor_patients(self.doctor_id)), 1)

        self.assertTrue(database.remove_care_relationship(self.doctor_id, self.patient_id))
        self.assertFalse(database.is_doctor_for_patient(self.doctor_id, self.patient_id))
        self.assertEqual(database.get_doctor_patients(self.doctor_id), [])
        self.assertEqual(database.get_assignment(assignment["assignment_id"])["status"], "paused")

    def test_session_metrics_are_atomic_and_streak_counts_days(self) -> None:
        session_data = {
            "duration": 60,
            "exercise_name": "Squat",
            "total_reps": 2,
            "form_quality": 50,
            "speed_warnings_count": 1,
            "plan_id": "test_plan",
            "exercise_results": [
                {
                    "exercise_name": "Squat",
                    "total_reps": 2,
                    "good_form_reps": 1,
                    "form_quality": 50,
                    "speed_warnings_count": 1,
                    "sets_completed": 1,
                }
            ],
        }
        first_id = database.save_session(self.patient_id, session_data)
        second_id = database.save_session(self.patient_id, session_data)
        self.assertIsNotNone(first_id)
        self.assertIsNotNone(second_id)

        profile = database.get_user_profile(self.patient_id)
        self.assertEqual(profile["total_sessions"], 2)
        self.assertEqual(profile["current_streak"], 1)
        sessions = database.get_user_sessions(self.patient_id)
        self.assertEqual(sessions[0]["exercises"][0]["good_form_reps"], 1)
        analytics = database.get_patient_analytics(self.patient_id, days=30)
        self.assertEqual(analytics["total_reps_all_time"], 4)
        self.assertEqual(analytics["total_sessions"], 2)


if __name__ == "__main__":
    unittest.main()
