import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import logging
from ytmusicapi import YTMusic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from youtube_music_downloader import CustomMusicDownloader

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')

API_KEY = 'AIzaSyCSrmcJ3mBG2Z7kYH0GjMH5Kpxunq-bLj0'


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
        title = request.json.get('title')
        artist = request.json.get('artist')

        with tempfile.TemporaryDirectory() as temp_dir:
            ytmusic = YTMusic()
            search_results = ytmusic.search(f"{title} {artist}", filter="songs", limit=1)

            if not search_results:
                return jsonify({'error': 'Song not found'}), 404

            video_id = search_results[0]['videoId']

            # Download using custom downloader
            downloader = CustomMusicDownloader(API_KEY)
            try:
                stream_url = downloader.get_stream_url(video_id)
                output_path = Path(temp_dir) / f"{title} - {artist}"
                mp3_file = downloader.download_audio(stream_url, output_path)

                def generate():
                    with open(mp3_file, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            yield chunk

                response = Response(generate(), mimetype='audio/mpeg')
                response.headers['Content-Disposition'] = f'attachment; filename="{title} - {artist}.mp3"'
                return response

            except Exception as e:
                app.logger.error(f"Download error: {str(e)}")
                return jsonify({'error': 'Failed to download audio'}), 500

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