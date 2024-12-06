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
import logging
from logging.handlers import RotatingFileHandler

from spotdl import Spotdl
import urllib.parse
import yt_dlp
import tempfile
from pathlib import Path
import requests
import re
from urllib.parse import quote

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('../public/images', filename)


# # Set up file logging
# log_file = '/var/www/spotifysave/app.log'
# file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=5)
# file_handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# file_handler.setFormatter(formatter)
# app.logger.addHandler(file_handler)


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


def download_track(title, artist, spotify_url):
    try:
        output_path = f"{title} - {artist}.mp3"
        command = ['/var/www/spotifysave/venv/bin/spotdl', spotify_url, '--output', output_path]

        app.logger.debug(f"Command: {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True)

        if os.path.exists(output_path):
            return output_path
        return None

    except Exception as e:
        app.logger.exception("Download failed")
        return None


# @app.route('/download', methods=['POST'])
# def download():
#     try:
#         title = request.json.get('title')
#         artist = request.json.get('artist')
#         spotify_url = request.json.get('url')
#
#         cookie_file = '/var/www/spotifysave/cookies.txt'
#
#         with tempfile.TemporaryDirectory() as temp_dir:
#             spotdl = Spotdl(
#                 client_id='41c1c1a4546c413498d522b0f0508670',
#                 client_secret='c36781c6845448d3b97a1d30403d8bbe',
#                 downloader_settings={
#                     'output': f'{temp_dir}/%(title)s.%(ext)s',
#                     'format': 'mp3',
#                     'cookie_file': cookie_file,
#                     'yt_dlp_args': f'--cookies {cookie_file}',
#                     'audio_providers': ['youtube-music']
#                 }
#             )
#
#             songs = spotdl.search([spotify_url])
#             if not songs:
#                 return jsonify({'error': 'Song not found'}), 404
#
#             song, file_path = spotdl.download(songs[0])
#
#             if file_path and file_path.exists():
#                 response = send_file(
#                     str(file_path),
#                     mimetype='audio/mpeg',
#                     as_attachment=True,
#                     download_name=f"{title} - {artist}.mp3"
#                 )
#                 return response
#
#             return jsonify({'error': 'Download failed'}), 500
#
#     except Exception as e:
#         app.logger.error(f"Download error: {str(e)}")
#         return jsonify({'error': str(e)}), 500




@app.route('/download', methods=['POST'])
def download():
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')
        
        # Search YouTube Music
        search_query = quote(f"{title} {artist}")
        search_url = f"https://music.youtube.com/search?q={search_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://music.youtube.com'
        }
        
        response = requests.get(search_url, headers=headers)
        app.logger.debug(f"Search response length: {len(response.text)}")
        
        # Try different regex patterns
        patterns = [
            r'videoId":"([^"]+)"',
            r'watchEndpoint":{"videoId":"([^"]+)"',
            r'"videoId"\s*:\s*"([^"]+)"',
            r'/watch\?v=([a-zA-Z0-9_-]{11})'
        ]
        
        video_id = None
        for pattern in patterns:
            matches = re.finditer(pattern, response.text)
            for match in matches:
                potential_id = match.group(1)
                if len(potential_id) == 11:  # YouTube IDs are 11 characters
                    video_id = potential_id
                    app.logger.debug(f"Found video ID: {video_id}")
                    break
            if video_id:
                break
                
        if not video_id:
            app.logger.error("No video ID found in response")
            return jsonify({'error': 'Song not found'}), 404
            
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'ffmpeg_location': '/usr/bin/ffmpeg',
                'no_check_certificate': True,
                'no_warnings': True,
                'quiet': True,
                'http_headers': headers
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    app.logger.debug(f"Attempting download from: {video_url}")
                    ydl.download([video_url])
                    
                    mp3_files = list(Path(temp_dir).glob('*.mp3'))
                    if mp3_files:
                        return send_file(
                            str(mp3_files[0]),
                            mimetype='audio/mpeg',
                            as_attachment=True,
                            download_name=f"{title} - {artist}.mp3"
                        )
                except Exception as e:
                    app.logger.error(f"Download error: {str(e)}")
                    
            return jsonify({'error': 'Download failed'}), 500

    except Exception as e:
        app.logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')
        
        # First get the video ID from YouTube Music
        search_query = quote(f"{title} {artist}")
        search_url = f"https://music.youtube.com/search?q={search_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(search_url, headers=headers)
        match = re.search(r'videoId\":\"([^\"]+)\"', response.text)
        
        if not match:
            return jsonify({'error': 'Song not found'}), 404
            
        video_id = match.group(1)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'ffmpeg_location': '/usr/bin/ffmpeg',
                'no_check_certificate': True,
                'no_warnings': True,
                'quiet': True,
                'extract_flat': False,
                'http_headers': headers
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    app.logger.debug(f"Downloading from: {video_url}")
                    ydl.download([video_url])
                    
                    mp3_files = list(Path(temp_dir).glob('*.mp3'))
                    if mp3_files:
                        return send_file(
                            str(mp3_files[0]),
                            mimetype='audio/mpeg',
                            as_attachment=True,
                            download_name=f"{title} - {artist}.mp3"
                        )
                except Exception as e:
                    app.logger.error(f"Download error: {str(e)}")
                    
            return jsonify({'error': 'Download failed'}), 500

    except Exception as e:
        app.logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'cookiefile': '/var/www/spotifysave/cookies.txt',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'ffmpeg_location': '/usr/bin/ffmpeg',  # Verified path
                'proxy': 'socks5://127.0.0.1:9050',    # Tor is running
                'source_address': '0.0.0.0',
                'sleep_interval': 1,
                'max_sleep_interval': 5,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive'
                },
                'nocheckcertificate': True,
                'ignoreerrors': False
            }
            
            search_terms = [
                f"ytsearch1:{title} {artist} audio",
                f"ytsearch1:{title} {artist} official",
                f"ytsearch1:{title} by {artist}"
            ]
            
            for search_term in search_terms:
                try:
                    app.logger.debug(f"Trying search term: {search_term}")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([search_term])
                        
                        mp3_files = list(Path(temp_dir).glob('*.mp3'))
                        if mp3_files:
                            return send_file(
                                str(mp3_files[0]),
                                mimetype='audio/mpeg',
                                as_attachment=True,
                                download_name=f"{title} - {artist}.mp3"
                            )
                except Exception as e:
                    app.logger.error(f"Error with search term '{search_term}': {str(e)}")
                    continue
            
            return jsonify({'error': 'Could not download from any source'}), 500

    except Exception as e:
        app.logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'cookiefile': '/var/www/spotifysave/cookies.txt',
                'default_search': 'ytmusic',
                'socket_timeout': 30,
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'concurrent_fragment_downloads': 1,
                'ffmpeg_location': '/usr/bin/ffmpeg',
                'verbose': False,
                'extract_audio': True,
                'audio_format': 'mp3',
                'audio_quality': '192K',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            }
            
            search_term = f"ytsearch1:{title} {artist} official audio"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    app.logger.debug(f"Searching for: {search_term}")
                    ydl.download([search_term])
                    
                    mp3_files = list(Path(temp_dir).glob('*.mp3'))
                    if mp3_files:
                        return send_file(
                            str(mp3_files[0]),
                            mimetype='audio/mpeg',
                            as_attachment=True,
                            download_name=f"{title} - {artist}.mp3"
                        )
                except Exception as e:
                    app.logger.error(f"Download error: {str(e)}")
                    return jsonify({'error': str(e)}), 500
                
            return jsonify({'error': 'No files found'}), 404

    except Exception as e:
        app.logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    try:
        spotify_url = request.json.get('url')
        title = request.json.get('title')
        artist = request.json.get('artist')
        cookie_file = '/var/www/spotifysave/cookies.txt'
        
        with tempfile.TemporaryDirectory() as temp_dir:
            search_query = f"ytmusic1:{title} {artist} official music audio"
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
                'cookiefile': cookie_file,
                'cookies': cookie_file,
                'default_search': 'ytmusic',
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls'],
                        'player_skip': ['js', 'configs', 'webpage']
                    },
                    'youtubetab': ['music']
                },
                'extract_flat': False,
                'writethumbnail': True,
                'no_warnings': True,
                'quiet': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'no_color': True,
                'geo_bypass': True,
                'socket_timeout': 30,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Origin': 'https://music.youtube.com'
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # First try YouTube Music
                    yt_music_url = f"https://music.youtube.com/search?q={urllib.parse.quote(f'{title} {artist}')}"
                    ydl.download([yt_music_url])
                    
                    mp3_files = list(Path(temp_dir).glob('*.mp3'))
                    if mp3_files:
                        return send_file(
                            str(mp3_files[0]),
                            mimetype='audio/mpeg',
                            as_attachment=True,
                            download_name=f"{title} - {artist}.mp3"
                        )
                        
                    # Fallback to regular YouTube search
                    app.logger.debug("Falling back to YouTube search")
                    ydl.download([f"ytsearch1:{title} {artist} official audio"])
                    
                    mp3_files = list(Path(temp_dir).glob('*.mp3'))
                    if mp3_files:
                        return send_file(
                            str(mp3_files[0]),
                            mimetype='audio/mpeg',
                            as_attachment=True,
                            download_name=f"{title} - {artist}.mp3"
                        )
                        
                except Exception as e:
                    app.logger.error(f"YT-DLP error: {str(e)}")
                    
            return jsonify({'error': 'Download failed'}), 500

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