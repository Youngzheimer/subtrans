import os
import time
import subprocess
import google.generativeai as genai
import json
import srt
from datetime import datetime
from google.api_core.exceptions import ResourceExhausted

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

# --- User Configuration ---
WATCH_DIRECTORY = os.getenv("WATCH_DIRECTORY", "/videos")
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "en")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60")) # In seconds
# ------------------------

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)

last_scanned_files = set()

def get_video_files(directory):
    video_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                video_files.append(os.path.join(root, file))
    return video_files

def get_subtitle_info(video_path):
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

def extract_subtitle(video_path, subtitle_relative_index):
    # Include the index in the output path to avoid overwriting
    output_path = f"{os.path.splitext(video_path)[0]}.raw.{subtitle_relative_index}.srt"
    command = [
        "ffmpeg",
        "-i", video_path,
        "-map", f"0:s:{subtitle_relative_index}",
        "-c:s", "srt",
        output_path,
        "-y" # Overwrite output file if it exists
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Could not extract subtitle for {video_path} (stream {subtitle_relative_index}). It might be an image-based format. FFMPEG stderr: {result.stderr})")
        return None
    return output_path

def translate_and_save_subtitle(subtitle_paths, video_path):
    combined_subtitle_text = ""
    for i, subtitle_path in enumerate(subtitle_paths):
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_text = f.read()
            if subtitle_text.strip():
                combined_subtitle_text += f"--- Subtitle Version {i+1} ---\n{subtitle_text}\n\n"
        except FileNotFoundError:
            log(f"Could not find subtitle file {subtitle_path}. Skipping this version.")

    if not combined_subtitle_text.strip():
        log("All subtitle files were empty or unreadable. Skipping translation.")
        return

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Parse the combined subtitle text into SRT objects
        # Assuming combined_subtitle_text contains multiple SRTs, we'll just take the first one for parsing
        # For more robust handling, you might need to parse each subtitle_path separately
        # For now, let's assume the first subtitle_path is the primary one to parse
        with open(subtitle_paths[0], 'r', encoding='utf-8') as f:
            subs = list(srt.parse(f.read()))
        
        total_subtitles = len(subs)
        translated_subtitles = []
        chunk_size = 10 # Translate 10 subtitles at a time

        for i in range(0, total_subtitles, chunk_size):
            chunk = subs[i:i + chunk_size]
            chunk_text = srt.compose(chunk)

            prompt = (
                f"You are an expert translator specializing in subtitles for movies, TV, and animation. "
                f"""Your task is to translate the provided SRT subtitle content into {TARGET_LANGUAGE}, making it sound as natural as possible, as if it were originally written in Korean.

"""
                """Follow these instructions carefully:
"""
                """1. **Natural Translation:** The translation must be fluent and natural. Avoid stiff, literal translations.
2. **Completeness:** It is absolutely critical that you translate the entire content from beginning to end. Do not omit any lines.
3. **Strict SRT Format Preservation:** You MUST strictly preserve the original SRT format. This includes:
   - Exact sequential numbering (e.g., 1, 2, 3...)
   - Exact timestamps (e.g., 00:00:01,000 --> 00:00:03,500)
   - All original formatting tags (e.g., <i>, <b>, <font color=\"#RRGGBB\">)
   - Correct line breaks between subtitle text and the next number/timestamp block.
   - Do NOT add any extra blank lines unless they are present in the original SRT.
4. **Output ONLY SRT:** Your final output MUST be ONLY the complete, translated SRT file content. Do NOT include any conversational text, explanations, markdown code blocks (like ```srt or ```), or any other extraneous characters before or after the SRT content. Just the raw SRT text.

"""
                f"{chunk_text}"
            )
            
            retries = 5
            for attempt in range(retries):
                try:
                    response = model.generate_content(prompt)
                    translated_chunk_text = response.text
                    break # If successful, break out of the retry loop
                except ResourceExhausted as e:
                    wait_time = min(60, 2**(attempt+1) * 5) # Cap at 60 seconds
                    log(f"Quota exceeded for {video_path} (chunk {i}-{i+len(chunk)}). Retrying in {wait_time} seconds... ({e})")
                    time.sleep(wait_time) # Exponential backoff with increased base
                except Exception as e:
                    log(f"Error generating content for {video_path} (chunk {i}-{i+len(chunk)}): {e})")
                    translated_chunk_text = "" # Mark as empty to skip this chunk
                    break # Exit if it's not a quota error
            else: # This else block is executed if the loop completes without a 'break'
                log(f"Failed to translate chunk {i}-{i+len(chunk)} for {video_path} after {retries} retries due to quota issues. Skipping this chunk.")
                translated_chunk_text = "" # Mark as empty to skip this chunk

            # Clean up potential markdown formatting from the response
            if translated_chunk_text.strip().startswith("```srt"):
                translated_chunk_text = translated_chunk_text.strip()[6:-3].strip()
            elif translated_chunk_text.strip().startswith("```"):
                 translated_chunk_text = translated_chunk_text.strip()[3:-3].strip()
            
            try:
                translated_subtitles.extend(list(srt.parse(translated_chunk_text)))
            except Exception as e:
                log(f"Error parsing translated chunk for {video_path} (chunk {i}-{i+len(chunk)}): {e}. Skipping this chunk.")

            progress = (i + len(chunk)) / total_subtitles * 100
            log(f"Translation progress for {os.path.basename(video_path)}: {progress:.2f}% ({i + len(chunk)}/{total_subtitles} subtitles translated)")

        final_translated_srt = srt.compose(translated_subtitles)
        output_path = f"{os.path.splitext(video_path)[0]}.{TARGET_LANGUAGE}.srt"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_translated_srt)
        log(f"Translated subtitle saved to {output_path}")

    except Exception as e:
        log(f"Error translating or saving subtitle for {video_path}: {e}")


def main():
    log("--- Subtitle Translator ---")
    log(f"Watching directory: {WATCH_DIRECTORY}")
    log(f"Target language: {TARGET_LANGUAGE}")
    log("---------------------------")

    # Initial scan to populate the set of existing files
    last_scanned_files = set(get_video_files(WATCH_DIRECTORY))
    if last_scanned_files:
        log(f"Initial scan complete. Found {len(last_scanned_files)} existing video files. These will be ignored.")
        for f in last_scanned_files:
            log(f"  - Ignoring: {os.path.basename(f)}")
    else:
        log("Initial scan complete. No existing video files found.")

    log(f"\nStarting to watch for new files. Scanning every {SCAN_INTERVAL} seconds...")

    while True:
        current_files = set(get_video_files(WATCH_DIRECTORY))
        new_files = current_files - last_scanned_files
        removed_files = last_scanned_files - current_files

        if new_files:
            log(f"\nDetected {len(new_files)} new video file(s). Processing...")
            for video_file in new_files:
                log(f"--- Processing: {os.path.basename(video_file)} ---")
                try:
                    subtitle_info_str = get_subtitle_info(video_file)
                    if not subtitle_info_str:
                        log(f"Could not retrieve subtitle information for {video_file}. Skipping.")
                        continue

                    subtitle_info = json.loads(subtitle_info_str)
                    subtitles = subtitle_info.get('streams', [])

                    if not subtitles:
                        log("No subtitle streams found. Skipping.")
                        continue

                    if any(sub.get('tags', {}).get('language', 'und').lower() == TARGET_LANGUAGE.lower() for sub in subtitles):
                        log(f"Target language '{TARGET_LANGUAGE}' subtitle already exists. Skipping.")
                        continue

                    extracted_subtitle_paths = []
                    first_extracted_path = None

                    if not subtitles:
                        log("No subtitle streams found. Skipping.")
                        continue

                    # Check if target language subtitle already exists
                    if any(sub.get('tags', {}).get('language', 'und').lower() == TARGET_LANGUAGE.lower() for sub in subtitles):
                        log(f"Target language '{TARGET_LANGUAGE}' subtitle already exists. Skipping.")
                        continue

                    # Always extract the first subtitle stream to check its size
                    first_extracted_path = extract_subtitle(video_file, 0)
                    if not first_extracted_path:
                        log(f"Could not extract the first subtitle stream for {video_file}. Skipping.")
                        continue # Skip to next video file

                    extracted_subtitle_paths.append(first_extracted_path) # Add to list for potential translation and cleanup

                    # Check the size of the first extracted subtitle
                    first_subtitle_size_bytes = os.path.getsize(first_extracted_path)
                    first_subtitle_size_kb = first_subtitle_size_bytes / 1024 # Size in KB
                    log(f"First extracted subtitle size: {first_subtitle_size_kb:.2f} KB")

                    if first_subtitle_size_kb > 500:
                        log(f"Subtitle file size ({first_subtitle_size_kb:.2f} KB) exceeds 500KB. Skipping translation for {video_file}.")
                        # Clean up the temporary file immediately
                        for subtitle_file in extracted_subtitle_paths: # This will only contain first_extracted_path
                            try:
                                os.remove(subtitle_file)
                                log(f"  - Removed temporary file: {os.path.basename(subtitle_file)}")
                            except OSError as e:
                                log(f"Error removing temporary subtitle file {subtitle_file}: {e}")
                        continue # Skip to next video file

                    num_to_extract_total = 0
                    if first_subtitle_size_kb <= 100:
                        num_to_extract_total = min(len(subtitles), 3)
                        log(f"Subtitle size <= 100KB. Will attempt to extract up to {num_to_extract_total} subtitle streams.")
                    elif first_subtitle_size_kb <= 200:
                        num_to_extract_total = min(len(subtitles), 2)
                        log(f"Subtitle size <= 200KB. Will attempt to extract up to {num_to_extract_total} subtitle streams.")
                    else: # > 200KB and <= 500KB
                        num_to_extract_total = min(len(subtitles), 1)
                        log(f"Subtitle size > 200KB. Will attempt to extract up to {num_to_extract_total} subtitle streams.")

                    # Extract additional subtitles if num_to_extract_total is greater than 1
                    # Start from index 1 because index 0 is already extracted and in extracted_subtitle_paths
                    for i in range(1, num_to_extract_total):
                        if i < len(subtitles): # Ensure index is within bounds
                            additional_extracted_path = extract_subtitle(video_file, i)
                            if additional_extracted_path:
                                log(f"  - Successfully extracted stream {i} to: {os.path.basename(additional_extracted_path)}")
                                extracted_subtitle_paths.append(additional_extracted_path)
                            else:
                                log(f"Could not extract additional subtitle stream {i} for {video_file}. Continuing with extracted streams.")
                        else:
                            log(f"No more subtitle streams available to extract (requested {num_to_extract_total}, but only {len(subtitles)} exist).")
                            break # No more streams to extract

                    if extracted_subtitle_paths: # This check is important, as it might be empty if first extraction failed
                        translate_and_save_subtitle(extracted_subtitle_paths, video_file)
                        # Clean up all raw extracted subtitle files
                        for subtitle_file in extracted_subtitle_paths:
                            try:
                                os.remove(subtitle_file)
                                log(f"  - Removed temporary file: {os.path.basename(subtitle_file)}")
                            except OSError as e:
                                log(f"Error removing temporary subtitle file {subtitle_file}: {e}")
                    else:
                        log("Failed to extract any valid subtitle streams for translation. Skipping.")

                except json.JSONDecodeError:
                    log(f"Error parsing subtitle information for {video_file}. It might not be valid JSON. Skipping.")
                except Exception as e:
                    log(f"An unexpected error occurred while processing {video_file}: {e}")
                finally:
                    log(f"--- Finished processing: {os.path.basename(video_file)} ---\n")

        if removed_files:
            log(f"\nDetected {len(removed_files)} removed video file(s).")
            for video_file in removed_files:
                log(f"  - Removed: {os.path.basename(video_file)}")

        last_scanned_files = current_files

        # No log statement here for quiet running, it will only log when new files are detected.
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
