#!/usr/bin/env python3
# processing_status.py - 비디오 처리 상태를 관리하는 모듈

import os
import json
import time
import requests
from threading import Lock

class ProcessingStatus:
    """비디오 처리 상태를 관리하는 클래스
    
    이 클래스는 비디오 처리 진행 상황을 추적하고 웹 UI에 상태를 전송합니다.
    각 비디오 파일의 처리 단계, 진행률 등을 관리합니다.
    ETA(예상 완료 시간) 계산 기능 포함.
    """

    def __init__(self, webui_url="http://localhost:8080"):
        """초기화
        
        Args:
            webui_url (str): 웹 UI 서버 URL
        """
        self.webui_url = webui_url
        self.lock = Lock()  # 스레드 안전성 보장을 위한 락
        self._progress_info = {}  # 파일별 진행 정보: {filename: {start_time, last_time, last_current, total}}
    
    def update_status(self, filename, status, current=0, total=0, eta=None):
        """처리 상태 업데이트
        
        비디오 파일의 처리 상태를 업데이트하고 웹 UI에 전송합니다.
        ETA(초)도 함께 전송할 수 있습니다.
        """
        try:
            data = {
                'filename': filename,
                'status': status,
                'current': current,
                'total': total,
                'timestamp': time.time()
            }
            if eta is not None:
                data['eta'] = eta

            response = requests.post(
                f"{self.webui_url}/api/update_status",
                json=data,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"상태 업데이트 중 오류 발생: {e}")
            return False
    
    def start_extracting(self, filename):
        """자막 추출 시작
        Args:
            filename (str): 비디오 파일 경로
        """
        # 추출 단계에서는 ETA 필요 없음, 진행 정보 초기화
        self._progress_info.pop(filename, None)
        return self.update_status(filename, 'extracting')
    
    def start_translating(self, filename, total_subtitles):
        """번역 시작
        Args:
            filename (str): 비디오 파일 경로
            total_subtitles (int): 총 자막 수
        """
        now = time.time()
        self._progress_info[filename] = {
            'start_time': now,
            'last_time': now,
            'last_current': 0,
            'total': total_subtitles
        }
        return self.update_status(filename, 'translating', 0, total_subtitles, eta=None)
    
    def update_translation_progress(self, filename, current, total):
        """번역 진행 상태 업데이트 및 ETA 계산
        Args:
            filename (str): 비디오 파일 경로
            current (int): 현재까지 번역된 자막 수
            total (int): 총 자막 수
        Returns:
            bool: 업데이트 성공 여부
        """
        eta = None
        info = self._progress_info.get(filename)
        now = time.time()
        if info and current > 0 and total > 0 and current <= total:
            elapsed = now - info['start_time']
            progress = current / total
            if progress > 0:
                eta = int(elapsed * (1 - progress) / progress)
            # 진행 정보 갱신
            info['last_time'] = now
            info['last_current'] = current
        return self.update_status(filename, 'translating', current, total, eta=eta)
    
    def complete(self, filename):
        """처리 완료
        Args:
            filename (str): 비디오 파일 경로
        """
        self._progress_info.pop(filename, None)
        return self.update_status(filename, 'completed')
    
    def error(self, filename):
        """처리 오류
        Args:
            filename (str): 비디오 파일 경로
        """
        self._progress_info.pop(filename, None)
        return self.update_status(filename, 'error')

# 글로벌 인스턴스 생성
processing_status = ProcessingStatus()
