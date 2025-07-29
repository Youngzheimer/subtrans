#!/usr/bin/env python3
# webui.py - 웹 기반 설정 관리 인터페이스

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from config import config_manager, DEFAULT_CONFIG, BASE_DIR

# Flask 앱 생성
app = Flask(__name__)
CORS(app)  # CORS 설정 - 다른 도메인에서의 요청 허용

# 템플릿 디렉토리 설정
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

# HTML 템플릿 파일 생성
@app.route('/create_templates', methods=['GET'])
def create_templates():
    """템플릿 파일 생성 (개발용)"""
    # index.html 파일 생성
    index_html = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SubTrans 설정</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #2c3e50;
        }
        input[type="text"], input[type="number"], textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        .array-input {
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }
        .array-input input {
            flex-grow: 1;
            margin-right: 10px;
        }
        button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #2980b9;
        }
        .btn-add {
            background-color: #27ae60;
        }
        .btn-add:hover {
            background-color: #2ecc71;
        }
        .btn-remove {
            background-color: #e74c3c;
            padding: 5px 10px;
        }
        .btn-remove:hover {
            background-color: #c0392b;
        }
        .array-items {
            margin-top: 10px;
        }
        .success-message {
            background-color: #dff0d8;
            color: #3c763d;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 20px;
            display: none;
        }
        .section-title {
            margin-top: 20px;
            color: #2c3e50;
            font-weight: bold;
        }
        .setting-description {
            font-size: 14px;
            color: #7f8c8d;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <h1>SubTrans 설정 관리</h1>
    
    <div id="success-message" class="success-message">
        설정이 저장되었습니다.
    </div>

    <div class="container">
        <form id="config-form">
            <!-- 기본 설정 -->
            <h2 class="section-title">기본 설정</h2>
            
            <div class="form-group">
                <label for="WATCH_DIRECTORY">동영상 감시 디렉토리</label>
                <div class="setting-description">동영상 파일을 감시할 디렉토리 경로</div>
                <input type="text" id="WATCH_DIRECTORY" name="WATCH_DIRECTORY">
            </div>
            
            <div class="form-group">
                <label for="TARGET_LANGUAGE">자막 언어</label>
                <div class="setting-description">번역할 대상 언어 코드 (예: ko, en, ja)</div>
                <input type="text" id="TARGET_LANGUAGE" name="TARGET_LANGUAGE">
            </div>
            
            <div class="form-group">
                <label for="GEMINI_API_KEY">Gemini API 키</label>
                <div class="setting-description">Google Gemini API 인증 키</div>
                <input type="text" id="GEMINI_API_KEY" name="GEMINI_API_KEY">
            </div>
            
            <div class="form-group">
                <label for="SCAN_INTERVAL">스캔 간격 (초)</label>
                <div class="setting-description">새로운 파일을 확인하는 주기</div>
                <input type="number" id="SCAN_INTERVAL" name="SCAN_INTERVAL" min="5" step="1">
            </div>
            
            <!-- 자막 추출 설정 -->
            <h2 class="section-title">자막 추출 설정</h2>
            
            <div class="form-group">
                <label for="SUBTITLE_LINE_THRESHOLDS">자막 줄 수 임계값</label>
                <div class="setting-description">자막 줄 수에 따른 임계값 배열</div>
                <div id="SUBTITLE_LINE_THRESHOLDS_inputs" class="array-items"></div>
                <button type="button" class="btn-add" onclick="addArrayItem('SUBTITLE_LINE_THRESHOLDS')">+ 임계값 추가</button>
            </div>
            
            <div class="form-group">
                <label for="SUBTITLE_STREAMS_TO_EXTRACT">최대 추출 자막 수</label>
                <div class="setting-description">각 임계값별 최대 추출할 자막 스트림 수</div>
                <div id="SUBTITLE_STREAMS_TO_EXTRACT_inputs" class="array-items"></div>
                <button type="button" class="btn-add" onclick="addArrayItem('SUBTITLE_STREAMS_TO_EXTRACT')">+ 값 추가</button>
            </div>
            
            <!-- 번역 설정 -->
            <h2 class="section-title">번역 설정</h2>
            
            <div class="form-group">
                <label for="TRANSLATION_CHUNK_SIZE">번역 청크 크기</label>
                <div class="setting-description">한 번에 번역할 자막 수</div>
                <input type="number" id="TRANSLATION_CHUNK_SIZE" name="TRANSLATION_CHUNK_SIZE" min="1" step="1">
            </div>
            
            <div class="form-group">
                <label for="TRANSLATION_MAX_RETRIES">최대 재시도 횟수</label>
                <div class="setting-description">번역 실패 시 최대 재시도 횟수</div>
                <input type="number" id="TRANSLATION_MAX_RETRIES" name="TRANSLATION_MAX_RETRIES" min="1" step="1">
            </div>
            
            <div class="form-group">
                <label for="TRANSLATION_RETRY_BASE_SECONDS">재시도 기본 대기 시간 (초)</label>
                <div class="setting-description">번역 실패 후 재시도하기 전 기본 대기 시간</div>
                <input type="number" id="TRANSLATION_RETRY_BASE_SECONDS" name="TRANSLATION_RETRY_BASE_SECONDS" min="1" step="1">
            </div>
            
            <div class="form-group">
                <label for="TRANSLATION_RETRY_MAX_SECONDS">최대 재시도 대기 시간 (초)</label>
                <div class="setting-description">번역 실패 후 재시도하기 전 최대 대기 시간</div>
                <input type="number" id="TRANSLATION_RETRY_MAX_SECONDS" name="TRANSLATION_RETRY_MAX_SECONDS" min="1" step="1">
            </div>
            
            <button type="submit">설정 저장</button>
            <button type="button" id="reset-btn" style="margin-left: 10px; background-color: #95a5a6;">기본값으로 초기화</button>
        </form>
    </div>

    <script>
        // 배열 항목 추가 함수
        function addArrayItem(id, value='') {
            const container = document.getElementById(`${id}_inputs`);
            const itemCount = container.children.length;
            
            const div = document.createElement('div');
            div.className = 'array-input';
            
            const input = document.createElement('input');
            input.type = 'number';
            input.name = `${id}[${itemCount}]`;
            input.value = value;
            
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn-remove';
            removeBtn.textContent = '제거';
            removeBtn.onclick = function() {
                container.removeChild(div);
                // 인덱스 재정렬
                updateArrayIndices(id);
            };
            
            div.appendChild(input);
            div.appendChild(removeBtn);
            container.appendChild(div);
        }
        
        // 인덱스 재정렬 함수
        function updateArrayIndices(id) {
            const container = document.getElementById(`${id}_inputs`);
            const inputs = container.querySelectorAll('input');
            inputs.forEach((input, index) => {
                input.name = `${id}[${index}]`;
            });
        }
        
        // 페이지 로드 시 설정 로드
        document.addEventListener('DOMContentLoaded', async function() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                
                // 일반 입력 필드 채우기
                for (const [key, value] of Object.entries(config)) {
                    const element = document.getElementById(key);
                    if (element && !Array.isArray(value)) {
                        element.value = value;
                    }
                }
                
                // 배열 입력 필드 채우기
                for (const [key, value] of Object.entries(config)) {
                    if (Array.isArray(value)) {
                        const container = document.getElementById(`${key}_inputs`);
                        if (container) {
                            // 기존 항목 제거
                            container.innerHTML = '';
                            // 새 항목 추가
                            value.forEach(item => {
                                addArrayItem(key, item);
                            });
                        }
                    }
                }
            } catch (error) {
                console.error('설정을 로드하는 중 오류가 발생했습니다:', error);
            }
        });
        
        // 폼 제출 처리
        document.getElementById('config-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = {};
            
            // 일반 필드 처리
            for (const [key, value] of formData.entries()) {
                if (!key.includes('[')) {
                    // 숫자 변환 처리
                    const numValue = Number(value);
                    data[key] = isNaN(numValue) || value === '' ? value : numValue;
                }
            }
            
            // 배열 필드 처리
            const arrayKeys = ['SUBTITLE_LINE_THRESHOLDS', 'SUBTITLE_STREAMS_TO_EXTRACT'];
            arrayKeys.forEach(key => {
                data[key] = [];
                const container = document.getElementById(`${key}_inputs`);
                const inputs = container.querySelectorAll('input');
                inputs.forEach(input => {
                    const value = Number(input.value);
                    if (!isNaN(value)) {
                        data[key].push(value);
                    }
                });
            });
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data),
                });
                
                if (response.ok) {
                    const successMsg = document.getElementById('success-message');
                    successMsg.style.display = 'block';
                    setTimeout(() => {
                        successMsg.style.display = 'none';
                    }, 3000);
                } else {
                    const errorData = await response.json();
                    alert(`오류: ${errorData.error || '알 수 없는 오류가 발생했습니다.'}`);
                }
            } catch (error) {
                console.error('설정을 저장하는 중 오류가 발생했습니다:', error);
                alert('설정을 저장하는 중 오류가 발생했습니다.');
            }
        });
        
        // 초기화 버튼 처리
        document.getElementById('reset-btn').addEventListener('click', async function() {
            if (confirm('모든 설정을 기본값으로 초기화하시겠습니까?')) {
                try {
                    const response = await fetch('/api/config/reset', {
                        method: 'POST',
                    });
                    
                    if (response.ok) {
                        alert('설정이 초기화되었습니다. 페이지를 새로고침합니다.');
                        window.location.reload();
                    } else {
                        const errorData = await response.json();
                        alert(`오류: ${errorData.error || '알 수 없는 오류가 발생했습니다.'}`);
                    }
                } catch (error) {
                    console.error('설정을 초기화하는 중 오류가 발생했습니다:', error);
                    alert('설정을 초기화하는 중 오류가 발생했습니다.');
                }
            }
        });
    </script>
</body>
</html>"""
    
    # 템플릿 디렉토리에 파일 작성
    with open(os.path.join(TEMPLATES_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    return "템플릿이 생성되었습니다."

# 기본 경로 - 웹 UI
@app.route('/')
def index():
    """웹 UI 메인 페이지"""
    return render_template('index.html')

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

# 메인 함수
def main():
    """웹 서버 실행"""
    # 템플릿 디렉토리가 없으면 생성
    if not os.path.exists(os.path.join(TEMPLATES_DIR, 'index.html')):
        create_templates()
    
    # 서버 시작 (도커 환경에서 모든 인터페이스에서 요청 수신)
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == "__main__":
    main()
