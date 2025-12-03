let recentDetections = [];
let alertsInterval = null;
let currentStreamUrl = null;
let latestAlertSeen = 0;

// File input handler
document.getElementById('videoFile').addEventListener('change', function(e) {
    const label = document.getElementById('fileLabel');
    const labelText = document.getElementById('fileLabelText');
    
    if (e.target.files.length > 0) {
        const fileName = e.target.files[0].name;
        labelText.textContent = fileName;
        label.classList.add('has-file');
        
        showVideoPreview(e.target.files[0]);
    } else {
        labelText.textContent = 'Seleccionar video';
        label.classList.remove('has-file');
    }
});

function showVideoPreview(file) {
    const videoDisplay = document.getElementById('videoDisplay');
    const displayTitle = document.getElementById('displayTitle');
    const videoFrame = document.getElementById('videoFrame');
    const statusBadgeContainer = document.getElementById('statusBadgeContainer');
    const stopBtn = document.getElementById('stopBtn');
    
    videoFrame.classList.remove('empty');
    videoFrame.innerHTML = `
        <div style="color: var(--muted); font-size: 0.875rem;">
            Presiona "Procesar Video" para ver la detección en tiempo real
        </div>
    `;
    
    displayTitle.textContent = 'Listo para Procesar';
    statusBadgeContainer.style.display = 'none';
    stopBtn.style.display = 'none';
}

function showAlert(containerId, message, type) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => {
        container.innerHTML = '';
    }, 5000);
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = '';
    if (type === 'success') {
        icon = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
        </svg>`;
    } else if (type === 'error') {
        icon = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>`;
    } else if (type === 'info') {
        icon = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>`;
    }
    
    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">${message}</div>
        <div class="toast-close" onclick="this.parentElement.remove()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

function addDetection(imageUrl, timestamp) {
    const detection = {
        id: Date.now(),
        timestamp: timestamp ? new Date(timestamp) : new Date(),
        imageUrl: imageUrl
    };
    
    recentDetections.unshift(detection);
    if (recentDetections.length > 10) {
        recentDetections.pop();
    }
    
    updateCarousel();
}

async function loadRecentAlerts() {
    try {
        const res = await fetch('/api/alerts/recent');
        if (!res.ok) return;
        const data = await res.json();
        if (!Array.isArray(data)) return;

        // Detectar nuevo alerta (ordenado descendente desde backend)
        if (data.length > 0) {
            const newestTs = data[0].timestamp ? data[0].timestamp * 1000 : Date.now();
            if (latestAlertSeen === 0) {
                latestAlertSeen = newestTs; // primera carga, no toastear
            } else if (newestTs > latestAlertSeen) {
                latestAlertSeen = newestTs;
                showToast('⚠️ Nueva alerta de arma detectada y notificada');
            }
        }

        recentDetections = data.map(item => ({
            id: item.image,
            imageUrl: item.image,
            timestamp: item.timestamp ? new Date(item.timestamp * 1000) : new Date(),
        }));
        updateCarousel();
    } catch (e) {
        console.error('No se pudieron cargar alertas recientes', e);
    }
}

function startAlertsPolling(intervalMs = 3000) {
    stopAlertsPolling();
    loadRecentAlerts();
    alertsInterval = setInterval(loadRecentAlerts, intervalMs);
}

function stopAlertsPolling() {
    if (alertsInterval) {
        clearInterval(alertsInterval);
        alertsInterval = null;
    }
}

function updateCarousel() {
    const track = document.getElementById('carouselTrack');
    
    if (recentDetections.length === 0) {
        track.innerHTML = '<div class="empty-carousel">No hay detecciones registradas aún</div>';
        return;
    }
    
    track.innerHTML = recentDetections.map(detection => {
        const date = new Date(detection.timestamp);
        const timeStr = date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        const dateStr = date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
        const cacheBust = detection.timestamp instanceof Date ? detection.timestamp.getTime() : Date.now();
        const imgSrc = `${detection.imageUrl}?t=${cacheBust}`;
        
        return `
            <div class="detection-item">
                <div class="detection-thumbnail" onclick="openModal('${detection.imageUrl}')">
                    <img src="${imgSrc}" alt="Detección">
                </div>
                <div class="detection-info">
                    <div class="detection-time">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                        ${timeStr} · ${dateStr}
                    </div>
                    <div class="detection-badge">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                            <line x1="12" y1="9" x2="12" y2="13"/>
                            <line x1="12" y1="17" x2="12.01" y2="17"/>
                        </svg>
                        Arma detectada
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function uploadVideo() {
    const fileInput = document.getElementById('videoFile');
    const uploadBtn = document.getElementById('uploadBtn');
    
    if (!fileInput.files.length) {
        showAlert('uploadAlert', 'Por favor selecciona un video', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<div class="loading"></div> Procesando...';
    
    fetch('/detect/video', { method: 'POST', body: formData })
        .then(r => {
            if (!r.ok) throw new Error('Error en la carga');
            return r.json();
        })
        .then(res => {
            const streamUrl = res.stream_url || `/stream/video?file=${res.file}`;
            // Mostrar stream de inmediato mientras se procesa en segundo plano
            showStream(streamUrl, 'Video Subido - Detección en Vivo');
            // Cargar alertas guardadas (todas) desde backend (pequeño delay para que se escriban)
            setTimeout(startAlertsPolling, 1500);
            showAlert('uploadAlert', 'Video procesado exitosamente', 'success');
        })
        .catch(err => {
            showAlert('uploadAlert', 'Error al procesar el video: ' + err.message, 'error');
        })
        .finally(() => {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = 'Procesar Video';
        });
}

function showWebcam() {
    // 1) Iniciar la detección en el backend
    fetch('/detect/webcam', { method: 'POST' })
        .then(r => {
            if (!r.ok) throw new Error("No se pudo iniciar la detección en webcam");
            return r.json();
        })
        .then(() => {
            // 2) Mostrar el stream anotado
            const streamUrl = '/stream';
            showStream(streamUrl, 'Webcam - Detección en Vivo');

            // 3) Iniciar el polling para ver nuevas alertas
            startAlertsPolling();

            showToast("Detección de webcam iniciada correctamente.", "success");
        })
        .catch(err => {
            console.error(err);
            showAlert('uploadAlert', err.message, 'error');
        });
}

function showRTSP() {
    const url = document.getElementById('rtspInput').value.trim();
    
    if (!url) {
        showAlert('rtspAlert', 'Por favor ingresa una URL RTSP válida', 'error');
        return;
    }

    if (!url.startsWith('rtsp://')) {
        showAlert('rtspAlert', 'La URL debe comenzar con rtsp://', 'error');
        return;
    }

    const streamUrl = `/stream/rtsp?url=${encodeURIComponent(url)}`;
    showStream(streamUrl, 'Cámara RTSP - Detección en Vivo');
    startAlertsPolling();
    showAlert('rtspAlert', 'Conectado a cámara RTSP', 'success');
}

function showStream(streamUrl, title) {
    const videoDisplay = document.getElementById('videoDisplay');
    const displayTitle = document.getElementById('displayTitle');
    const videoFrame = document.getElementById('videoFrame');
    const statusBadgeContainer = document.getElementById('statusBadgeContainer');
    const stopBtn = document.getElementById('stopBtn');
    
    videoFrame.classList.remove('empty');
    videoFrame.innerHTML = `<img id="streamImg" src="${streamUrl}" alt="Stream de detección en tiempo real" style="width: 100%; height: auto;">`;
    currentStreamUrl = streamUrl;
    
    displayTitle.textContent = title;
    statusBadgeContainer.style.display = 'block';
    stopBtn.style.display = 'flex';
    startAlertsPolling();
    
    videoDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function stopTransmission() {
    const videoFrame = document.getElementById('videoFrame');
    const statusBadgeContainer = document.getElementById('statusBadgeContainer');
    const stopBtn = document.getElementById('stopBtn');
    const displayTitle = document.getElementById('displayTitle');
    const streamImg = document.getElementById('streamImg');
    
    if (streamImg) {
        streamImg.src = '';
    }
    currentStreamUrl = null;
    videoFrame.classList.add('empty');
    videoFrame.innerHTML = 'Selecciona una fuente de video para comenzar la detección';
    
    statusBadgeContainer.style.display = 'none';
    stopBtn.style.display = 'none';
    displayTitle.textContent = 'Detección en Tiempo Real';
    stopAlertsPolling();
    // Notificar al backend para detener la captura
    fetch('/stream/stop', { method: 'POST' }).catch(() => {});
}

// Cargar alertas ya existentes al abrir la página
loadRecentAlerts();

function openModal(imageUrl) {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    
    modalImage.src = imageUrl;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(event) {
    if (event.target.classList.contains('image-modal') || 
        event.target.classList.contains('modal-close') ||
        event.target.closest('.modal-close')) {
        const modal = document.getElementById('imageModal');
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
        event.stopPropagation();
    }
}
