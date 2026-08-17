
import os
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Model path for the hand landmarker task AI
MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
#rasm el hand  
MP_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),
    (0,17)
]
#command el hand gesture y3ni el hand gesture ely feha el command
# dictionary el hand gesture ely feha el command key value pair
GESTURE_COMMAND_MAP = {
    "Open Hand ✋":    "START",
    "Fist ✊":         "STOP",
    "One Finger ☝️":   "SELECT",
    "Peace ✌️":        "PEACE",
    "Four Fingers 🖐️": "FOUR",
    "Unknown":        "NONE",
    "No Hand":        "NONE",
}


# count the fingers ely feha el hand landmark ely feha el hand label 
#Awel haga:fingers = []De list hnt7ot feha 7alet kol esba3.
#1 = Open
#0 = Closed
#Index Finger
#landmarks[8].y < landmarks[6].y
#Law no2tet ra2s el esba3 (8) fo2 el mofsal (6), yeb2a el esba3 maftoo7.
#=> A    dd 1
    #Law la2
#=> Add 0
def count_fingers(landmarks, hand_label):
    fingers = []

    fingers.append(1 if landmarks[8].y < landmarks[6].y else 0)
    fingers.append(1 if landmarks[12].y < landmarks[10].y else 0) #middle finger
    fingers.append(1 if landmarks[16].y < landmarks[14].y else 0)  #ring finger
    fingers.append(1 if landmarks[20].y < landmarks[18].y else 0)  #pinky finger
    #if hand_label is right, add 1 if the index finger is to the right of the middle finger, otherwise add 0
    if hand_label == "Right":
        fingers.append(1 if landmarks[4].x < landmarks[3].x else 0) #index finger
    else:
        fingers.append(1 if landmarks[4].x > landmarks[3].x else 0) #index finger
    #return the list of fingers
    return fingers


def recognize_gesture(fingers):
    total = sum(fingers)
#if total is 5, return "Open Hand ✋"
    if total == 5:
        return "Open Hand ✋"
    #if total is 0, return "Fist ✊"
    elif total == 0:    
        return "Fist ✊"
    #if total is 1, return "One Finger ☝️"
    elif total == 1:
        return "One Finger ☝️"
    #if total is 2, return "Peace ✌️"
    elif total == 2:
        return "Peace ✌️"
    #if total is 4, return "Four Fingers 🖐️"
    elif total == 4:
        return "Four Fingers 🖐️"
    else:
        #if total is not 0, 1, 2, 4, return "Unknown"
        return "Unknown"



#calculate the distance between two points
def _distance(p1, p2):
    #return the distance between two points
    #Bnesta5demha 3ashan n3raf: #Tol el kaf (Palm) and #Tol el esba3 (Finger)
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5

#El esba3 byeshawr Fo2 wala Ta7t ely feha el pointing direction (UP or DOWN)
def detect_pointing_direction(landmarks):

    wrist = landmarks[0]
    index_mcp = landmarks[5]   
    index_tip = landmarks[8]   
 #Ye7seb tol el kaf (Palm) ely feha el index finger.
    palm_size = _distance(wrist, index_mcp)
    finger_length = _distance(index_mcp, index_tip)
#Law el esba3 a2sar mn nos el kaf
#=> yeb2a mesh mafrud. #(mafrud means pointing)
# #=> Mesh pointing.
 
    if finger_length < palm_size * 0.5:
        return None
#Direction
    diff_y = index_mcp.y - index_tip.y

    if diff_y > 0.02:
        return "UP"
    elif diff_y < -0.02:
        return "DOWN"
    else:
        return None


#Da el class el mas2ool 3an kol 7aga. #(processor means processor)
#Ye5od frame mn el camera.
#Ye3raf el gesture. #(gesture means gesture)
#Ye3raf el movement. #(movement means movement)
#Yerga3 command. #(command means command)
class HandGestureProcessor:

    def __init__(self, model_path: str = MODEL_PATH, num_hands: int = 1):                     #BaseOptions #3ashan yefta7 model: #(model means model)
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=num_hands,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.previous_y = None #3ashan yefta7 el previous y. #(previous y means previous y)
        self.movement = "No Movement"

    def process_frame(self, frame, draw=True):  #Kol frame mn el camera by5osh hena.
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) #Convert el frame ely feha el camera ely feha el bgr ely feha el rgb. #(bgr means blue green red) #(rgb means red green blue)    
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame) #Bn7awel el frame le MediaPipe Image.

        result = self.landmarker.detect(mp_image) #MediaPipe by3ml detection.
 #Law mafesh yad.
        gesture_text = "No Hand"
        command = "NONE"
        confidence = 0.0
    #Law la2a yad feha el hand landmarks.
        if result.hand_landmarks:
            hand_landmarks = result.hand_landmarks[0]
            hand_label = result.handedness[0][0].category_name    #yq3rf de left a2o right 

            fingers = count_fingers(hand_landmarks, hand_label)
            gesture_text = recognize_gesture(fingers)
            confidence = 0.92
    
            if gesture_text == "One Finger ☝️":
                pointing_direction = detect_pointing_direction(hand_landmarks)
                if pointing_direction == "UP":
                    gesture_text = "One Finger Up"
                    command = "SCROLL_UP"
                elif pointing_direction == "DOWN":
                    gesture_text = "One Finger Down"
                    command = "SCROLL_DOWN"
                else:
                    command = GESTURE_COMMAND_MAP.get(gesture_text, "SELECT")
            else:
                pointing_direction = detect_pointing_direction(hand_landmarks)
                wrist_y = hand_landmarks[0].y
                if self.previous_y is not None:
                    diff = self.previous_y - wrist_y
                    if diff > 0.04:
                        self.movement = "Scroll Up"
                    elif diff < -0.04:
                        self.movement = "Scroll Down"
                    else:
                        self.movement = "No Movement"
                else:
                    self.movement = "No Movement"
                self.previous_y = wrist_y

                command = GESTURE_COMMAND_MAP.get(gesture_text, "NONE")
     
            if draw:
                
                h, w, _ = frame.shape
# Ersm el hand landmarks 3ala el frame. #3ashan n7awel coordinates mn MediaPipe le pixels.
                for start, end in MP_CONNECTIONS:
                    # List feha el points eli btwasal el hand skeleton.
                    x1 = int(hand_landmarks[start].x * w)
                    y1 = int(hand_landmarks[start].y * h)
                    x2 = int(hand_landmarks[end].x * w)
                    y2 = int(hand_landmarks[end].y * h)
                    #Byrsm line ben kol 2 landmarks.
                    cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                for point in hand_landmarks:
                    x = int(point.x * w)
                    y = int(point.y * h)
                    cv2.circle(frame, (x, y), 5, (255, 0, 0), -1)

        if draw:
            #yrsm circle 3ala kol landmark.
            cv2.putText(frame, f"Gesture: {gesture_text}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        # By3rd etgah 7arakat el yad.
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
        print(result)

        cv2.imshow("Hand Gesture Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()