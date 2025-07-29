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
