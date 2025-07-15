# Subtitle Translator

[한국어 README](README.ko.md)

This project provides an automated solution for extracting subtitles from video files, translating them using the Google Gemini API, and saving the translated subtitles as new SRT files. It continuously monitors a specified directory for new video files and processes them automatically.

## Features

*   **Automated Monitoring**: Watches a designated directory for newly added video files.
*   **Subtitle Extraction**: Extracts subtitle streams from video files using `ffmpeg` and `ffprobe`.
*   **AI-Powered Translation**: Translates subtitles using the `gemini-2.5-flash` model from the Google Gemini API.
*   **Multi-stream Support**: Handles multiple subtitle streams within a video, prioritizing extraction based on size.
*   **SRT Output**: Saves translated subtitles in standard SRT format.
*   **Configurable**: Easily customizable via environment variables for watch directory, target language, API key, and scan interval.
*   **Error Handling**: Includes retry mechanisms for API quota issues.
*   **Temporary File Cleanup**: Automatically removes temporary raw subtitle files after translation.

## Requirements

*   `ffmpeg` and `ffprobe` (will be included in the Docker image)
*   Python 3.x (will be included in the Docker image)
*   A Google Gemini API Key.
*   Docker and Docker Compose

## Environment Variables

The following environment variables can be set to configure the application:

*   `WATCH_DIRECTORY`: The absolute path inside the Docker container to monitor for new video files. (Default: `/videos`)
*   `TARGET_LANGUAGE`: The language code for the desired translation (e.g., `en` for English, `ko` for Korean). (Default: `en`)
*   `GEMINI_API_KEY`: Your Google Gemini API key. **This is a mandatory environment variable.**
*   `SCAN_INTERVAL`: The interval in seconds at which the application scans for new video files. (Default: `60`)

## Usage with Docker Compose

1.  **Create a `.env` file**:
    Create a file named `.env` in the root directory of the project and add your `GEMINI_API_KEY` to it:
    ```
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    ```
    Replace `YOUR_GEMINI_API_KEY` with your actual Gemini API key.

2.  **Prepare your video directory**:
    Create a directory named `videos` in the root of this project. This directory will be mounted into the Docker container and will be where you place your video files for processing.

3.  **Run with Docker Compose**:
    Navigate to the root directory of the project in your terminal and run:
    ```bash
    docker-compose up --build -d
    ```
    *   `--build`: Builds the Docker image before starting the containers.
    *   `-d`: Runs the containers in detached mode (in the background).

    The application will start monitoring the `videos` directory for new video files. When a new video is detected, it will attempt to extract and translate its subtitles.

4.  **Stop the application**:
    To stop the application, run:
    ```bash
    docker-compose down
    ```

## How it Works

The script operates in a continuous loop:
1.  It scans the `WATCH_DIRECTORY` (which is mapped to your local `videos` directory) for new video files that have been added since the last scan.
2.  For each new video file, it uses `ffprobe` to identify available subtitle streams.
3.  It then uses `ffmpeg` to extract the subtitle streams into temporary SRT files.
4.  The extracted subtitle content is sent to the Google Gemini API for translation into the `TARGET_LANGUAGE`.
5.  The translated content is then saved as a new SRT file in the same directory as the video, with the target language appended to the filename (e.g., `my_video.en.srt`).
6.  Finally, the temporary raw subtitle files are removed.