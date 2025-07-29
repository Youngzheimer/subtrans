import os
import json
import subprocess
from utils import log
from processing_status import processing_status

def get_video_files(directory):
    """지정된 디렉토리에서 비디오 파일들을 찾아 반환"""
    video_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                video_files.append(os.path.join(root, file))
    return video_files

def get_subtitle_info(video_path):
    """비디오 파일의 자막 정보를 추출"""
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index:stream_tags=language",
        "-of", "json",
        video_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Error getting subtitle info for {video_path}: {result.stderr})")
        return None
    return result.stdout

def check_existing_target_language(subtitles, target_language):
    """대상 언어 자막이 이미 존재하는지 확인"""
    return any(sub.get('tags', {}).get('language', 'und').lower() == target_language.lower() 
               for sub in subtitles)

def process_video(video_path, config):
    """비디오 파일을 처리하여 자막을 추출하고 번역"""
    try:
        from subtitle_extractor import extract_multiple_subtitles, cleanup_subtitle_files
        from translator import SubtitleTranslator
        import requests
        import json
        import time
        
        log(f"Processing video: {os.path.basename(video_path)}")
        
        # 처리 상태 업데이트 - 서버에 알림
        try:
            # localhost에 상태 업데이트
            url = "http://localhost:8080/api/update_status"
            payload = {
                "filename": video_path,
                "status": "extracting"
            }
            requests.post(url, json=payload)
        except Exception as e:
            log(f"Status update error: {str(e)}")
        
        # 1. 자막 추출
        subtitle_files = extract_multiple_subtitles(
            video_path, 
            config.SUBTITLE_LINE_THRESHOLDS,
            config.SUBTITLE_STREAMS_TO_EXTRACT
        )
        
        if not subtitle_files:
            log(f"No suitable subtitles found in {os.path.basename(video_path)}")
            # 처리 상태 업데이트
            try:
                url = "http://localhost:8080/api/update_status"
                payload = {
                    "filename": video_path,
                    "status": "error",
                    "message": "No suitable subtitles found"
                }
                requests.post(url, json=payload)
            except Exception as e:
                log(f"Status update error: {str(e)}")
            return
        
        # 2. 번역기 초기화
        translator = SubtitleTranslator(config.GEMINI_API_KEY, config.TARGET_LANGUAGE)
        
        # 3. 각 자막 파일에 대해 번역 수행
        total_files = len(subtitle_files)
        
        for i, srt_file in enumerate(subtitle_files):
            try:
                # 처리 상태 업데이트
                try:
                    url = "http://localhost:8080/api/update_status"
                    payload = {
                        "filename": video_path,
                        "status": "translating",
                        "current": i + 1,
                        "total": total_files
                    }
                    requests.post(url, json=payload)
                except Exception as e:
                    log(f"Status update error: {str(e)}")
                
                log(f"Translating subtitle {i+1}/{total_files}: {os.path.basename(srt_file)}")
                translator.translate_and_save_subtitle([srt_file], video_path)
            except Exception as e:
                log(f"Error translating {srt_file}: {str(e)}")
                # 개별 자막 파일 실패는 전체 프로세스를 중단하지 않음
        
        # 4. 임시 파일 정리
        cleanup_subtitle_files(subtitle_files)
        
        # 5. 처리 완료 상태 업데이트
        try:
            url = "http://localhost:8080/api/update_status"
            payload = {
                "filename": video_path,
                "status": "completed"
            }
            requests.post(url, json=payload)
        except Exception as e:
            log(f"Status update error: {str(e)}")
        
        log(f"Completed processing {os.path.basename(video_path)}")
        
    except Exception as e:
        log(f"Error processing video {os.path.basename(video_path)}: {str(e)}")
        # 처리 상태 업데이트
        try:
            url = "http://localhost:8080/api/update_status"
            payload = {
                "filename": video_path,
                "status": "error",
                "message": str(e)
            }
            requests.post(url, json=payload)
        except Exception as status_error:
            log(f"Status update error: {str(status_error)}")
        return
