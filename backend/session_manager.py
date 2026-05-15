from datetime import datetime
from collections import Counter

class SessionManager:
    def __init__(self):
        self.start_time = None
        self.total_reps = 0
        self.detected_exercises = [] # List of labels detected per frame/window
        self.is_active = False

    def start_session(self):
        self.start_time = datetime.now()
        self.total_reps = 0
        self.detected_exercises = []
        self.is_active = True

    def update(self, label, reps):
        if not self.is_active:
            return
        
        if label:
            self.detected_exercises.append(label)
        
        # Assume reps is cumulative for the current exercise
        # For session total, we might need logic to sum up reps across different exercises
        # For this MVP, let's just track the max reps seen or increment if we detect a change
        # Simplified: Just store the current rep count passed from the main loop
        self.total_reps = reps

    def end_session(self):
        self.is_active = False
        if not self.start_time:
            return None

        duration = (datetime.now() - self.start_time).total_seconds()
        
        # Find most frequent exercise
        most_common_exercise = "None"
        if self.detected_exercises:
            counts = Counter(self.detected_exercises)
            most_common_exercise = counts.most_common(1)[0][0]

        summary = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "durationSeconds": int(duration),
            "totalReps": self.total_reps,
            "mostFrequentExercise": most_common_exercise,
            "message": f"Great job! You focused mostly on {most_common_exercise}."
        }
        return summary
