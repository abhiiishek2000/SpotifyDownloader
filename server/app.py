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

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('../public/images', filename)


def download_track(title, artist):
    try:
        temp_dir = tempfile.mkdtemp()
        os.chdir(temp_dir)

        # Create config file
        config_content = {
            "audio_providers": ["youtube-music"],
            "lyrics_providers": ["genius"],
            "ffmpeg": "ffmpeg",
            "bitrate": "320k",
            "format": "mp3",
            "threads": 1,
            "sponsor_block": False
        }

        config_file = os.path.join(temp_dir, 'spotdl.json')
        with open(config_file, 'w') as f:
            json.dump(config_content, f)

        # Construct spotdl command with config
        command = [
            '/var/www/spotifysave/env/bin/spotdl',
            '--config', config_file,
            '--output', os.path.join(temp_dir, '{artist} - {title}.{ext}'),
            'download',
            '--use-youtube-music',  # Force YouTube Music
            '--search-query', '{artist} - {title} audio official',  # Better search query
            f'"{title} - {artist}"'
        ]

        app.logger.debug(f"Running command: {' '.join(command)}")

        env = os.environ.copy()
        env['PATH'] = f"/var/www/spotifysave/env/bin:/usr/local/bin:/usr/bin:{env.get('PATH', '')}"

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            timeout=300
        )

        app.logger.debug(f"Command output: {process.stdout}")
        if process.stderr:
            app.logger.error(f"Command error: {process.stderr}")

        files = os.listdir(temp_dir)
        mp3_files = [f for f in files if f.endswith('.mp3')]

        if mp3_files:
            file_path = os.path.join(temp_dir, mp3_files[0])
            if os.path.exists(file_path):
                app.logger.info(f"Successfully downloaded: {file_path}")
                return file_path

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