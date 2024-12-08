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

    // Disable button and show progress UI
    downloadTrack.style.display = 'none';
    progressBar.style.display = 'block';
    progressElement.style.width = '0%';
    progressText.textContent = 'Searching track...';

    try {
        // Simulate search progress
        progressElement.style.width = '20%';

        const response = await fetch('/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: currentTrackInfo.title,
                artist: currentTrackInfo.artist,
                url: currentTrackInfo.spotifyUrl
            })
        });

        // Check for non-successful HTTP response
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Download failed');
        }

        // Initialize progress tracking for the file download
        progressElement.style.width = '40%';
        progressText.textContent = 'Downloading audio...';

        const reader = response.body.getReader();
        const contentLength = response.headers.get('Content-Length');
        if (!contentLength) {
            throw new Error('Content-Length header is missing. Cannot track progress.');
        }

        let receivedLength = 0;
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            receivedLength += value.length;

            // Calculate and update progress dynamically
            const percentage = (receivedLength / contentLength) * 100;
            progressElement.style.width = `${40 + (percentage * 0.4)}%`;
            progressText.textContent = `Downloading: ${Math.floor(percentage)}%`;
        }

        // Combine chunks into a Blob
        progressElement.style.width = '90%';
        progressText.textContent = 'Finalizing...';
        const blob = new Blob(chunks, { type: 'audio/mpeg' });

        // Create a save button dynamically
        const saveButton = document.createElement('a');
        saveButton.href = URL.createObjectURL(blob);
        saveButton.download = `${currentTrackInfo.title} - ${currentTrackInfo.artist}.mp3`;
        saveButton.className = 'download-btn mt-4';
        saveButton.textContent = 'Save MP3';
        saveButton.style.display = 'block';
        saveButton.style.marginTop = '1rem';

        // Update UI and allow saving the file
        progressElement.style.width = '100%';
        progressText.textContent = 'Ready to save!';
        setTimeout(() => {
            progressBar.style.display = 'none';
            downloadTrack.parentNode.insertBefore(saveButton, progressBar);
        }, 1000);

        // Clean up resources after save
        saveButton.addEventListener('click', () => {
            URL.revokeObjectURL(saveButton.href);
            saveButton.remove();
            showSuccess('Download complete!');
            downloadTrack.style.display = 'block';
            downloadTrack.textContent = 'Downloaded';
            downloadTrack.disabled = true;
        });

    } catch (error) {
        // Handle errors gracefully and reset UI
        showError('Download failed: ' + error.message);
        progressBar.style.display = 'none';
        downloadTrack.style.display = 'block';
        downloadTrack.disabled = false;
    }
});
