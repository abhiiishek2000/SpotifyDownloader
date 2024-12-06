from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, Response, stream_with_context
import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import io
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

        spotdl = Spotdl(
            client_id='41c1c1a4546c413498d522b0f0508670',
            client_secret='c36781c6845448d3b97a1d30403d8bbe',
            downloader_settings={
                'format': 'mp3',
                'ffmpeg': '/usr/bin/ffmpeg',
                'cookie_file': '/var/www/spotifysave/cookies.txt',
                'threads': 1,
                'audio_providers': ['youtube-music'],
                'ytm_data': True,
                'filter_results': True
            }
        )
        
        songs = spotdl.search([spotify_url])
        if not songs:
            return jsonify({'error': 'Song not found'}), 404

        # Get audio stream and metadata
        def generate():
            audio_stream = spotdl.download_stream(songs[0])
            yield from audio_stream

        response = Response(
            stream_with_context(generate()),
            mimetype='audio/mpeg'
        )
        response.headers['Content-Disposition'] = f'attachment; filename="{title} - {artist}.mp3"'
        return response

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