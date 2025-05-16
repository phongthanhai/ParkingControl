import cv2
import numpy as np
import onnxruntime as ort
import threading
from threading import Lock
import time
import os
from config import MODEL_PATH, INPUT_SIZE, CONFIDENCE_THRESHOLD

class PlateDetector:
    _instance = None
    _lock = Lock()
    
    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = PlateDetector()
            return cls._instance
    
    def __init__(self):
        self.model_path = MODEL_PATH
        self.input_size = INPUT_SIZE
        self.confidence_threshold = CONFIDENCE_THRESHOLD
        
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        self.session_lock = Lock()
        self.processing_lock = Lock()
        
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = 2
        
        try:
            self.session = ort.InferenceSession(self.model_path, sess_options=session_options)
            self.input_name = self.session.get_inputs()[0].name
            self.empty_frame = np.zeros((INPUT_SIZE[1], INPUT_SIZE[0], 3), dtype=np.uint8)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ONNX model: {str(e)}")
    
    def detect(self, frame):
        if frame is None:
            return self.empty_frame, None
            
        working_frame = frame.copy()
        
        try:
            with self.processing_lock:
                display_img = cv2.resize(working_frame, self.input_size)
                
                input_tensor = np.expand_dims(
                    display_img.transpose(2, 0, 1).astype(np.float32) / 255.0,
                    axis=0
                )
                
                with self.session_lock:
                    start_time = time.time()
                    outputs = self.session.run(None, {self.input_name: input_tensor})
                    inference_time = time.time() - start_time
                
                boxes = outputs[0][0]
                
                if boxes.shape[0] == 0:
                    return display_img, None
                
                max_conf_idx = np.argmax(boxes[:, 4])
                confidence = boxes[max_conf_idx, 4]
                
                if confidence > self.confidence_threshold:
                    x1, y1, x2, y2 = map(int, boxes[max_conf_idx, :4])
                    
                    h, w = working_frame.shape[:2]
                    scale_x, scale_y = w / self.input_size[0], h / self.input_size[1]
                    
                    x1_scaled = max(0, int(x1 * scale_x))
                    y1_scaled = max(0, int(y1 * scale_y))
                    x2_scaled = min(w - 1, int(x2 * scale_x))
                    y2_scaled = min(h - 1, int(y2 * scale_y))
                    
                    if x2_scaled > x1_scaled and y2_scaled > y1_scaled:
                        cropped = working_frame[y1_scaled:y2_scaled, x1_scaled:x2_scaled]
                        
                        cv2.rectangle(display_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        conf_text = f"{confidence:.2f}"
                        cv2.putText(display_img, conf_text, (x1, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        
                        return display_img, cropped
            
            return display_img, None
            
        except Exception as e:
            return self.empty_frame, None
    
    def __del__(self):
        pass