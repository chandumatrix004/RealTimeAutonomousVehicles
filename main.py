import numpy as np
import datetime
import cv2
from ultralytics import YOLO
from helper import create_video_writer

from deep_sort.deep_sort.tracker import Tracker
from deep_sort.deep_sort import nn_matching
from deep_sort.deep_sort.detection import Detection
from deep_sort.tools import generate_detections as gdet

# Defining some parameters e.g., Setting prediction confidence threshold
conf_threshold = 0.5
max_cosine_distance = 0.4
nn_budget = None

# Initializing the video capture & the video writer objects for frame extraction & video write back
video_cap = cv2.VideoCapture("street3.mp4")

writer = create_video_writer(video_cap, "output.mp4")
# We 're initializing the YOLO V8 model using the default weights
model = YOLO("yolov8n.pt")

# Here we're initializing the deep sort tracker
model_filename = "config/mars-small128.pb"
encoder = gdet.create_box_encoder(model_filename, batch_size=1)
metric = nn_matching.NearestNeighborDistanceMetric(
    "cosine", max_cosine_distance, nn_budget)
tracker = Tracker(metric)

# Here we're loading the COCO class labels separately on which the YOLO model was trained on
classes_path = "config/coco.names"
with open(classes_path, "r") as f:
    class_names = f.read().strip().split("\n")

# Now Creating a list of random colors to represent each class extracted above
np.random.seed(42)  # to get the same colors
colors = np.random.randint(0, 255, size=(len(class_names), 3))  # (80, 3)

counter = 0
while True:
    # We're starting time to compute the FPS (Frames Per Second)
    start = datetime.datetime.now()
    ret, frame = video_cap.read()
    # If there is no frame, it means we have reached the end of the video
    if not ret:
        print("End of the video file...")
        break

    # Detecting the objects in the frame using the YOLO model
    results = model(frame, stream=True)

    # Loop over the results
    for result in results:
        # Initializing the list of bounding boxes, confidences, and class IDs
        bboxes = []
        confidences = []
        class_ids = []

        # Loop over the detections
        for data in result.boxes.data.tolist():
            x1, y1, x2, y2, confidence, class_id = data
            x = int(x1)
            y = int(y1)
            w = int(x2) - int(x1)
            h = int(y2) - int(y1)
            class_id = int(class_id)

            # Here we're filtering out weak predictions by ensuring the confidence is greater than minimum confidence
            if confidence > conf_threshold:
                bboxes.append([x, y, w, h])
                confidences.append(confidence)
                class_ids.append(class_id)
                # cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # Tracking the objects in the frame using DeepSort

    # Extracting the names of the detected objects from class_names array
    names = [class_names[class_id] for class_id in class_ids]

    # Extracting the features of the detected objects
    features = encoder(frame, bboxes)
    # converting the detections to deep sort format
    dets = []
    for bbox, conf, class_name, feature in zip(bboxes, confidences, names, features):
        dets.append(Detection(bbox, conf, class_name, feature))

    # Here we're the tracker on the detections
    tracker.predict()
    tracker.update(dets)

    # Looping over the tracked objects
    for track in tracker.tracks:
        if not track.is_confirmed() or track.time_since_update > 1:
            continue

        # Here we're getting the bounding box of the object, the name of the object, and the track id
        bbox = track.to_tlbr()
        track_id = track.track_id
        class_name = track.get_class()
        # Converting the bounding box to integers
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Extracting the color associated with the class name
        class_id = class_names.index(class_name)
        color = colors[class_id]
        B, G, R = int(color[0]), int(color[1]), int(color[2])

        # Drawing the bounding box of the object, the name of the predicted object, and the track id
        text = "ID: " + str(track_id) + " - " + class_name
        cv2.rectangle(frame, (x1, y1), (x2, y2), (B, G, R), 2)
        cv2.rectangle(frame, (x1 - 1, y1 - 20),
                      (x1 + len(text) * 12, y1), (B, G, R), -1)
        cv2.putText(frame, text, (x1 + 5, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Performing some post-processing to display the results

    # Ending the time to compute the fps
    end = datetime.datetime.now()
    # Calculation of the FPS (Frame Per Second) and draw it on the frame
    fps = f"FPS: {1 / (end - start).total_seconds():.2f}"
    cv2.putText(frame, fps, (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 8)

    # Showing each output frame
    cv2.imshow("Output", frame)
    # Writing each frame to the disk
    writer.write(frame)
    if cv2.waitKey(1) == ord("q"):
        break

# Here we're releasing the video capture object, video writer, and closing all windows
video_cap.release()
writer.release()
cv2.destroyAllWindows()
