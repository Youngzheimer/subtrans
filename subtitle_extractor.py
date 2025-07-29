import os
import subprocess
from utils import log
import pysrt
import ass
import webvtt
from utils import Config
from processing_status import processing_status

def extract_subtitle(video_path, subtitle_relative_index):
    """비디오에서 자막을 추출"""
    # Include the index in the output path to avoid overwriting
    output_path = f"{os.path.splitext(video_path)[0]}.raw.{subtitle_relative_index}.srt"
    command = [
        "ffmpeg",
        "-i", video_path,
        "-map", f"0:s:{subtitle_relative_index}",
        "-c:s", "srt",
        output_path,
        "-y"  # Overwrite output file if it exists
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Could not extract subtitle for {video_path} (stream {subtitle_relative_index}). "
            f"It might be an image-based format. FFMPEG stderr: {result.stderr})")
        return None
    return output_path

def determine_extraction_count(subtitle_size_kb, total_subtitles):
    """**WARNING: NOT USED. USE `extract_multiple_subtitles` INSTEAD.**
    자막 크기에 따라 추출할 자막 수를 결정"""
    if subtitle_size_kb <= 100:
        return min(total_subtitles, 3)
    elif subtitle_size_kb <= 200:
        return min(total_subtitles, 2)
    else:  # > 200KB and <= 500KB
        return min(total_subtitles, 1)
    
def extract_subtitle_lines(subtitle_path):
    """자막 파일에서 텍스트 라인 추출"""
    try:
        if subtitle_path.endswith('.srt'):
            subs = pysrt.open(subtitle_path)
            return [sub.text for sub in subs]
        elif subtitle_path.endswith('.ass'):
            with open(subtitle_path, encoding='utf_8_sig') as f:
                subs = ass.parse(f.read())
            return [sub.text for sub in subs]
        elif subtitle_path.endswith('.vtt'):
            with open(subtitle_path, encoding='utf_8_sig') as f:
                subs = webvtt.read(f)
            return [sub.text for sub in subs]
        else:
            log(f"Unsupported subtitle format: {subtitle_path}")
            return []
    except Exception as e:
        log(f"Error extracting subtitle lines from {subtitle_path}: {e}")
    return []

def extract_multiple_subtitles(video_file, line_thresholds, streams_to_extract):
    """여러 자막 스트림을 추출하고 관리
    
    Args:
        video_file (str): 비디오 파일 경로
        line_thresholds (list): 자막 라인 수 임계값 목록
        streams_to_extract (list): 각 임계값 별로 추출할 자막 스트림 수
        
    Returns:
        list: 추출된 자막 파일 경로 목록
    """
    extracted_subtitle_paths = []
    
    # 자막 추출 상태 업데이트
    processing_status.start_extracting(video_file)
    
    # Always extract the first subtitle stream to check its size
    first_extracted_path = extract_subtitle(video_file, 0)
    if not first_extracted_path:
        log(f"Could not extract the first subtitle stream for {video_file}. Skipping.")
        processing_status.error(video_file)
        return []
    
    extracted_subtitle_paths.append(first_extracted_path)

    lines = extract_subtitle_lines(first_extracted_path)    
    if not lines:
        log(f"No valid subtitle lines extracted from {first_extracted_path}. Skipping translation.")
        return []
    
    # Determine number of subtitles to extract based on the first subtitle length
    line_count = len(lines)
    num_to_extract_total = streams_to_extract[-1]  # 기본값: 가장 적은 수
    
    # 자막 라인 수에 따라 추출할 자막 수 결정
    for i, threshold in enumerate(line_thresholds):
        if line_count < threshold:
            # 자막 스트림 수는 0부터 시작하므로 총 스트림 수 계산 시 주의
            num_to_extract_total = streams_to_extract[i]
            break
    
    log(f"Total {len(lines)} lines of subtitles, extracting {num_to_extract_total} subtitle streams from {video_file}.")
    
    # # Check the size of the first extracted subtitle
    # first_subtitle_size_bytes = os.path.getsize(first_extracted_path)
    # first_subtitle_size_kb = first_subtitle_size_bytes / 1024  # Size in KB
    # log(f"First extracted subtitle size: {first_subtitle_size_kb:.2f} KB")
    
    # if first_subtitle_size_kb > 500:
    #     log(f"Subtitle file size ({first_subtitle_size_kb:.2f} KB) exceeds 500KB. Skipping translation for {video_file}.")
    #     cleanup_subtitle_files(extracted_subtitle_paths)
    #     return None, []
    
    # num_to_extract_total = determine_extraction_count(first_subtitle_size_kb, len(subtitles))
    # log(f"Will attempt to extract up to {num_to_extract_total} subtitle streams.")
    
    # Extract additional subtitles if num_to_extract_total is greater than 1
    for i in range(1, num_to_extract_total):
        # 자막 스트림 인덱스가 존재하는지 확인하기는 어려우므로 시도해보고 실패하면 중단
        additional_extracted_path = extract_subtitle(video_file, i)
        if additional_extracted_path:
            log(f"  - Successfully extracted stream {i} to: {os.path.basename(additional_extracted_path)}")
            extracted_subtitle_paths.append(additional_extracted_path)
        else:
            log(f"Could not extract additional subtitle stream {i} for {video_file}. Continuing with extracted streams.")
            break
    
    return extracted_subtitle_paths

def cleanup_subtitle_files(subtitle_paths):
    """임시 자막 파일들을 정리"""
    for subtitle_file in subtitle_paths:
        try:
            os.remove(subtitle_file)
            log(f"  - Removed temporary file: {os.path.basename(subtitle_file)}")
        except OSError as e:
            log(f"Error removing temporary subtitle file {subtitle_file}: {e}")
