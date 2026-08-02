import os
import face_recognition
import cv2
import numpy as np


KNOWN_FACES_DIR = os.path.join(os.path.dirname(__file__), "known_faces")


def load_known_faces(known_dir: str = KNOWN_FACES_DIR):
    
    known_encodings = []
    known_names = []

    if not os.path.exists(known_dir):
        print(f"⚠️ Folder not found: {known_dir}")
        return known_encodings, known_names

    for person in os.listdir(known_dir):
        person_folder = os.path.join(known_dir, person)

        if not os.path.isdir(person_folder):
            continue

        for file in os.listdir(person_folder):
            file_path = os.path.join(person_folder, file)

            image = face_recognition.load_image_file(file_path)
            encodings = face_recognition.face_encodings(image)

            if len(encodings) > 0:
                known_encodings.append(encodings[0])
                known_names.append(person)

    return known_encodings, known_names


class FaceRecognitionProcessor:

    def __init__(self, known_dir: str = KNOWN_FACES_DIR, tolerance: float = 0.6):
        self.known_encodings, self.known_names = load_known_faces(known_dir)
        self.tolerance = tolerance
        print(f"✅ Loaded {len(self.known_names)} known face(s): {self.known_names}")

    def process_frame(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        faces_result = []

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

            name = "Unknown"
            confidence = 0.0

            if len(self.known_encodings) > 0:
                face_distances = face_recognition.face_distance(
                    self.known_encodings, face_encoding
                )
                best_match = np.argmin(face_distances)
                best_distance = face_distances[best_match]

                if best_distance <= self.tolerance:
                    name = self.known_names[best_match]
                    confidence = round(max(0.0, 1 - best_distance), 2)

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(
                frame, name, (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
            )

            faces_result.append({
                "name": name,
                "confidence": confidence,
                "location": {"top": top, "right": right, "bottom": bottom, "left": left},
            })

        result_dict = {
            "faces_count": len(faces_result),
            "faces": faces_result,
        }

        return frame, result_dict


if __name__ == "__main__":
    processor = FaceRecognitionProcessor()
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, result = processor.process_frame(frame)
        print(result)

        cv2.imshow("Face Recognition Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()