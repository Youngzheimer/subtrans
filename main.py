import sys
import os

# 현재 디렉토리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import log, Config
import config
from file_watcher import FileWatcher

def main():
    """메인 실행 함수"""
    log("--- Subtitle Translator ---")
    
    # 설정 로드
    config = Config()
    log(f"Watching directory: {config.WATCH_DIRECTORY}")
    log(f"Target language: {config.TARGET_LANGUAGE}")
    log("---------------------------")
    
    # 파일 감시자 초기화 및 실행
    watcher = FileWatcher(config)
    watcher.initialize()
    watcher.watch_and_process()

if __name__ == "__main__":
    main()
