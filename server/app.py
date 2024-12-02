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

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
   static_folder='../src',
   static_url_path='',
   template_folder='../src')

os.system('pip install -U yt-dlp')

@app.route('/images/<path:filename>')
def serve_image(filename):
   return send_from_directory('../public/images', filename)

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


def create_youtube_cookie_file():
    cookie_content = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file!  Do not edit.

.youtube.com	TRUE	/	FALSE	2597573456	CONSENT	YES+cb
.youtube.com	TRUE	/	FALSE	2597573456	GPS	1
.youtube.com	TRUE	/	FALSE	2597573456	VISITOR_INFO1_LIVE	vCxkeHDQRUs
.youtube.com	TRUE	/	FALSE	2597573456	LOGIN_INFO	AFmmF2swRQIhAJxz74jOXpbr7PxW6w5KlYMpXZ0sZ7n5H_GWpDxsf9NLAiAKLkY4CnqznPrEY0LHw9zXxfRxo-80Nto_yXLYfKdQxQ:QUQ3MjNmeXJtSERjMlZWRDllUnhqTkhLUzNyMDZzbi1yd2N3RlRNeUNfLXBNNEhpMDRwR21URHVWMEYwUlN0ZUxjZGE3cEVNVWF2NmxrVXhzZmhnMnM4dE9COUR2NEpJQk5QS2ozQjJfaHAwcXFWMmFwS2pOQjM4aW5HSnVlZFA1N01YX19ETlRrWURiQUVjYWtlektEUmQ2UWZyeFJBSjJl"""

    cookie_file = os.path.join(os.path.dirname(__file__), 'youtube.cookies')
    with open(cookie_file, 'w') as f:
        f.write(cookie_content)

    # Set permissions
    os.chmod(cookie_file, 0o644)
    return cookie_file


def download_track(title, artist):
    try:
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, f'{title} - {artist}.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'no_check_certificate': True,
            'extractor_args': {
                'youtube': {
                    'nocheckcertificate': True,
                    'no_warnings': True,
                    'format': 'bestaudio/best'
                }
            },
            'external_downloader': 'aria2c',
            'external_downloader_args': ['--min-split-size=1M', '--max-connection-per-server=16']
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_result = ydl.extract_info(f"scsearch1:{title} {artist} audio", download=False)
            if search_result.get('entries'):
                video_url = search_result['entries'][0]['url']
                ydl.download([video_url])
                final_file = os.path.join(temp_dir, f'{title} - {artist}.mp3')
                if os.path.exists(final_file):
                    return final_file
        return None

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return None

@app.route('/download', methods=['POST'])
def download():
   try:
       title = request.json.get('title')
       artist = request.json.get('artist')

       if not title or not artist:
           return jsonify({'error': 'Title and artist required'}), 400

       file_path = download_track(title, artist)
       if file_path and os.path.exists(file_path):
           return send_file(
               file_path,
               as_attachment=True,
               download_name=f'{title} - {artist}.mp3',
               mimetype='audio/mpeg'
           )
       return jsonify({'error': 'Download failed'}), 500

   except Exception as e:
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