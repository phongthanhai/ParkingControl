import time
import requests
from io import BytesIO
import cv2
from config import PLATE_RECOGNIZER_API_KEY, PLATE_RECOGNIZER_URL, OCR_RATE_LIMIT

class PlateRecognizer:
    def __init__(self):
        self.last_call = 0

    def process(self, image):
        """Returns plate text or None"""
        if time.time() - self.last_call < OCR_RATE_LIMIT:
            return None
            
        _, img_encoded = cv2.imencode('.jpg', image)
        img_bytes = BytesIO(img_encoded.tobytes())
        
        try:
            response = requests.post(
                PLATE_RECOGNIZER_URL,
                files={'upload': img_bytes},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'},
                timeout=5
            )
            if response.status_code == 201:
                results = response.json()
                if results['results']:
                    self.last_call = time.time()
                    return results['results'][0]['plate']
        except Exception:
            pass
        return None