import tempfile
from flask import Flask, render_template, request, jsonify, send_file, Response
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import logging
from spotdl import Spotdl

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
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')

        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize Spotdl with updated settings
            spotdl = Spotdl(
                client_id='41c1c1a4546c413498d522b0f0508670',
                client_secret='c36781c6845448d3b97a1d30403d8bbe',
                downloader_settings={
                    'output': f'{temp_dir}/%(artist)s - %(title)s.%(ext)s',
                    'format': 'mp3',
                    'ffmpeg': '/usr/bin/ffmpeg',
                    'cookie_file': '/var/www/spotifysave/cookies.txt',
                    'threads': 1,
                    'audio_providers': ['youtube-music', 'youtube'],
                    'filter_results': True,
                    'yt_dlp_args': '--force-ipv4 --no-check-certificates',  # Changed to string
                    'headless': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Connection': 'keep-alive',
                    }
                }
            )
            # Log and search for songs
            app.logger.debug(f"Searching for: {spotify_url}")
            songs = spotdl.search([spotify_url])

            if not songs:
                return jsonify({'error': 'Song not found'}), 404

            app.logger.debug(f"Found {len(songs)} songs")
            song, file_path = spotdl.download(songs[0])

            if file_path and file_path.exists():
                def generate():
                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            yield chunk

                response = Response(
                    generate(),
                    mimetype='audio/mpeg'
                )
                response.headers['Content-Disposition'] = f'attachment; filename="{title} - {artist}.mp3"'
                return response

            return jsonify({'error': 'Download failed'}), 500

    except Exception as e:

        app.logger.error(f"Download error: {str(e)}", exc_info=True)  # Add full traceback

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
