import os
import time
import json
from utils import log
from video_processor import get_video_files, get_subtitle_info, check_existing_target_language
from subtitle_extractor import extract_multiple_subtitles, cleanup_subtitle_files
from translator import SubtitleTranslator

class FileWatcher:
    """파일 감시 및 처리를 담당하는 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.translator = SubtitleTranslator(config.GEMINI_API_KEY, config.TARGET_LANGUAGE)
        self.last_scanned_files = set()
    
    def initialize(self):
        """초기 스캔을 수행하여 기존 파일들을 등록"""
        self.last_scanned_files = set(get_video_files(self.config.WATCH_DIRECTORY))
        if self.last_scanned_files:
            log(f"Initial scan complete. Found {len(self.last_scanned_files)} existing video files. These will be ignored.")
            for f in self.last_scanned_files:
                log(f"  - Ignoring: {os.path.basename(f)}")
        else:
            log("Initial scan complete. No existing video files found.")
    
    def watch_and_process(self):
        """파일을 감시하고 새로운 파일을 처리"""
        log(f"\nStarting to watch for new files. Scanning every {self.config.SCAN_INTERVAL} seconds...")
        
        while True:
            current_files = set(get_video_files(self.config.WATCH_DIRECTORY))
            new_files = current_files - self.last_scanned_files
            removed_files = self.last_scanned_files - current_files
            
            if new_files:
                self._process_new_files(new_files)
            
            if removed_files:
                self._log_removed_files(removed_files)
            
            self.last_scanned_files = current_files
            time.sleep(self.config.SCAN_INTERVAL)
    
    def _process_new_files(self, new_files):
        """새로운 파일들을 처리"""
        log(f"\nDetected {len(new_files)} new video file(s). Processing...")
        for video_file in new_files:
            self._process_single_video(video_file)
    
    def _process_single_video(self, video_file):
        """개별 비디오 파일을 처리"""
        log(f"--- Processing: {os.path.basename(video_file)} ---")
        try:
            # 자막 정보 가져오기
            subtitle_info_str = get_subtitle_info(video_file)
            if not subtitle_info_str:
                log(f"Could not retrieve subtitle information for {video_file}. Skipping.")
                return
            
            subtitle_info = json.loads(subtitle_info_str)
            subtitles = subtitle_info.get('streams', [])
            
            if not subtitles:
                log("No subtitle streams found. Skipping.")
                return
            
            # 타겟 언어 자막이 이미 존재하는지 확인
            if check_existing_target_language(subtitles, self.config.TARGET_LANGUAGE):
                log(f"Target language '{self.config.TARGET_LANGUAGE}' subtitle already exists. Skipping.")
                return
            
            # 자막 추출
            extracted_subtitle_paths = extract_multiple_subtitles(video_file, subtitles)
            
            if extracted_subtitle_paths:
                # 번역 및 저장
                self.translator.translate_and_save_subtitle(extracted_subtitle_paths, video_file)
                # 임시 파일 정리
                cleanup_subtitle_files(extracted_subtitle_paths)
            else:
                log("Failed to extract any valid subtitle streams for translation. Skipping.")
        
        except json.JSONDecodeError:
            log(f"Error parsing subtitle information for {video_file}. It might not be valid JSON. Skipping.")
        except Exception as e:
            log(f"An unexpected error occurred while processing {video_file}: {e}")
        finally:
            log(f"--- Finished processing: {os.path.basename(video_file)} ---\n")
    
    def _log_removed_files(self, removed_files):
        """제거된 파일들을 로깅"""
        log(f"\nDetected {len(removed_files)} removed video file(s).")
        for video_file in removed_files:
            log(f"  - Removed: {os.path.basename(video_file)}")
