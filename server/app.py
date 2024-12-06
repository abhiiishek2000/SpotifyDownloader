import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import logging
from ytmusicapi import YTMusic
import yt_dlp

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

            yt_url = f"https://music.youtube.com/watch?v={search_results[0]['videoId']}"
            output_template = f'{temp_dir}/%(title)s.%(ext)s'

            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'outtmpl': output_template,
                'ffmpeg_location': '/usr/bin/ffmpeg',
                'extract_flat': False,
                'no_check_certificate': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://music.youtube.com/'
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                app.logger.debug(f"Downloading from URL: {yt_url}")
                info = ydl.extract_info(yt_url, download=True)
                file_path = Path(ydl.prepare_filename(info)).with_suffix('.mp3')

                app.logger.debug(f"Download complete, file path: {file_path}")

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