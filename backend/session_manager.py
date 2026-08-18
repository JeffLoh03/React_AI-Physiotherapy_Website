from collections import Counter
from datetime import datetime
from typing import Dict, Optional


class SessionManager:
    """State for one WebSocket connection and one rehabilitation session."""

    def __init__(self) -> None:
        self.start_time: Optional[datetime] = None
        self.pause_started: Optional[datetime] = None
        self.paused_seconds = 0.0
        self.is_active = False
        self.plan_id: Optional[str] = None
        self.assignment_id: Optional[str] = None
        self.detected_exercises = []
        self.exercise_results: Dict[str, Dict[str, float]] = {}

    def start_session(self, plan_id: Optional[str] = None, assignment_id: Optional[str] = None) -> None:
        self.start_time = datetime.now()
        self.pause_started = None
        self.paused_seconds = 0.0
        self.is_active = True
        self.plan_id = plan_id
        self.assignment_id = assignment_id
        self.detected_exercises = []
        self.exercise_results = {}

    def pause_session(self) -> None:
        if self.is_active and self.pause_started is None:
            self.pause_started = datetime.now()

    def resume_session(self) -> None:
        if self.pause_started is not None:
            self.paused_seconds += (datetime.now() - self.pause_started).total_seconds()
            self.pause_started = None

    def update(
        self,
        label: str,
        reps: int,
        form_quality: float,
        speed_warning: Optional[str],
        good_form_reps: int,
        sets_completed: int,
    ) -> None:
        if not self.is_active or self.pause_started is not None or not label:
            return

        self.detected_exercises.append(label)
        result = self.exercise_results.setdefault(
            label,
            {
                "total_reps": 0,
                "good_form_reps": 0,
                "form_quality": 100.0,
                "speed_warnings_count": 0,
                "sets_completed": 0,
            },
        )
        result["total_reps"] = max(int(result["total_reps"]), int(reps))
        result["good_form_reps"] = max(int(result["good_form_reps"]), int(good_form_reps))
        result["sets_completed"] = max(int(result["sets_completed"]), int(sets_completed))
        result["form_quality"] = min(max(float(form_quality), 0.0), 100.0)
        if speed_warning:
            result["speed_warnings_count"] += 1

    def end_session(self) -> Optional[Dict[str, object]]:
        if not self.start_time or not self.is_active:
            return None

        now = datetime.now()
        if self.pause_started is not None:
            self.paused_seconds += (now - self.pause_started).total_seconds()
            self.pause_started = None
        self.is_active = False

        duration = max(0, int((now - self.start_time).total_seconds() - self.paused_seconds))
        results = []
        for exercise_name, values in self.exercise_results.items():
            results.append(
                {
                    "exercise_name": exercise_name,
                    "total_reps": int(values["total_reps"]),
                    "good_form_reps": int(values["good_form_reps"]),
                    "form_quality": round(float(values["form_quality"]), 2),
                    "speed_warnings_count": int(values["speed_warnings_count"]),
                    "sets_completed": int(values["sets_completed"]),
                }
            )

        total_reps = sum(item["total_reps"] for item in results)
        speed_warnings = sum(item["speed_warnings_count"] for item in results)
        weighted_quality = (
            sum(item["form_quality"] * max(item["total_reps"], 1) for item in results)
            / sum(max(item["total_reps"], 1) for item in results)
            if results
            else 100.0
        )
        most_common = "None"
        if self.detected_exercises:
            most_common = Counter(self.detected_exercises).most_common(1)[0][0]

        return {
            "date": now.strftime("%Y-%m-%d %H:%M:%S"),
            "durationSeconds": duration,
            "totalReps": total_reps,
            "mostFrequentExercise": most_common,
            "formQuality": round(weighted_quality, 2),
            "speedWarningsCount": speed_warnings,
            "exerciseResults": results,
            "planId": self.plan_id,
            "assignmentId": self.assignment_id,
            "message": f"Great job! You completed {total_reps} reps with {weighted_quality:.0f}% average form quality.",
        }
