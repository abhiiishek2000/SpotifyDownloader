from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
from datetime import timedelta
from pathlib import Path
import os
import logging
import tempfile
import subprocess
import json
import io
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, send_file, jsonify
import requests
import re
import tempfile
import json
from pathlib import Path
import urllib.parse

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('../public/images', filename)


# Set up file logging
log_file = '/var/www/spotifysave/app.log'
file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)


def get_track_info(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        title = soup.find('meta', property='og:title')['content']
        description = soup.find('meta', property='og:description')['content']
        image = soup.find('meta', property='og:image')['content']
        duration = soup.find('meta', property='music:duration')
        duration = str(timedelta(seconds=int(duration['content']))) if duration else "Unknown"

        return {
            'title': title,
            'artist': description.split('·')[0].strip(),
            'image': image,
            'duration': duration,
            'url': url
        }
    except Exception as e:
        app.logger.error(f"Error getting track info: {str(e)}")
        return None


def download_track(title, artist, spotify_url):
    try:
        output_path = f"{title} - {artist}.mp3"
        command = ['/var/www/spotifysave/venv/bin/spotdl', spotify_url, '--output', output_path]

        app.logger.debug(f"Command: {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True)

        if os.path.exists(output_path):
            return output_path
        return None

    except Exception as e:
        app.logger.exception("Download failed")
        return None


def download_audio(video_id, output_path):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Get video info
        info_url = f"https://www.youtube.com/youtubei/v1/player?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        data = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "16.20"
                }
            }
        }

        response = requests.post(info_url, json=data, headers=headers)
        if response.status_code != 200:
            return False

        video_data = response.json()
        formats = video_data.get('streamingData', {}).get('adaptiveFormats', [])
        audio_url = next((f['url'] for f in formats if f.get('mimeType', '').startswith('audio/')), None)

        if audio_url:
            audio_response = requests.get(audio_url, headers=headers, stream=True)
            if audio_response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in audio_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True

        return False

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return False


def search_youtube_music(query):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        search_url = "https://www.youtube.com/youtubei/v1/search?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        data = {
            "query": query,
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "16.20"
                }
            }
        }

        response = requests.post(search_url, json=data, headers=headers)
        if response.status_code != 200:
            return None

        search_data = response.json()
        items = search_data.get('contents', {}).get('sectionListRenderer', {}).get('contents', [])

        for item in items:
            video_id = item.get('itemSectionRenderer', {}).get('contents', [])[0].get('videoRenderer', {}).get(
                'videoId')
            if video_id:
                return video_id

        return None

    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        return None


@app.route('/download', methods=['POST'])
def download():
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')
        search_query = f"{title} {artist} audio"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / f"{title} - {artist}.mp3"

            # Search and get video ID
            video_id = search_youtube_music(search_query)
            if not video_id:
                return jsonify({'error': 'Song not found'}), 404

            # Download audio
            if download_audio(video_id, output_path):
                return send_file(
                    str(output_path),
                    mimetype='audio/mpeg',
                    as_attachment=True,
                    download_name=output_path.name
                )

            return jsonify({'error': 'Download failed'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/track-info', methods=['POST'])
def get_info():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    track_info = get_track_info(url)
    if track_info:
        return jsonify(track_info)
    return jsonify({'error': 'Could not fetch track info'}), 500


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    return render_template('terms.html')


if __name__ == '__main__':
    app.run(debug=True)