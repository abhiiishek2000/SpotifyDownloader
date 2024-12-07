import requests
from ytmusicapi import YTMusic
import subprocess


class YouTubeMusicDownloader:
    def __init__(self):
        self.ytmusic = YTMusic()
        self.session = requests.Session()

    def get_stream_url(self, video_id):
        """Get audio stream URL from video ID"""
        try:
            # Get watch playlist data which contains URLs
            data = self.ytmusic.get_watch_playlist(videoId=video_id)
            if not data or 'tracks' not in data:
                raise Exception("Could not get video data")

            # Get track details
            track = next((t for t in data['tracks'] if t['videoId'] == video_id), None)
            if not track:
                raise Exception("Track not found in playlist")

            # Return the best audio URL
            return f"https://music.youtube.com/watch?v={video_id}"

        except Exception as e:
            raise Exception(f"Failed to get stream URL: {str(e)}")

    def download_song(self, video_id, output_path):
        """Download and convert song"""
        stream_url = self.get_stream_url(video_id)

        # Download audio stream
        response = self.session.get(stream_url, stream=True)
        temp_audio = output_path.with_suffix('.m4a')

        with open(temp_audio, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Convert to MP3 using ffmpeg
        output_mp3 = output_path.with_suffix('.mp3')
        subprocess.run([
            'ffmpeg', '-i', str(temp_audio),
            '-acodec', 'libmp3lame', '-ab', '320k',
            str(output_mp3)
        ], check=True)

        # Cleanup temp file
        temp_audio.unlink()
        return output_mp3