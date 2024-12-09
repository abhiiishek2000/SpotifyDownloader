const urlInput = document.getElementById('url-input');
const downloadBtn = document.getElementById('download-btn');
const trackInfo = document.getElementById('track-info');
const trackImage = document.getElementById('track-image');
const trackTitle = document.getElementById('track-title');
const trackArtist = document.getElementById('track-artist');
const trackDuration = document.getElementById('track-duration');
const status = document.getElementById('status');
const pasteBtn = document.querySelector('.paste-btn');
const downloadTrack = document.getElementById('download-track');
const progressBar = document.getElementById('progress-bar');
const progressElement = progressBar.querySelector('.progress');
const progressText = progressBar.querySelector('.progress-text');
const spinner = document.getElementById('loading-spinner');

let currentTrackInfo = null;

const resetUI = () => {
    urlInput.value = '';
    trackInfo.style.display = 'none';
    downloadTrack.textContent = 'Download Track';
    downloadTrack.disabled = false;
    progressBar.style.display = 'none';
    status.style.display = 'none';
    status.classList.remove('loading-dots');
};

pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        urlInput.value = text;
    } catch (err) {
        console.error('Failed to read clipboard:', err);
    }
});
// Toast configuration
toastr.options = {
    "closeButton": true,
    "positionClass": "toast-top-right",
    "timeOut": "3000"
};

function showError(message) {
    toastr.error(message);
}

function showSuccess(message) {
    toastr.success(message);
}

function showInfo(message) {
    toastr.info(message);
}

downloadBtn.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a Spotify URL');
        return;
    }

    if (!url.includes('spotify.com')) {
        showError('Please enter a valid Spotify URL');
        return;
    }
    resetUI();

    spinner.style.display = 'block';
    status.style.display = 'none';
    trackInfo.style.display = 'none';
    downloadBtn.style.display = 'none';

    try {
        showInfo('Fetching track information...');
        const response = await fetch('/track-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        // Store complete track info including Spotify URL
        currentTrackInfo = {
            title: data.title,
            artist: data.artist,
            image: data.image,
            duration: data.duration,
            spotifyUrl: url  // Store the Spotify URL
        };

        trackImage.src = data.image;
        trackTitle.textContent = data.title;
        trackArtist.textContent = data.artist;
        trackDuration.textContent = data.duration;
        trackInfo.style.display = 'block';
        showSuccess('Track found successfully!');
    } catch (error) {
        showError(error.message);
        downloadBtn.style.display = 'block';
    } finally {
        spinner.style.display = 'none';
    }
});

downloadTrack.addEventListener('click', async () => {
    if (!currentTrackInfo) {
        showError('No track selected');
        return;
    }

    downloadTrack.style.display = 'none';
    progressBar.style.display = 'block';
    progressElement.style.width = '0%';
    progressText.textContent = 'Starting download...';

    try {
        const response = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: currentTrackInfo.title,
                artist: currentTrackInfo.artist,
                url: currentTrackInfo.spotifyUrl
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Download failed');
        }

        // Get total size for progress calculation
        const totalBytes = parseInt(response.headers.get('Content-Length'));

        // Stream the response
        const reader = response.body.getReader();
        const chunks = [];
        let receivedBytes = 0;
        let startTime = Date.now();

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            chunks.push(value);
            receivedBytes += value.length;

            // Calculate speed and progress
            const elapsedSeconds = (Date.now() - startTime) / 1000;
            const bytesPerSecond = receivedBytes / elapsedSeconds;
            const speedMbps = (bytesPerSecond / (1024 * 1024)).toFixed(2);

            // Update progress only if we have the total size
            if (totalBytes) {
                const progress = (receivedBytes / totalBytes) * 100;
                progressElement.style.width = `${progress}%`;
                progressText.textContent = `Downloading... ${Math.round(progress)}% (${speedMbps} MB/s)`;
            } else {
                // If no Content-Length, show downloaded size
                const downloadedMB = (receivedBytes / (1024 * 1024)).toFixed(2);
                progressText.textContent = `Downloading... ${downloadedMB}MB (${speedMbps} MB/s)`;
            }
        }

        // Create and trigger download
        const blob = new Blob(chunks, { type: 'audio/mpeg' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentTrackInfo.title} - ${currentTrackInfo.artist}.mp3`;
        document.body.appendChild(a);
        a.click();

        // Cleanup
        setTimeout(() => {
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }, 100);

        progressElement.style.width = '100%';
        progressText.textContent = 'Download complete!';
        showSuccess('Download complete!');

        setTimeout(() => {
            progressBar.style.display = 'none';
            downloadTrack.style.display = 'block';
            downloadTrack.textContent = 'Downloaded';
            downloadTrack.disabled = true;
        }, 2000);

    } catch (error) {
        showError('Download failed: ' + error.message);
        progressBar.style.display = 'none';
        downloadTrack.style.display = 'block';
        downloadTrack.disabled = false;
    }
});