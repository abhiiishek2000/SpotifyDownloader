import requests
from bs4 import BeautifulSoup
from datetime import timedelta
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
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
        # Get detailed track info
        track_info = ytmusic.get_song(video_id)

        # Construct streaming URL with required parameters
        params = {
            'v': video_id,
            'alt': 'media',
            'key': 'AIzaSyCSrmcJ3mBG2Z7kYH0GjMH5Kpxunq-bLj0'  # Optional, if needed
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Range': 'bytes=0-',
            'Origin': 'https://music.youtube.com'
        }

        # Use YouTube API endpoint for actual stream
        stream_url = f"https://youtube.googleapis.com/v/{video_id}"
        response = requests.head(stream_url, params=params, headers=headers)

        if response.status_code == 200:
            return stream_url + '?' + '&'.join(f'{k}={v}' for k, v in params.items())
        else:
            raise Exception(f"Failed to get valid stream URL: Status {response.status_code}")

    except Exception as e:
        raise Exception(f"Failed to get stream URL: {str(e)}")


def download_song(video_id, output_path):
    """Download and convert song from YouTube Music."""
    try:
        stream_url = get_stream_url(video_id)
        temp_audio = output_path.with_suffix('.m4a')

        # Use ffmpeg directly to download and convert
        download_process = subprocess.run([
            'ffmpeg',
            '-y',  # Overwrite output files
            '-http_seekable', '0',
            '-i', stream_url,
            '-c:a', 'copy',
            str(temp_audio)
        ], check=True, capture_output=True)

        if not temp_audio.exists() or temp_audio.stat().st_size == 0:
            raise Exception("Downloaded file is invalid or empty.")

        # Convert to MP3
        output_mp3 = output_path.with_suffix('.mp3')
        subprocess.run([
            'ffmpeg',
            '-y',
            '-i', str(temp_audio),
            '-acodec', 'libmp3lame',
            '-ab', '320k',
            str(output_mp3)
        ], check=True)

        # Cleanup temp file
        temp_audio.unlink()
        return output_mp3

    except subprocess.CalledProcessError as e:
        app.logger.error(f"FFmpeg error: {e.stderr.decode()}")
        raise Exception("Error processing audio file")
    except Exception as e:
        app.logger.error(f"Error in download_song: {str(e)}")
        raise



@app.route('/download', methods=['POST'])
def download():
    try:
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')

        with tempfile.TemporaryDirectory() as temp_dir:
            # Search using YTMusic
            ytmusic = YTMusic()
            search_results = ytmusic.search(f"{title} {artist}", filter="songs")

            if not search_results:
                return jsonify({'error': 'Song not found'}), 404

            video_id = search_results[0]['videoId']

            # Download the song
            output_path = Path(temp_dir) / f"{title} - {artist}"

            try:
                mp3_file = download_song(video_id, output_path)

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
