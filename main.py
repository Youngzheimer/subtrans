from utils import log, Config
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
