import numpy as np

def calculate_angle(a, b, c):
    """
    Calculates the angle between three points a, b, c.
    b is the vertex.
    Returns angle in degrees (0-180).
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    if angle > 180.0:
        angle = 360-angle
        
    return angle

def extract_features(landmarks):
    """
    Extracts a feature vector from MediaPipe landmarks for the exercise classifier.
    
    IMPORTANT: This function MUST match the feature columns used during training.
    Since we don't have the training code, we implement a standard set of 
    joint angles and relative positions.
    
    Expected landmarks: MediaPipe Pose landmarks object.
    Returns: list of float values (feature vector).
    """
    
    # Helper to get [x, y]
    def get_coords(idx):
        return [landmarks[idx].x, landmarks[idx].y]

    # Key points
    # 11: left_shoulder, 12: right_shoulder
    # 13: left_elbow, 14: right_elbow
    # 15: left_wrist, 16: right_wrist
    # 23: left_hip, 24: right_hip
    # 25: left_knee, 26: right_knee
    # 27: left_ankle, 28: right_ankle

    # 1. Calculate Angles (8 main joint angles)
    # Left Arm
    l_shoulder_angle = calculate_angle(get_coords(23), get_coords(11), get_coords(13))
    l_elbow_angle = calculate_angle(get_coords(11), get_coords(13), get_coords(15))
    
    # Right Arm
    r_shoulder_angle = calculate_angle(get_coords(24), get_coords(12), get_coords(14))
    r_elbow_angle = calculate_angle(get_coords(12), get_coords(14), get_coords(16))
    
    # Left Leg
    l_hip_angle = calculate_angle(get_coords(11), get_coords(23), get_coords(25))
    l_knee_angle = calculate_angle(get_coords(23), get_coords(25), get_coords(27))
    
    # Right Leg
    r_hip_angle = calculate_angle(get_coords(12), get_coords(24), get_coords(26))
    r_knee_angle = calculate_angle(get_coords(24), get_coords(26), get_coords(28))

    # 2. Relative Y-distances (vertical alignment)
    # Wrist vs Shoulder (positive if wrist is below shoulder)
    l_wrist_shoulder_y = landmarks[15].y - landmarks[11].y
    r_wrist_shoulder_y = landmarks[16].y - landmarks[12].y
    
    # Wrist vs Hip
    l_wrist_hip_y = landmarks[15].y - landmarks[23].y
    r_wrist_hip_y = landmarks[16].y - landmarks[24].y

    # Construct Feature Vector
    # ORDER MATTERS: This must match your .pkl model's expectation.
    # If your model uses raw x,y,z coordinates, replace this logic.
    features = [
        l_shoulder_angle, l_elbow_angle, 
        r_shoulder_angle, r_elbow_angle,
        l_hip_angle, l_knee_angle,
        r_hip_angle, r_knee_angle,
        l_wrist_shoulder_y, r_wrist_shoulder_y,
        l_wrist_hip_y, r_wrist_hip_y
    ]
    
    return features
