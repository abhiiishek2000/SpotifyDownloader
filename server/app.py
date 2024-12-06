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
    """Fetch metadata for a track from the given URL."""
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
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
    """Handle downloading and converting a track to MP3."""
    try:
        spotify_url = request.json.get('url')
        if not spotify_url:
            return jsonify({'error': 'No URL provided'}), 400

        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize Spotdl with configuration
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
                    'yt_dlp_args': '--force-ipv4',
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Connection': 'keep-alive',
                    }
                }
            )

            app.logger.debug(f"Searching for track: {spotify_url}")
            songs = spotdl.search([spotify_url])

            if not songs:
                return jsonify({'error': 'Song not found'}), 404

            app.logger.debug(f"Found song: {songs[0].title}")
            song, file_path = spotdl.download(songs[0])

            if file_path and file_path.exists():
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=f"{songs[0].artist} - {songs[0].title}.mp3",
                    mimetype='audio/mpeg'
                )

            return jsonify({'error': 'Download or conversion failed'}), 500

    except Exception as e:
        app.logger.error(f"Error during download: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    """Render the homepage."""
    return render_template('index.html')


@app.route('/track-info', methods=['POST'])
def get_info():
    """Fetch and return track metadata."""
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    track_info = get_track_info(url)
    if track_info:
        return jsonify(track_info)
    return jsonify({'error': 'Could not fetch track info'}), 500


@app.route('/privacy')
def privacy():
    """Render the privacy policy page."""
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    """Render the terms and conditions page."""
    return render_template('terms.html')


if __name__ == '__main__':
    app.run(debug=True)
