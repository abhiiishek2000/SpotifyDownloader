import logging
import os
import tempfile
from datetime import timedelta

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from spotdl import Spotdl

logging.basicConfig(level=logging.DEBUG)

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
        app.logger.error(f"Error getting track info: {str(e)}")
        return None



def download_track(title, artist):
    try:
        temp_dir = tempfile.mkdtemp()
        spotdl = Spotdl()

        # Create song object
        search_query = f"{title} {artist}"
        app.logger.debug(f"Searching for: {search_query}")

        # Search for songs
        songs = spotdl.search([search_query])

        if songs:
            # Download the first matching song
            song = songs[0]
            app.logger.debug(f"Found song: {song.name} by {song.artist}")

            try:
                # Set output path
                output_path = os.path.join(temp_dir, f"{title} - {artist}.mp3")

                # Download the song
                download_info = spotdl.download(songs[0])

                if download_info and os.path.exists(download_info[0]):
                    # Move file to desired location if needed
                    if download_info[0] != output_path:
                        os.rename(download_info[0], output_path)
                    return output_path

            except Exception as e:
                app.logger.error(f"Download error: {str(e)}")

        return None

    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
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