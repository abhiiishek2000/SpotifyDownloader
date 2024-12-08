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

    // UI Updates: Disable download button and show progress bar
    downloadTrack.style.display = 'none';
    progressBar.style.display = 'block';
    progressElement.style.width = '0%';
    progressText.textContent = 'Searching track...';

    try {
        progressElement.style.width = '20%'; // Update progress

        // Request the track download
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

        progressElement.style.width = '40%';
        progressText.textContent = 'Downloading audio...';

        // Reading response as a stream
        const reader = response.body.getReader();
        const contentLength = parseInt(response.headers.get('Content-Length'), 10);
        if (isNaN(contentLength)) {
            throw new Error('Missing Content-Length header.');
        }

        let receivedLength = 0;
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            receivedLength += value.length;

            // Update progress
            const percentage = (receivedLength / contentLength) * 100;
            progressElement.style.width = `${40 + (percentage * 0.4)}%`;
            progressText.textContent = `Downloading: ${Math.floor(percentage)}%`;
        }

        progressElement.style.width = '90%';
        progressText.textContent = 'Finalizing...';

        // Combine chunks into a Blob
        const blob = new Blob(chunks, { type: 'audio/mpeg' });
        if (!blob.size) throw new Error('Failed to create Blob.');

        // Create and configure the save button
        const saveButton = document.createElement('a');
        saveButton.href = URL.createObjectURL(blob);
        saveButton.download = `${currentTrackInfo.title} - ${currentTrackInfo.artist}.mp3`;
        saveButton.className = 'download-btn mt-4';
        saveButton.textContent = 'Save MP3';
        saveButton.style.display = 'block';
        saveButton.style.marginTop = '1rem';

        progressElement.style.width = '100%';
        progressText.textContent = 'Ready to save!';
        setTimeout(() => {
            progressBar.style.display = 'none';
            downloadTrack.parentNode.insertBefore(saveButton, progressBar);
        }, 1000);

        // Clean up after download
        saveButton.addEventListener('click', () => {
            URL.revokeObjectURL(saveButton.href);
            saveButton.remove();
            showSuccess('Download complete!');
            downloadTrack.style.display = 'block';
            downloadTrack.textContent = 'Downloaded';
            downloadTrack.disabled = true;
        });

    } catch (error) {
        // Error handling
        showError('Download failed: ' + error.message);
        progressBar.style.display = 'none';
        downloadTrack.style.display = 'block';
        downloadTrack.disabled = false;
    }
});

