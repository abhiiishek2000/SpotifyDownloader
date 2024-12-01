from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
from datetime import timedelta
from pathlib import Path
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder='../src',
            static_url_path='',
            template_folder='../src')

# Update yt-dlp on startup
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


def get_download_url(title, artist):
    try:
        search_query = f"{title} {artist} audio"
        app.logger.debug(f"Searching for: {search_query}")

        # List of sources to try
        sources = [
            ('soundcloud', 'scsearch'),
            ('youtube', 'ytsearch'),
            ('deezer', 'dzsearch')
        ]

        for source_name, source_prefix in sources:
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    'extract_audio': True,
                    'default_search': source_prefix,
                    'noplaylist': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'cookiefile': 'youtube_cookies.txt' if source_name == 'youtube' else None
                }

                app.logger.info(f"Trying source: {source_name}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"{source_prefix}:{search_query}", download=False)

                    if info:
                        if 'entries' in info and info['entries']:
                            video = info['entries'][0]
                        else:
                            video = info

                        url = video.get('url')
                        if url:
                            app.logger.info(f"Found on {source_name}")
                            return {
                                'url': url,
                                'title': video.get('title', title),
                                'duration': video.get('duration', 0),
                                'source': source_name
                            }
            except Exception as e:
                app.logger.error(f"Error with {source_name}: {str(e)}")
                continue

        app.logger.error("No sources available")
        return None

    except Exception as e:
        app.logger.error(f"Download URL error: {str(e)}")
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
    try:
        title = request.json.get('title')
        artist = request.json.get('artist')

        if not title or not artist:
            return jsonify({'error': 'Title and artist required'}), 400

        app.logger.info(f"Download requested: {title} by {artist}")
        download_info = get_download_url(title, artist)

        if download_info and download_info.get('url'):
            return jsonify({
                'success': True,
                'url': download_info['url'],
                'title': download_info['title'],
                'source': download_info.get('source', 'unknown')
            })

        return jsonify({'error': 'Could not find download source'}), 404

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    return render_template('terms.html')


if __name__ == '__main__':
    app.run(debug=True)