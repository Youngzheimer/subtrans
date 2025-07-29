from datetime import datetime
from config import config_manager

def log(message):
    """로그 메시지를 타임스탬프와 함께 출력"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class Config:
    """환경 설정 관리 클래스"""
    def __init__(self):
        # config_manager에서 설정 가져오기
        self.WATCH_DIRECTORY = config_manager.get("WATCH_DIRECTORY")
        self.TARGET_LANGUAGE = config_manager.get("TARGET_LANGUAGE")
        self.GEMINI_API_KEY = config_manager.get("GEMINI_API_KEY")
        self.SCAN_INTERVAL = config_manager.get("SCAN_INTERVAL")
        
        # 자막 추출 관련 설정
        self.SUBTITLE_LINE_THRESHOLDS = config_manager.get("SUBTITLE_LINE_THRESHOLDS")
        self.SUBTITLE_STREAMS_TO_EXTRACT = config_manager.get("SUBTITLE_STREAMS_TO_EXTRACT")
        
        # 번역 관련 설정
        self.TRANSLATION_CHUNK_SIZE = config_manager.get("TRANSLATION_CHUNK_SIZE")
        self.TRANSLATION_MAX_RETRIES = config_manager.get("TRANSLATION_MAX_RETRIES")
        self.TRANSLATION_RETRY_BASE_SECONDS = config_manager.get("TRANSLATION_RETRY_BASE_SECONDS")
        self.TRANSLATION_RETRY_MAX_SECONDS = config_manager.get("TRANSLATION_RETRY_MAX_SECONDS")
    
    def update_config(self, key, value):
        """설정 값 업데이트"""
        result = config_manager.set(key, value)
        if result:
            # 인스턴스 변수도 업데이트
            setattr(self, key, value)
        return result
    
    def get_all_config(self):
        """모든 설정 반환"""
        return config_manager.get_all()
