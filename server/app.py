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


@app.route('/download', methods=['POST'])
def download():
    try:
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')

        # Create a temporary directory for downloads
        temp_dir = os.path.join(os.getcwd(), 'temp_downloads')
        os.makedirs(temp_dir, exist_ok=True)

        # Change working directory to temp_dir
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        try:
            # Run spotdl with proper arguments
            command = ['/var/www/spotifysave/venv/bin/spotdl', spotify_url, '--output', '{title} - {artist}.mp3']
            app.logger.debug(f"Running command: {' '.join(command)}")

            process = subprocess.run(command, capture_output=True, text=True)

            if process.returncode != 0:
                app.logger.error(f"spotdl error: {process.stderr}")
                return jsonify({'error': 'Download failed'}), 500

            # Find the downloaded file
            downloaded_files = [f for f in os.listdir() if f.endswith('.mp3')]
            if not downloaded_files:
                return jsonify({'error': 'No file downloaded'}), 500

            file_path = os.path.join(temp_dir, downloaded_files[0])

            # Read file and send
            with open(file_path, 'rb') as file:
                file_data = file.read()

            # Clean up
            os.remove(file_path)

            return send_file(
                io.BytesIO(file_data),
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=f"{title} - {artist}.mp3"
            )

        finally:
            # Always return to original directory and cleanup
            os.chdir(original_dir)
            try:
                os.rmdir(temp_dir)
            except:
                pass

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
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