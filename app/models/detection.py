import cv2
import numpy as np
import onnxruntime as ort
from threading import Lock
from config import MODEL_PATH, INPUT_SIZE, CONFIDENCE_THRESHOLD

class PlateDetector:
    def __init__(self):
        self.session = ort.InferenceSession(MODEL_PATH)
        self.input_name = self.session.get_inputs()[0].name
        self.lock = Lock()

    def detect(self, frame):
        """Returns (display_frame, cropped_plate)"""
        display_img = cv2.resize(frame, INPUT_SIZE)
        input_tensor = np.expand_dims(
            display_img.transpose(2,0,1).astype(np.float32)/255.0, 
            axis=0
        )
        
        with self.lock:
            outputs = self.session.run(None, {self.input_name: input_tensor})
        
        boxes = outputs[0][0]
        if boxes.shape[0] == 0:
            return display_img, None
        
        max_conf_idx = np.argmax(boxes[:, 4])
        if boxes[max_conf_idx, 4] > CONFIDENCE_THRESHOLD:
            x1, y1, x2, y2 = map(int, boxes[max_conf_idx, :4])
            h, w = frame.shape[:2]
            scale_x, scale_y = w/INPUT_SIZE[0], h/INPUT_SIZE[1]
            cropped = frame[
                int(y1*scale_y):int(y2*scale_y),
                int(x1*scale_x):int(x2*scale_x)
            ]
            cv2.rectangle(display_img, (x1,y1), (x2,y2), (0,255,0), 2)
            return display_img, cropped
        
        return display_img, None