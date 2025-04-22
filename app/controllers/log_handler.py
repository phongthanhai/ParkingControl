import requests
import time
from config import SERVER_URL

class LogHandler:
    def __init__(self):
        self.queue = []
    
    def add_log(self, lane, plate, manual=False):
        log = {
            'timestamp': time.time(),
            'lane': lane,
            'plate': plate,
            'manual': manual,
            'status': 'pending'
        }
        self.queue.append(log)
    
    def send_logs(self):
        for log in self.queue:
            try:
                #CALL API TO LOG
                #response = requests.post(SERVER_URL, json=log)
                #Test:
                print(log)
                #if response.ok:
                    #log['status'] = 'sent'
            except Exception:
                pass
    
    def retry_failed(self):
        self.queue = [log for log in self.queue if log['status'] != 'sent']