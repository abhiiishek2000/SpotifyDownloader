# youtube_music_downloader.py

import requests
import subprocess
from pathlib import Path


class CustomMusicDownloader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': '*/*',
            'Origin': 'https://music.youtube.com',
            'Referer': 'https://music.youtube.com/',
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.api_key
        }

    def get_stream_url(self, video_id):
        player_url = f"https://music.youtube.com/youtubei/v1/player?key={self.api_key}"
        data = {
            "videoId": video_id,
            "context": {
                "client": {
                    "clientName": "ANDROID_MUSIC",
                    "clientVersion": "5.28.1",
                    "hl": "en",
                    "gl": "US",
                    "clientScreen": "WATCH",
                    "androidSdkVersion": 30
                }
            }
        }

        response = self.session.post(player_url, json=data, headers=self.headers)
        response.raise_for_status()

        data = response.json()
        print("API Response:", data)  # Add this for debugging

        if 'streamingData' not in data:
            raise Exception(f"No streaming data found. Response: {data}")

        formats = data['streamingData']['adaptiveFormats']
        audio_format = next(f for f in formats if f['mimeType'].startswith('audio/'))
        return audio_format['url']

    def download_audio(self, stream_url, output_path):
        response = self.session.get(stream_url, headers=self.headers, stream=True)
        temp_audio = output_path.with_suffix('.m4a')

        with open(temp_audio, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        output_mp3 = output_path.with_suffix('.mp3')
        subprocess.run([
            'ffmpeg', '-i', str(temp_audio),
            '-acodec', 'libmp3lame', '-ab', '320k',
            str(output_mp3)
        ])

        temp_audio.unlink()
        return output_mp3