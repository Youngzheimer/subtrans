#!/usr/bin/env python3
# start.py - 웹 UI와 메인 프로세스를 함께 실행

import os
import sys
import threading
import time
import subprocess
import logging
import webui
from config import config_manager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def run_main_process():
    """메인 프로세스 실행"""
    logger.info("메인 프로세스 시작...")
    try:
        import main
        main.main()
    except Exception as e:
        logger.error(f"메인 프로세스 오류: {e}")

def run_web_ui():
    """웹 UI 실행"""
    logger.info("웹 UI 시작...")
    try:
        webui.app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"웹 UI 오류: {e}")

def main():
    """시작 함수"""
    # 설정 디렉토리 초기화
    if not os.path.exists(config_manager.CONFIG_DIR):
        os.makedirs(config_manager.CONFIG_DIR)
    
    # 웹 UI 템플릿 디렉토리 확인
    if not os.path.exists(webui.TEMPLATES_DIR):
        os.makedirs(webui.TEMPLATES_DIR)
    
    # 웹 UI 스레드 시작
    web_thread = threading.Thread(target=run_web_ui, daemon=True)
    web_thread.start()
    logger.info("웹 UI 시작됨: http://localhost:8080")
    
    # 메인 프로세스 시작 (별도 스레드)
    main_thread = threading.Thread(target=run_main_process)
    main_thread.start()
    
    try:
        # 메인 스레드가 종료될 때까지 대기
        while main_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("프로그램 종료 요청됨...")
    
    logger.info("프로그램 종료")

if __name__ == "__main__":
    main()
