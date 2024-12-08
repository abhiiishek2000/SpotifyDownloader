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


def download_song(video_id, output_path):
    """Download and convert song from YouTube Music."""
    try:
        stream_url = get_stream_url(video_id)
        temp_audio = output_path.with_suffix('.m4a')

        command = [
            'yt-dlp',
            '--format', 'bestaudio',
            '--extract-audio',
            '--audio-format', 'm4a',
            '--audio-quality', '0',
            '--no-check-certificate',
            '--force-ipv4',
            '--cookies', '/var/www/spotifysave/cookies.txt',  # Add our generated cookies
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36',
            '--add-header', 'Accept:*/*',
            '--add-header', 'Origin:https://www.youtube.com',
            '--add-header', 'Referer:https://www.youtube.com',
            '--no-warnings',
            '--no-playlist',
            '-o', str(temp_audio),
            stream_url
        ]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            app.logger.error(f"yt-dlp error output: {e.stderr}")
            raise Exception(f"yt-dlp error: {e.stderr}")

        if not temp_audio.exists() or temp_audio.stat().st_size == 0:
            raise Exception("Downloaded file is invalid or empty")

        # Convert to MP3
        output_mp3 = output_path.with_suffix('.mp3')
        convert_command = [
            'ffmpeg',
            '-i', str(temp_audio),
            '-acodec', 'libmp3lame',
            '-ab', '320k',
            str(output_mp3)
        ]

        subprocess.run(convert_command, check=True, capture_output=True)

        if temp_audio.exists():
            temp_audio.unlink()

        return output_mp3

    except Exception as e:
        app.logger.error(f"Error in download_song: {str(e)}")
        raise


@app.route('/download', methods=['POST'])
def download():
    try:
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')

        # Search using YTMusic
        ytmusic = YTMusic()
        search_results = ytmusic.search(f"{title} {artist}", filter="songs")

        if not search_results:
            return jsonify({'error': 'Song not found'}), 404

        video_id = search_results[0]['videoId']
        stream_url = f"https://music.youtube.com/watch?v={video_id}"

        def generate():
            # First download the audio
            yt_process = subprocess.Popen([
                'yt-dlp',
                '--format', 'bestaudio',
                '--cookies', '/var/www/spotifysave/cookies.txt',
                '--force-ipv4',
                '--no-check-certificate',
                '--no-warnings',
                '-o', '-',
                stream_url
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Then pipe it through ffmpeg for conversion
            ffmpeg_process = subprocess.Popen([
                'ffmpeg',
                '-i', 'pipe:0',
                '-f', 'mp3',
                '-acodec', 'libmp3lame',
                '-ab', '320k',
                '-ar', '44100',
                '-ac', '2',
                'pipe:1'
            ], stdin=yt_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Close yt-dlp stdout in parent process
            yt_process.stdout.close()

            # Read the converted audio data
            while True:
                data = ffmpeg_process.stdout.read(8192)
                if not data:
                    break
                yield data

            # Check for any errors
            ffmpeg_error = ffmpeg_process.stderr.read()
            yt_error = yt_process.stderr.read()

            if ffmpeg_error:
                app.logger.error(f"FFmpeg error: {ffmpeg_error.decode()}")
            if yt_error:
                app.logger.error(f"yt-dlp error: {yt_error.decode()}")

            # Wait for processes to complete
            ffmpeg_process.wait()
            yt_process.wait()

        return Response(
            generate(),
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': f'attachment; filename="{title} - {artist}.mp3"',
                'Cache-Control': 'no-cache'
            }
        )

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
