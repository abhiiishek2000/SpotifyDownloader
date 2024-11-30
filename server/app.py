from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
from datetime import timedelta
from pathlib import Path
import os

app = Flask(__name__,
    static_folder='../src',
    static_url_path='',
    template_folder='../src')

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
        return None


def download_track(title, artist):
    downloads_path = str(Path.home() / "Downloads")
    search_query = f"{title} {artist} audio"

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'outtmpl': f'{downloads_path}/%(title)s.%(ext)s',
        'quiet': False
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{search_query}", download=True)
            file_path = f"{downloads_path}/{info['entries'][0]['title']}.mp3"

            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                return file_path if file_size > 0 else None
            return None
    except Exception as e:
        print(f"Download error: {str(e)}")
        return None


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


@app.route('/download', methods=['POST'])
def download():
    title = request.json.get('title')
    artist = request.json.get('artist')

    if not title or not artist:
        return jsonify({'error': 'Title and artist required'}), 400

    file_path = download_track(title, artist)
    if file_path and os.path.exists(file_path):
        return jsonify({
            'success': True,
            'message': f'Downloaded to: {file_path}'
        })
    return jsonify({'error': 'Download failed'}), 500

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')


if __name__ == '__main__':
    app.run(debug=True)
