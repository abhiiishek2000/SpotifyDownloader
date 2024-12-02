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
           'cookiesfrombrowser': ('chrome',),
           'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
           'http_headers': {
               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
               'Accept-Language': 'en-US,en;q=0.5',
               'Cookie': 'CONSENT=YES+; VISITOR_INFO1_LIVE=vCxkeHDQRUs; LOGIN_INFO=AFmmF2swRQIhAJxz74jOXpbr7PxW6w5KlYMpXZ0sZ7n5H_GWpDxsf9NLAiAKLkY4CnqznPrEY0LHw9zXxfRxo-80Nto_yXLYfKdQxQ:QUQ3MjNmeXJtSERjMlZWRDllUnhqTkhLUzNyMDZzbi1yd2N3RlRNeUNfLXBNNEhpMDRwR21URHVWMEYwUlN0ZUxjZGE3cEVNVWF2NmxrVXhzZmhnMnM4dE9COUR2NEpJQk5QS2ozQjJfaHAwcXFWMmFwS2pOQjM4aW5HSnVlZFA1N01YX19ETlRrWURiQUVjYWtlektEUmQ2UWZyeFJBSjJl; YSC=3Hgbq-2xn3E; GPS=1'
           }
       }

       with yt_dlp.YoutubeDL(ydl_opts) as ydl:
           ydl.download([f"ytsearch1:{title} {artist} audio"])
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