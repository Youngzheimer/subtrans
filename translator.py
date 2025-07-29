import os
import time
import srt
import config
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from utils import log, Config
from subtitle_extractor import extract_subtitle_lines
from processing_status import processing_status

class SubtitleTranslator:
    """Gemini API를 사용한 자막 번역 클래스"""
    
    def __init__(self, api_key, target_language):
        self.target_language = target_language
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(config.TRANSLATION_GEMINI_MODEL)
    
    def translate_and_save_subtitle(self, subtitle_paths, video_path):
        """자막을 번역하고 저장"""
        if not subtitle_paths:
            log("No subtitle files provided. Skipping translation.")
            processing_status.error(video_path)
            return
            
        try:
            # Parse the first subtitle file for SRT structure
            with open(subtitle_paths[0], 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f.read()))
            
            if not subs:
                log(f"No subtitles found in {subtitle_paths[0]}. Skipping translation.")
                processing_status.error(video_path)
                return
                
            # 자막 줄 추출 (첫 번째 자막 파일에서)
            subtitle_lines = extract_subtitle_lines(subtitle_paths[0])
            
            if not subtitle_lines:
                log(f"No subtitle lines could be extracted from {subtitle_paths[0]}. Skipping translation.")
                processing_status.error(video_path)
                return
                
            # 번역 시작 상태 업데이트
            processing_status.start_translating(video_path, len(subtitle_lines))
                
            # 줄 단위로 번역
            translated_lines = self._translate_subtitle_lines(subtitle_lines, video_path)
            
            # 번역된 줄들을 원본 자막 구조에 적용
            translated_subtitles = self._apply_translations_to_subtitles(subs, translated_lines)
            
            # 번역된 자막 저장
            self._save_translated_subtitles(translated_subtitles, video_path)
            
            # 번역 완료 상태 업데이트
            processing_status.complete(video_path)
            
        except Exception as e:
            log(f"Error translating or saving subtitle for {video_path}: {e}")
            processing_status.error(video_path)
    
    def _translate_subtitle_lines(self, subtitle_lines, video_path):
        """자막 줄 목록을 번역"""
        config_obj = Config()
        total_lines = len(subtitle_lines)
        translated_lines = []
        chunk_size = config_obj.TRANSLATION_CHUNK_SIZE
        
        for i in range(0, total_lines, chunk_size):
            chunk = subtitle_lines[i:i + chunk_size]
            translated_chunk = self._translate_line_chunk(chunk, video_path, i)
            
            if translated_chunk:
                translated_lines.extend(translated_chunk)
            
            # 진행 상황 업데이트 (로그 및 웹 UI)
            progress = min(i + len(chunk), total_lines)
            processing_status.update_translation_progress(video_path, progress, total_lines)
            
            progress_percent = (progress / total_lines * 100)
            log(f"Translation progress for {os.path.basename(video_path)}: {progress_percent:.2f}% "
                f"({progress}/{total_lines} lines translated)")
        
        return translated_lines
        
    def _translate_line_chunk(self, chunk_lines, video_path, chunk_index):
        """자막 줄 청크를 번역"""
        config_obj = Config()
        
        # 줄 목록을 하나의 문자열로 변환 (각 줄은 번호가 매겨짐)
        chunk_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(chunk_lines)])
        prompt = self._create_line_translation_prompt(chunk_text)
        
        retries = config_obj.TRANSLATION_MAX_RETRIES
        for attempt in range(retries):
            try:
                response = self.model.generate_content(prompt)
                translated_text = self._clean_response(response.text)
                
                # 번역된 텍스트에서 줄 단위로 파싱
                translated_lines = self._parse_translated_lines(translated_text, len(chunk_lines))
                if len(translated_lines) != len(chunk_lines):
                    log(f"Warning: Number of translated lines ({len(translated_lines)}) " 
                        f"does not match original ({len(chunk_lines)}). Using what we have.")
                
                return translated_lines
                
            except ResourceExhausted as e:
                wait_time = min(config_obj.TRANSLATION_RETRY_MAX_SECONDS, 
                               2**(attempt+1) * config_obj.TRANSLATION_RETRY_BASE_SECONDS)
                log(f"Quota exceeded for {video_path} (chunk {chunk_index}-{chunk_index+len(chunk_lines)}). "
                    f"Retrying in {wait_time} seconds... ({e})")
                time.sleep(wait_time)
                
            except Exception as e:
                log(f"Error generating content for {video_path} "
                    f"(chunk {chunk_index}-{chunk_index+len(chunk_lines)}): {e}")
                break
        
        log(f"Failed to translate chunk {chunk_index}-{chunk_index+len(chunk_lines)} "
            f"for {video_path} after {retries} retries.")
        return []
        
    def _parse_translated_lines(self, translated_text, expected_count):
        """번역된 텍스트에서 줄 목록으로 파싱"""
        lines = []
        for line in translated_text.split('\n'):
            # 번호 접두사(예: "1. ", "2. " 등) 제거
            parts = line.split('. ', 1)
            if len(parts) > 1 and parts[0].isdigit():
                lines.append(parts[1])
            else:
                # 번호 접두사가 없는 경우 그냥 추가
                lines.append(line)
                
        # 기대한 줄 수와 일치하도록 조정
        if len(lines) < expected_count:
            # 부족한 줄은 빈 줄로 채움
            lines.extend([''] * (expected_count - len(lines)))
        elif len(lines) > expected_count:
            # 초과 줄은 버림
            lines = lines[:expected_count]
            
        return lines
        
    def _apply_translations_to_subtitles(self, original_subs, translated_lines):
        """번역된 줄들을 원본 자막 구조에 적용"""
        translated_subs = []
        
        for i, sub in enumerate(original_subs):
            if i < len(translated_lines):
                # 새로운 자막 객체 생성
                new_sub = srt.Subtitle(
                    index=sub.index,
                    start=sub.start,
                    end=sub.end,
                    content=translated_lines[i]
                )
                translated_subs.append(new_sub)
            else:
                # 번역된 줄이 부족하면 원본 자막 유지
                translated_subs.append(sub)
                
        return translated_subs
        
    def _create_line_translation_prompt(self, chunk_text):
        """줄 단위 번역을 위한 프롬프트 생성"""
        return (
            f"You are an expert translator specializing in subtitles for movies, TV, and animation. "
            f"Your task is to translate the provided subtitle lines into {self.target_language}, "
            f"making them sound as natural as possible, as if they were originally written in {self.target_language}.\n\n"
            "Follow these instructions carefully:\n"
            "1. **Natural Translation:** The translation must be fluent and natural. Avoid stiff, literal translations.\n"
            "2. **Completeness:** It is absolutely critical that you translate every line. Do not omit any lines.\n"
            "3. **Formatting:** Keep the line number prefix (e.g., '1. ', '2. ') in your response.\n"
            "4. **Preserve Formatting Tags:** Preserve any formatting tags such as <i>, <b>, etc.\n"
            "5. **Output Format:** Your response should be ONLY the numbered translated lines, one per line.\n\n"
            "Here are the subtitle lines to translate:\n\n"
            f"{chunk_text}"
        )
    
    def _clean_response(self, response_text):
        """응답에서 마크다운 포맷팅 제거"""
        cleaned = response_text.strip()
        if cleaned.startswith("```srt"):
            cleaned = cleaned[6:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        return cleaned
    
    def _save_translated_subtitles(self, translated_subtitles, video_path):
        """번역된 자막을 파일로 저장"""
        final_translated_srt = srt.compose(translated_subtitles)
        output_path = f"{os.path.splitext(video_path)[0]}.{self.target_language}.srt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_translated_srt)
        log(f"Translated subtitle saved to {output_path}")
    
    def _clean_response(self, response_text):
        """응답에서 마크다운 포맷팅 제거"""
        cleaned = response_text.strip()
        if cleaned.startswith("```srt"):
            cleaned = cleaned[6:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        return cleaned
    
    def _save_translated_subtitles(self, translated_subtitles, video_path):
        """번역된 자막을 파일로 저장"""
        final_translated_srt = srt.compose(translated_subtitles)
        output_path = f"{os.path.splitext(video_path)[0]}.{self.target_language}.srt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_translated_srt)
        log(f"Translated subtitle saved to {output_path}")
