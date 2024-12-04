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

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('../public/images', filename)


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


def download_track(title, artist):
    try:
        temp_dir = tempfile.mkdtemp()
        os.chdir(temp_dir)

        # Construct spotdl command with additional options
        command = [
            '/var/www/spotifysave/env/bin/spotdl',
            '--output', temp_dir,
            '--format', 'mp3',
            '--bitrate', '320k',
            '--no-cache',  # Add this to avoid caching issues
            '--audio-provider', 'youtube-music',  # Specify YouTube Music as provider
            '--search-query', '{artist} - {track-name} audio',  # Better search format
            '--download-ffmpeg',  # Ensure ffmpeg is available
            'download',
            f"{title} - {artist}"
        ]

        app.logger.debug(f"Running command: {' '.join(command)}")

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['PATH'] = f"/var/www/spotifysave/env/bin:{env.get('PATH', '')}"

        # Run spotdl command with extended timeout
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            timeout=300  # 5 minutes timeout
        )

        app.logger.debug(f"Command output: {process.stdout}")
        if process.stderr:
            app.logger.error(f"Command error: {process.stderr}")

        # Check for downloaded files
        files = os.listdir(temp_dir)
        mp3_files = [f for f in files if f.endswith('.mp3')]

        if mp3_files:
            file_path = os.path.join(temp_dir, mp3_files[0])
            if os.path.exists(file_path):
                return file_path

        return None

    except subprocess.TimeoutExpired:
        app.logger.error("Download timed out")
        return None
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return None

@app.route('/download', methods=['POST'])
def download():
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')

        if not title or not artist:
            return jsonify({'error': 'Title and artist required'}), 400

        file_path = download_track(title, artist)
        if file_path and os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f'{title} - {artist}.mp3',
                mimetype='audio/mpeg'
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