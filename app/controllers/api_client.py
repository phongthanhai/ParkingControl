import time
import requests
from io import BytesIO
import cv2
from PyQt5.QtCore import pyqtSignal, QObject
from config import PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT

class PlateRecognizer(QObject):
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.last_call = 0

    def process(self, image):
        """Returns plate text or None"""
        try:
            if time.time() - self.last_call < OCR_RATE_LIMIT:
                return None
                
            _, img_encoded = cv2.imencode('.jpg', image)
            img_bytes = BytesIO(img_encoded.tobytes())
            
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=5
            )
            
            if response.status_code == 429:
                self.error_signal.emit("API rate limit exceeded")
                return None
                
            if response.status_code == 201:
                results = response.json()
                if results['results']:
                    self.last_call = time.time()
                    return results['results'][0]['plate']
        except requests.exceptions.RequestException as e:
            self.error_signal.emit(f"Connection error: {str(e)}")
        except Exception as e:
            self.error_signal.emit(f"Processing error: {str(e)}")
        return None