import tempfile
from flask import Flask, render_template, request, jsonify, send_file, Response
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import logging
from spotdl import Spotdl

from flask import Flask, request, jsonify, send_file
from spotdl import Spotdl
from yt_dlp import YoutubeDL
import os
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Path to ffmpeg
FFMPEG_PATH = "/usr/bin/ffmpeg"
if not os.path.isfile(FFMPEG_PATH):
    raise EnvironmentError("ffmpeg is not installed or not found at /usr/bin/ffmpeg. Install it using 'sudo apt install ffmpeg'.")

# Spotdl setup
spotdl = Spotdl(
    client_id= '41c1c1a4546c413498d522b0f0508670',
    client_secret='c36781c6845448d3b97a1d30403d8bbe'
)

# YouTube downloader options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/%(title)s.%(ext)s',
    'postprocessors': [
        {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }
    ],
    'ffmpeg_location': FFMPEG_PATH,
    'quiet': True,
    'noplaylist': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url']
        logger.info(f"Received URL: {url}")

        # Spotify processing
        if "spotify.com" in url:
            logger.info("Processing Spotify URL...")
            track = spotdl.search([url])
            if not track:
                return jsonify({'error': 'Spotify track not found'}), 404
            
            output_path = '/tmp'
            filename = spotdl.download(track, output_path=output_path)
            if not filename:
                return jsonify({'error': 'Failed to download Spotify track'}), 500
            
            logger.info(f"Spotify track downloaded: {filename}")
            return send_file(filename, as_attachment=True)

        # YouTube processing
        elif "youtube.com" in url or "youtu.be" in url:
            logger.info("Processing YouTube URL...")
            with YoutubeDL(YTDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                converted_path = file_path.replace('.webm', '.mp3').replace('.m4a', '.mp3')
                if os.path.isfile(converted_path):
                    logger.info(f"YouTube track downloaded: {converted_path}")
                    return send_file(converted_path, as_attachment=True)
                else:
                    return jsonify({'error': 'Failed to convert YouTube video to MP3'}), 500

        # Invalid URL
        else:
            return jsonify({'error': 'Invalid URL'}), 400

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return jsonify({'error': str(e)}), 500


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
