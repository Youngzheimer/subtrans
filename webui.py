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
from utils import Config

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
    # ETA 지원: 요청에서 eta가 있으면 반영
    eta = None
    if hasattr(request, 'json') and request.json:
        eta = request.json.get('eta')
    elif isinstance(request, dict):
        eta = request.get('eta')

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
        video_info = {
            'id': video_id,
            'filename': os.path.basename(filename),
            'status': status,
            'current': current,
            'total': total
        }
        if eta is not None:
            video_info['eta'] = eta
        processing_videos[video_id] = video_info

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

# 모니터링 폴더 브라우징 API 엔드포인트
@app.route('/api/browse', methods=['GET'])
def browse_directory():
    """모니터링 폴더 브라우징 API"""
    # 현재 설정된 감시 디렉토리 가져오기
    config = Config()
    watch_dir = config.WATCH_DIRECTORY
    
    # 서브 디렉토리 경로 (query parameter로 받음)
    subdir = request.args.get('path', '')
    
    # 전체 경로 구성
    current_path = os.path.normpath(os.path.join(watch_dir, subdir))
    
    # 보안을 위해 watch_dir 밖으로 나가지 못하도록 체크
    if not current_path.startswith(watch_dir):
        return jsonify({'error': '유효하지 않은 경로입니다.'}), 400
    
    # 디렉토리가 존재하는지 확인
    if not os.path.exists(current_path) or not os.path.isdir(current_path):
        return jsonify({'error': '디렉토리를 찾을 수 없습니다.'}), 404
    
    try:
        items = []
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            is_dir = os.path.isdir(item_path)
            relative_path = os.path.relpath(item_path, watch_dir)
            
            # 숨김 파일 및 폴더 제외
            if item.startswith('.'):
                continue
                
            # 항목 정보 추가
            item_info = {
                'name': item,
                'path': relative_path.replace('\\', '/'),  # Windows 경로 처리
                'type': 'directory' if is_dir else 'file',
                'size': os.path.getsize(item_path) if not is_dir else 0,
                'modified': os.path.getmtime(item_path)
            }
            
            # 파일 확장자 추가 (파일인 경우)
            if not is_dir:
                _, ext = os.path.splitext(item)
                item_info['extension'] = ext.lower()
                
            items.append(item_info)
            
        # 결과 반환
        return jsonify({
            'current_path': subdir,
            'items': sorted(items, key=lambda x: (0 if x['type'] == 'directory' else 1, x['name'].lower()))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API 엔드포인트 - 영상 파일 번역 시작
@app.route('/api/translate', methods=['POST'])
def start_translation():
    """영상 파일 번역 시작 API"""
    data = request.json
    
    if not data or 'filepath' not in data:
        return jsonify({'error': '유효하지 않은 요청입니다.'}), 400
    
    filepath = data['filepath']
    config = Config()
    watch_dir = config.WATCH_DIRECTORY
    
    # 전체 경로 구성
    full_path = os.path.normpath(os.path.join(watch_dir, filepath))
    
    # 보안을 위해 watch_dir 밖으로 나가지 못하도록 체크
    if not full_path.startswith(watch_dir):
        return jsonify({'error': '유효하지 않은 경로입니다.'}), 400
    
    # 파일이 존재하는지 확인
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
    
    # 파일 확장자 확인
    _, ext = os.path.splitext(full_path)
    if ext.lower() not in ['.mkv', '.mp4', '.mov', '.avi']:
        return jsonify({'error': '지원하지 않는 파일 형식입니다.'}), 400
    
    try:
        # 처리 상태 생성
        update_processing_status(full_path, 'queued')
        
        # 여기서 실제 처리를 시작하는 로직을 추가
        # 백그라운드 작업으로 처리하거나 파일을 처리 큐에 추가
        from video_processor import process_video
        import threading
        
        # 비동기적으로 비디오 처리 시작
        thread = threading.Thread(target=process_video, args=(full_path, Config()))
        thread.daemon = True
        thread.start()
        
        return jsonify({'message': '번역이 시작되었습니다.', 'filename': os.path.basename(full_path)}), 200
    except Exception as e:
        update_processing_status(full_path, 'error')
        return jsonify({'error': str(e)}), 500

# 브라우저 페이지 라우트
@app.route('/browse')
def browse_page():
    """폴더 브라우징 페이지"""
    return render_template('browse.html')

# 메인 함수
def main():
    """웹 서버 실행"""
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == "__main__":
    main()
