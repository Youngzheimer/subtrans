import os
from datetime import datetime

def log(message):
    """로그 메시지를 타임스탬프와 함께 출력"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class Config:
    """환경 설정 관리 클래스"""
    def __init__(self):
        self.WATCH_DIRECTORY = os.getenv("WATCH_DIRECTORY", "/videos")
        self.TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "en")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))  # In seconds
        
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable not set.")
