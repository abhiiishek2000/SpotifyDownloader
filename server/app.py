import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from spotdl import Spotdl
from ytmusicapi import YTMusic
import logging
import subprocess

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')


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


def get_stream_url(video_id):
    """Get audio stream URL from video ID using YTMusic."""
    try:
        ytmusic = YTMusic()
        # Get basic details first
        data = ytmusic.get_watch_playlist(videoId=video_id, limit=1)

        if not data or 'tracks' not in data:
            raise Exception("Could not get video data")

        track = data['tracks'][0]

        # Get playback URL using endpoint
        endpoint = "https://music.youtube.com/watch?v=" + video_id
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Origin': 'https://music.youtube.com',
            'Referer': 'https://music.youtube.com/'
        }

        response = requests.get(endpoint, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get video page: {response.status_code}")

        return endpoint  # Return the YouTube Music URL directly

    except Exception as e:
        raise Exception(f"Failed to get stream URL: {str(e)}")


@app.route('/download', methods=['POST'])
def download():
    try:
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')

        # Initialize SpotDL with corrected cookie_file setting
        spotdl = Spotdl(
            client_id='41c1c1a4546c413498d522b0f0508670',
            client_secret='c36781c6845448d3b97a1d30403d8bbe',
            downloader_settings={
                'format': 'mp3',
                'ffmpeg': '/usr/bin/ffmpeg',
                'audio_providers': ['youtube-music', 'youtube'],
                'filter_results': True,
                'yt_dlp_args': '--no-check-certificate --force-ipv4',
                'cookie_file': '/var/www/spotifysave/youtube.txt',  # Corrected keyword
                'audio_quality': '320k',
                'headless': True,
                'quiet': True
            }
        )

        app.logger.debug(f"Searching for: {spotify_url}")
        songs = spotdl.search([spotify_url])

        if not songs:
            return jsonify({'error': 'Song not found'}), 404

        app.logger.debug(f"Found {len(songs)} songs")
        song, file_path = spotdl.download(songs[0])

        def generate():
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk

        response = Response(generate(), mimetype='audio/mpeg')
        response.headers['Content-Disposition'] = f'attachment; filename="{title} - {artist}.mp3"'
        return response

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}", exc_info=True)
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
