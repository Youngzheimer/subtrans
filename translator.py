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
            # SRT 파일 인코딩 자동 탐지 및 파싱
            subtitle_path = subtitle_paths[0]
            log(f"자막 파일 읽기: {os.path.basename(subtitle_path)}")
            
            # 다양한 인코딩으로 시도
            encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'euc-kr', 'latin1']
            subs = None
            
            for encoding in encodings:
                try:
                    with open(subtitle_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        subs = list(srt.parse(content))
                    log(f"자막 파일을 {encoding} 인코딩으로 성공적으로 읽었습니다.")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    log(f"SRT 파싱 오류 ({encoding}): {e}")
                    continue
            
            if not subs:
                log(f"지원되는 인코딩으로 자막 파일을 읽을 수 없습니다: {subtitle_path}")
                processing_status.error(video_path)
                return
            
            log(f"총 {len(subs)}개의 자막 항목이 발견되었습니다.")
            
            if not subs:
                log(f"No subtitles found in {subtitle_path}. Skipping translation.")
                processing_status.error(video_path)
                return
                
            # 자막 줄 추출 
            subtitle_lines = [sub.content for sub in subs]
            
            if not subtitle_lines:
                log(f"No subtitle lines could be extracted from {subtitle_path}. Skipping translation.")
                processing_status.error(video_path)
                return
                
            log(f"자막 번역 시작 - 총 {len(subtitle_lines)}줄")
            
            # 번역 시작 상태 업데이트
            processing_status.start_translating(video_path, len(subtitle_lines))
                
            # 줄 단위로 번역
            translated_lines = self._translate_subtitle_lines(subtitle_lines, video_path)
            
            # 번역된 줄들을 원본 자막 구조에 적용
            translated_subtitles = self._apply_translations_to_subtitles(subs, translated_lines)
            
            # 번역 전후 자막 수 검증
            log(f"번역 전 자막 항목 수: {len(subs)}, 번역 후 자막 항목 수: {len(translated_subtitles)}")
            
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
        numbered_lines = {}
        
        # 첫 번째 단계: 번호가 있는 줄 먼저 처리
        for line in translated_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # 번호 접두사(예: "1. ", "2. " 등) 찾기
            parts = line.split('. ', 1)
            if len(parts) > 1 and parts[0].isdigit():
                line_num = int(parts[0])
                if 1 <= line_num <= expected_count:
                    numbered_lines[line_num] = parts[1]
        
        # 모든 번호가 있는지 확인
        all_numbers_found = len(numbered_lines) == expected_count
        
        if all_numbers_found:
            # 번호가 모두 있으면 번호 순서대로 반환
            return [numbered_lines[i+1] for i in range(expected_count)]
        else:
            # 번호가 누락된 경우 다른 방식 시도
            log(f"번역된 줄에서 일부 번호가 누락되어 있습니다. 대체 파싱 방법 사용 중...")
            lines = []
            for line in translated_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split('. ', 1)
                if len(parts) > 1 and parts[0].isdigit():
                    lines.append(parts[1])
                else:
                    # 번호가 없는 경우 전체 라인 추가
                    lines.append(line)
        
        # 기대한 줄 수와 일치하도록 조정
        if len(lines) < expected_count:
            log(f"번역된 줄 수({len(lines)})가 기대한 줄 수({expected_count})보다 적습니다.")
            # 부족한 줄은 빈 줄로 채움
            lines.extend([''] * (expected_count - len(lines)))
        elif len(lines) > expected_count:
            log(f"번역된 줄 수({len(lines)})가 기대한 줄 수({expected_count})보다 많습니다.")
            # 초과 줄은 버림
            lines = lines[:expected_count]
            
        return lines
        
    def _apply_translations_to_subtitles(self, original_subs, translated_lines):
        """번역된 줄들을 원본 자막 구조에 적용"""
        translated_subs = []
        
        # 자막 수와 번역된 줄 수 확인
        if len(original_subs) != len(translated_lines):
            log(f"경고: 원본 자막 수({len(original_subs)})와 번역된 줄 수({len(translated_lines)})가 일치하지 않습니다. " 
                "자막 줄 매핑에 영향을 미칠 수 있습니다.")
        
        for i, sub in enumerate(original_subs):
            # 각 자막 항목에 번역된 내용 적용
            if i < len(translated_lines):
                translated_content = translated_lines[i].strip()
                # 번역된 내용이 비어있는 경우 원본 내용 유지
                if not translated_content:
                    log(f"경고: 자막 #{i+1}의 번역된 내용이 비어있습니다. 원본 내용을 유지합니다.")
                    translated_content = sub.content
                
                # 새로운 자막 객체 생성
                new_sub = srt.Subtitle(
                    index=sub.index,  # 원본 인덱스 유지
                    start=sub.start,  # 시작 시간 유지
                    end=sub.end,      # 종료 시간 유지
                    content=translated_content  # 번역된 내용 적용
                )
                translated_subs.append(new_sub)
            else:
                # 번역된 줄이 부족하면 원본 자막 유지
                log(f"경고: 자막 #{i+1}에 대한 번역이 없습니다. 원본 자막을 유지합니다.")
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
            "2. **Completeness:** It is absolutely critical that you translate every single line. You must maintain the EXACT number of lines.\n"
            "3. **Strict Formatting:** Start each line with its number followed by a period and space (e.g., '1. ', '2. '). \n"
            "4. **Preserve Formatting Tags:** Preserve any formatting tags such as <i>, <b>, etc.\n"
            "5. **Line Integrity:** Each line must remain a complete thought or sentence. Never break a line's meaning or flow.\n"
            "6. **Output Format:** Your response must contain ONLY the numbered translated lines, one per line.\n\n"
            "Here are the subtitle lines to translate (IMPORTANT: I must get back the exact same number of lines):\n\n"
            f"{chunk_text}"
        )
    
    def _clean_response(self, response_text):
        """응답에서 마크다운 포맷팅 제거 및 정제"""
        if not response_text:
            return ""
            
        cleaned = response_text.strip()
        
        # 마크다운 코드 블록 제거
        if cleaned.startswith("```srt") and cleaned.endswith("```"):
            cleaned = cleaned[6:-3].strip()
        elif cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned[3:-3].strip()
        
        # 불필요한 헤더나 설명 제거
        lines = cleaned.split('\n')
        filtered_lines = []
        
        # 번역된 줄만 수집 (번호로 시작하는 줄 또는 가능한 번역 줄)
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 줄이 번호로 시작하거나, 설명 텍스트가 아닌 경우만 포함
            if (line[0].isdigit() or 
                not line.lower().startswith(('here', 'translation', 'translated', '번역', '자막'))):
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _save_translated_subtitles(self, translated_subtitles, video_path):
        """번역된 자막을 파일로 저장"""
        final_translated_srt = srt.compose(translated_subtitles)
        output_path = f"{os.path.splitext(video_path)[0]}.{self.target_language}.srt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_translated_srt)
        log(f"Translated subtitle saved to {output_path}")
