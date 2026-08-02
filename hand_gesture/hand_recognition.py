
import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision



MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

MP_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),
    (0,17)
]

GESTURE_COMMAND_MAP = {
    "Open Hand ✋":    "START",
    "Fist ✊":         "STOP",
    "One Finger ☝️":   "SELECT",
    "Peace ✌️":        "PEACE",
    "Four Fingers 🖐️": "FOUR",
    "Unknown":        "NONE",
    "No Hand":        "NONE",
}



def count_fingers(landmarks, hand_label):
    fingers = []

    fingers.append(1 if landmarks[8].y < landmarks[6].y else 0)
    fingers.append(1 if landmarks[12].y < landmarks[10].y else 0)
    fingers.append(1 if landmarks[16].y < landmarks[14].y else 0)
    fingers.append(1 if landmarks[20].y < landmarks[18].y else 0)

    if hand_label == "Right":
        fingers.append(1 if landmarks[4].x < landmarks[3].x else 0)
    else:
        fingers.append(1 if landmarks[4].x > landmarks[3].x else 0)

    return fingers


def recognize_gesture(fingers):
    total = sum(fingers)

    if total == 5:
        return "Open Hand ✋"
    elif total == 0:
        return "Fist ✊"
    elif total == 1:
        return "One Finger ☝️"
    elif total == 2:
        return "Peace ✌️"
    elif total == 4:
        return "Four Fingers 🖐️"
    else:
        return "Unknown"



def _distance(p1, p2):
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5


def detect_pointing_direction(landmarks):

    wrist = landmarks[0]
    index_mcp = landmarks[5]   
    index_tip = landmarks[8]   

    palm_size = _distance(wrist, index_mcp)
    finger_length = _distance(index_mcp, index_tip)

 
    if finger_length < palm_size * 0.5:
        return None

    diff_y = index_mcp.y - index_tip.y

    if diff_y > 0.02:
        return "UP"
    elif diff_y < -0.02:
        return "DOWN"
    else:
        return None



class HandGestureProcessor:

    def __init__(self, model_path: str = MODEL_PATH, num_hands: int = 1):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=num_hands,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.previous_y = None
        self.movement = "No Movement"

    def process_frame(self, frame, draw=True):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self.landmarker.detect(mp_image)

        gesture_text = "No Hand"
        command = "NONE"
        confidence = 0.0

        if result.hand_landmarks:
            hand_landmarks = result.hand_landmarks[0]
            hand_label = result.handedness[0][0].category_name

            fingers = count_fingers(hand_landmarks, hand_label)
            gesture_text = recognize_gesture(fingers)
            confidence = 0.92

            pointing_direction = detect_pointing_direction(hand_landmarks)

            if pointing_direction == "UP":
                gesture_text = "One Finger Up"
                command = "SCROLL_UP"
            elif pointing_direction == "DOWN":
                gesture_text = "One Finger Down"
                command = "SCROLL_DOWN"
            else:
                wrist_y = hand_landmarks[0].y
                if self.previous_y is not None:
                    diff = self.previous_y - wrist_y
                    if diff > 0.02:
                        self.movement = "Scroll Up"
                        command = "SCROLL_UP"
                    elif diff < -0.02:
                        self.movement = "Scroll Down"
                        command = "SCROLL_DOWN"
                    else:
                        self.movement = "No Movement"
                else:
                    self.movement = "No Movement"
                self.previous_y = wrist_y

                if command == "NONE":
                    command = GESTURE_COMMAND_MAP.get(gesture_text, "NONE")

            if draw:
                h, w, _ = frame.shape

                for start, end in MP_CONNECTIONS:
                    x1 = int(hand_landmarks[start].x * w)
                    y1 = int(hand_landmarks[start].y * h)
                    x2 = int(hand_landmarks[end].x * w)
                    y2 = int(hand_landmarks[end].y * h)
                    cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                for point in hand_landmarks:
                    x = int(point.x * w)
                    y = int(point.y * h)
                    cv2.circle(frame, (x, y), 5, (255, 0, 0), -1)

        if draw:
            cv2.putText(frame, f"Gesture: {gesture_text}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Movement: {self.movement}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            cv2.putText(frame, f"Command: {command}", (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        result_dict = {
            "gesture": gesture_text,
            "movement": self.movement,
            "command": command,
            "confidence": confidence,
        }

        return frame, result_dict


if __name__ == "__main__":
    processor = HandGestureProcessor()
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, result = processor.process_frame(frame)
        print(result)

        cv2.imshow("Hand Gesture Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()