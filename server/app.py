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


@app.route('/download', methods=['POST'])
def download():
    try:
        spotify_url = request.json.get('url')
        command = ['/var/www/spotifysave/venv/bin/spotdl', spotify_url]

        process = subprocess.run(command,
                                 capture_output=True,
                                 cwd='/var/www/spotifysave/downloads')

        mp3_files = [f for f in os.listdir('/var/www/spotifysave/downloads')
                     if f.endswith('.mp3')]

        if mp3_files:
            file_path = f'/var/www/spotifysave/downloads/{mp3_files[0]}'
            with open(file_path, 'rb') as f:
                data = f.read()
            os.remove(file_path)

            return send_file(
                io.BytesIO(data),
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=mp3_files[0]
            )

        return jsonify({'error': 'No file downloaded'}), 500

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
