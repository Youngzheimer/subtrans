#!/usr/bin/env python3
# webui.py - 웹 기반 설정 관리 인터페이스

import os
import json
import queue
import time
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_cors import CORS
from config import config_manager, DEFAULT_CONFIG, BASE_DIR
from processing_status import ProcessingStatus

# Flask 앱 생성
app = Flask(__name__, template_folder='templates')
CORS(app)  # CORS 설정 - 다른 도메인에서의 요청 허용

# 템플릿 디렉토리 설정
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# 처리 상태를 저장하는 딕셔너리 - SSE 이벤트를 위한 것
processing_videos = {}

# 처리 상태 업데이트 함수
def update_processing_status(filename, status, current=0, total=0):
    """처리 상태를 업데이트"""
    video_id = filename.replace('/', '_').replace('\\', '_')
    
    if status == 'completed' or status == 'error':
        # 완료 또는 오류 상태는 30초 후에 목록에서 제거
        processing_videos[video_id] = {
            'id': video_id,
            'filename': os.path.basename(filename),
            'status': status,
            'current': current,
            'total': total,
            'remove_at': time.time() + 30
        }
    else:
        processing_videos[video_id] = {
            'id': video_id,
            'filename': os.path.basename(filename),
            'status': status,
            'current': current,
            'total': total
        }

# 기본 경로 - 웹 UI 메인 페이지
@app.route('/')
def index():
    """웹 UI 메인 페이지"""
    return render_template('index.html')

# 설정 페이지 경로
@app.route('/config')
def config():
    """설정 페이지"""
    return render_template('config.html')

# API 엔드포인트 - 모든 설정 가져오기
@app.route('/api/config', methods=['GET'])
def get_config():
    """모든 설정을 JSON으로 반환"""
    return jsonify(config_manager.get_all())

# API 엔드포인트 - 설정 업데이트
@app.route('/api/config', methods=['POST'])
def update_config():
    """설정 업데이트"""
    data = request.json
    
    if not data:
        return jsonify({'error': '유효하지 않은 요청입니다.'}), 400
    
    # 모든 설정 업데이트
    success = True
    for key, value in data.items():
        if key in DEFAULT_CONFIG:
            if not config_manager.set(key, value):
                success = False
    
    if success:
        return jsonify({'message': '설정이 업데이트되었습니다.'}), 200
    else:
        return jsonify({'error': '일부 설정을 업데이트하는 중 오류가 발생했습니다.'}), 500

# API 엔드포인트 - 설정 초기화
@app.route('/api/config/reset', methods=['POST'])
def reset_config():
    """모든 설정을 기본값으로 초기화"""
    success = True
    
    for key, value in DEFAULT_CONFIG.items():
        if not config_manager.set(key, value):
            success = False
    
    if success:
        return jsonify({'message': '모든 설정이 초기화되었습니다.'}), 200
    else:
        return jsonify({'error': '일부 설정을 초기화하는 중 오류가 발생했습니다.'}), 500

# 비디오 처리 상태를 제공하는 SSE 엔드포인트
@app.route('/api/status')
def status_stream():
    """비디오 처리 상태 SSE 스트림"""
    def generate():
        last_update = time.time()
        
        while True:
            # 오래된 완료/오류 항목 제거
            current_time = time.time()
            to_remove = []
            for video_id, video_info in processing_videos.items():
                if 'remove_at' in video_info and current_time > video_info['remove_at']:
                    to_remove.append(video_id)
            
            for video_id in to_remove:
                processing_videos.pop(video_id, None)
            
            # 클라이언트에 전송할 데이터 생성
            data = {
                'videos': list(processing_videos.values()),
                'timestamp': current_time
            }
            
            # 15초마다 클라이언트 연결 유지를 위한 메시지 전송
            if current_time - last_update >= 15:
                last_update = current_time
            
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')

# 처리 상태 업데이트 API 엔드포인트 (처리 모듈에서 호출)
@app.route('/api/update_status', methods=['POST'])
def api_update_status():
    """처리 상태 업데이트 API"""
    data = request.json
    
    if not data or 'filename' not in data or 'status' not in data:
        return jsonify({'error': '필수 필드가 누락되었습니다.'}), 400
    
    filename = data['filename']
    status = data['status']
    current = data.get('current', 0)
    total = data.get('total', 0)
    
    update_processing_status(filename, status, current, total)
    return jsonify({'success': True})

# 메인 함수
def main():
    """웹 서버 실행"""
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == "__main__":
    main()
