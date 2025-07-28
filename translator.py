import os
import time
import srt
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from utils import log

class SubtitleTranslator:
    """Gemini API를 사용한 자막 번역 클래스"""
    
    def __init__(self, api_key, target_language):
        self.target_language = target_language
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def translate_and_save_subtitle(self, subtitle_paths, video_path):
        """자막을 번역하고 저장"""
        combined_subtitle_text = self._combine_subtitle_texts(subtitle_paths)
        
        if not combined_subtitle_text.strip():
            log("All subtitle files were empty or unreadable. Skipping translation.")
            return
        
        try:
            # Parse the first subtitle file for SRT structure
            with open(subtitle_paths[0], 'r', encoding='utf-8') as f:
                subs = list(srt.parse(f.read()))
            
            translated_subtitles = self._translate_subtitles_in_chunks(subs, video_path)
            self._save_translated_subtitles(translated_subtitles, video_path)
            
        except Exception as e:
            log(f"Error translating or saving subtitle for {video_path}: {e}")
    
    def _combine_subtitle_texts(self, subtitle_paths):
        """여러 자막 파일의 텍스트를 결합"""
        combined_subtitle_text = ""
        for i, subtitle_path in enumerate(subtitle_paths):
            try:
                with open(subtitle_path, 'r', encoding='utf-8') as f:
                    subtitle_text = f.read()
                if subtitle_text.strip():
                    combined_subtitle_text += f"--- Subtitle Version {i+1} ---\n{subtitle_text}\n\n"
            except FileNotFoundError:
                log(f"Could not find subtitle file {subtitle_path}. Skipping this version.")
        return combined_subtitle_text
    
    def _translate_subtitles_in_chunks(self, subs, video_path):
        """자막을 청크 단위로 번역"""
        total_subtitles = len(subs)
        translated_subtitles = []
        chunk_size = 10  # Translate 10 subtitles at a time
        
        for i in range(0, total_subtitles, chunk_size):
            chunk = subs[i:i + chunk_size]
            translated_chunk = self._translate_chunk(chunk, video_path, i)
            
            if translated_chunk:
                translated_subtitles.extend(translated_chunk)
            
            progress = (i + len(chunk)) / total_subtitles * 100
            log(f"Translation progress for {os.path.basename(video_path)}: {progress:.2f}% "
                f"({i + len(chunk)}/{total_subtitles} subtitles translated)")
        
        return translated_subtitles
    
    def _translate_chunk(self, chunk, video_path, chunk_index):
        """개별 청크를 번역"""
        chunk_text = srt.compose(chunk)
        prompt = self._create_translation_prompt(chunk_text)
        
        retries = 5
        for attempt in range(retries):
            try:
                response = self.model.generate_content(prompt)
                translated_chunk_text = self._clean_response(response.text)
                return list(srt.parse(translated_chunk_text))
                
            except ResourceExhausted as e:
                wait_time = min(60, 2**(attempt+1) * 5)  # Cap at 60 seconds
                log(f"Quota exceeded for {video_path} (chunk {chunk_index}-{chunk_index+len(chunk)}). "
                    f"Retrying in {wait_time} seconds... ({e})")
                time.sleep(wait_time)
                
            except Exception as e:
                log(f"Error generating content for {video_path} "
                    f"(chunk {chunk_index}-{chunk_index+len(chunk)}): {e}")
                break
        
        log(f"Failed to translate chunk {chunk_index}-{chunk_index+len(chunk)} "
            f"for {video_path} after {retries} retries.")
        return []
    
    def _create_translation_prompt(self, chunk_text):
        """번역을 위한 프롬프트 생성"""
        return (
            f"You are an expert translator specializing in subtitles for movies, TV, and animation. "
            f"Your task is to translate the provided SRT subtitle content into {self.target_language}, "
            f"making it sound as natural as possible, as if it were originally written in Korean.\n\n"
            "Follow these instructions carefully:\n"
            "1. **Natural Translation:** The translation must be fluent and natural. Avoid stiff, literal translations.\n"
            "2. **Completeness:** It is absolutely critical that you translate the entire content from beginning to end. Do not omit any lines.\n"
            "3. **Strict SRT Format Preservation:** You MUST strictly preserve the original SRT format. This includes:\n"
            "   - Exact sequential numbering (e.g., 1, 2, 3...)\n"
            "   - Exact timestamps (e.g., 00:00:01,000 --> 00:00:03,500)\n"
            "   - All original formatting tags (e.g., <i>, <b>, <font color=\"#RRGGBB\">)\n"
            "   - Correct line breaks between subtitle text and the next number/timestamp block.\n"
            "   - Do NOT add any extra blank lines unless they are present in the original SRT.\n"
            "4. **Output ONLY SRT:** Your final output MUST be ONLY the complete, translated SRT file content. "
            "Do NOT include any conversational text, explanations, markdown code blocks (like ```srt or ```), "
            "or any other extraneous characters before or after the SRT content. Just the raw SRT text.\n\n"
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
