import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


MODEL_PATH = os.path.join(os.path.dirname(__file__), "pose_landmarker.task")

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (24, 26), (26, 28),
    (27, 29), (27, 31), (28, 30), (28, 32),
]

LANDMARK_NAMES = {
    0: "nose", 11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
}


def classify_posture(landmarks):
    left_hip_y = landmarks[23].y
    left_knee_y = landmarks[25].y
    left_shoulder_y = landmarks[11].y

    hip_knee_diff = abs(left_hip_y - left_knee_y)

    if hip_knee_diff < 0.15:
        return "Sitting"
    elif left_shoulder_y > left_hip_y:
        return "Bending"
    else:
        return "Standing"


class PoseProcessor:

    def __init__(self, model_path: str = MODEL_PATH):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)

    def process_frame(self, frame, draw=True):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self.landmarker.detect(mp_image)

        posture = "No Person"
        landmarks_dict = {}

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            posture = classify_posture(landmarks)

            for idx, name in LANDMARK_NAMES.items():
                landmarks_dict[name] = {"x": landmarks[idx].x, "y": landmarks[idx].y}

            if draw:
                h, w, _ = frame.shape
                for start, end in POSE_CONNECTIONS:
                    x1, y1 = int(landmarks[start].x * w), int(landmarks[start].y * h)
                    x2, y2 = int(landmarks[end].x * w), int(landmarks[end].y * h)
                    cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                for idx, name in LANDMARK_NAMES.items():
                    x, y = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
                    cv2.circle(frame, (x, y), 5, (255, 0, 0), -1)
                    cv2.putText(frame, name, (x + 8, y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        if draw:
            cv2.putText(frame, f"Posture: {posture}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        return frame, {"posture": posture, "landmarks": landmarks_dict}


if __name__ == "__main__":
    processor = PoseProcessor()
    camera_source = os.getenv("CAMERA_URL", "0")
    try:
        camera_source = int(camera_source)
    except ValueError:
        pass
    cap = cv2.VideoCapture(camera_source)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame, result = processor.process_frame(frame)
        print(result["posture"])
        cv2.imshow("Pose Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()