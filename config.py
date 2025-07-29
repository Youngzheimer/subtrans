# config.py
import os
import sqlite3
import json
import logging

# 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DB_PATH = os.path.join(CONFIG_DIR, "app.db")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# 기본 설정값 정의
DEFAULT_CONFIG = {
    # 기본 경로 설정
    "WATCH_DIRECTORY": "/videos",  # 도커에서 마운트된 볼륨 경로
    "TARGET_LANGUAGE": "ko",       # 기본 한국어로 설정
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),  # 초기값은 환경변수에서 가져옴
    "SCAN_INTERVAL": 30,  # In seconds
    
    # 자막 추출 관련 설정
    "SUBTITLE_LINE_THRESHOLDS": [100, 200, 300],  # 자막 줄 수 임계값
    "SUBTITLE_STREAMS_TO_EXTRACT": [4, 3, 2, 1],  # 각 임계값별 최대 추출 자막 수
    
    # 번역 관련 설정
    "TRANSLATION_CHUNK_SIZE": 10,  # 한 번에 번역할 자막 수
    "TRANSLATION_MAX_RETRIES": 5,  # 번역 재시도 횟수
    "TRANSLATION_RETRY_BASE_SECONDS": 5,  # 재시도 기본 대기 시간 (초)
    "TRANSLATION_RETRY_MAX_SECONDS": 60,  # 최대 재시도 대기 시간 (초)
    "TRANSLATION_GEMINI_MODEL": "gemini-2.5-flash-lite",  # 기본 모델 설정
}

def sync_module_vars():
    """ConfigManager._config의 값을 모듈 전역 변수로 동기화"""
    globals_ = globals()
    for key in DEFAULT_CONFIG.keys():
        globals_[key] = ConfigManager._config.get(key)

class ConfigManager:
    """설정 관리 클래스"""
    _instance = None
    _initialized = False
    _config = {}
    CONFIG_DIR = CONFIG_DIR

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not ConfigManager._initialized:
            self._ensure_config_dir()
            self._init_db()
            self._load_config()
            ConfigManager._initialized = True
    
    def _ensure_config_dir(self):
        """설정 디렉토리 확인 및 생성"""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
            logger.info(f"설정 디렉토리 생성됨: {CONFIG_DIR}")
    
    def _init_db(self):
        """데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 설정 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("데이터베이스 초기화 완료")
        except sqlite3.Error as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
            raise
    
    def _load_config(self):
        """설정 로드"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 데이터베이스에서 설정 로드
            cursor.execute("SELECT key, value FROM config")
            db_config = {key: json.loads(value) for key, value in cursor.fetchall()}
            
            # 기본 설정과 병합
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in db_config:
                    # 데이터베이스에 없는 설정은 기본값 저장
                    self.set(key, default_value)
                    ConfigManager._config[key] = default_value
                else:
                    ConfigManager._config[key] = db_config[key]
            
            conn.close()
            logger.info("설정 로드 완료")
            
            # API 키 검증
            if not self.get("GEMINI_API_KEY"):
                logger.error("GEMINI_API_KEY가 설정되지 않았습니다.")
            
        except sqlite3.Error as e:
            logger.error(f"설정 로드 오류: {e}")
            raise
    
    def get(self, key, default=None):
        """설정 값 가져오기"""
        return ConfigManager._config.get(key, default)
    
    def set(self, key, value):
        """설정 값 설정"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # 설정 저장 또는 업데이트
            cursor.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, json.dumps(value))
            )
            conn.commit()
            conn.close()

            # 메모리 캐시 및 모듈 변수 동기화
            ConfigManager._config[key] = value
            sync_module_vars()
            logger.info(f"설정 업데이트: {key}")
            return True
        except sqlite3.Error as e:
            logger.error(f"설정 저장 오류: {e}")
            return False
    
    def get_all(self):
        """모든 설정 반환"""
        return dict(ConfigManager._config)

# 설정 인스턴스 생성 및 전역 변수로 노출
config_manager = ConfigManager()
sync_module_vars()
