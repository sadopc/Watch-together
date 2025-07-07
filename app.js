/**
 * Modern WebRTC Streaming Application
 * RTMP to WebRTC Live Streaming Interface
 */

class StreamingApp {
    constructor() {
        // WebRTC Connection
        this.peerConnection = null;
        this.isConnected = false;
        this.receivedTracks = 0;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        
        // Media Elements
        this.videoPlayer = null;
        this.videoOverlay = null;
        
        // UI Elements
        this.statusElements = {};
        this.controlElements = {};
        
        // Stats
        this.stats = {
            video: { fps: 0, bitrate: 0, resolution: '', bytesReceived: 0 },
            audio: { bitrate: 0, bytesReceived: 0 },
            connection: { type: '', latency: 0 }
        };
        
        // Intervals
        this.statsInterval = null;
        this.healthCheckInterval = null;
        
        // Settings
        this.settings = {
            autoQuality: true,
            volume: 0.8,
            muted: true // Start muted due to autoplay policies
        };
        
        // Initialize
        this.init();
    }
    
    /**
     * Initialize the application
     */
    init() {
        this.setupDOM();
        this.setupEventListeners();
        this.setupHealthCheck();
        this.startConnection();
        
        // Show initial loading state
        this.showToast('WebRTC bağlantısı başlatılıyor...', 'info');
    }
    
    /**
     * Setup DOM element references
     */
    setupDOM() {
        // Media elements
        this.videoPlayer = document.getElementById('videoPlayer');
        this.videoOverlay = document.getElementById('videoOverlay');
        
        // Status elements
        this.statusElements = {
            dot: document.getElementById('statusDot'),
            connection: document.getElementById('connectionStatus'),
            resolution: document.getElementById('resolution'),
            fps: document.getElementById('fps'),
            videoBitrate: document.getElementById('videoBitrate'),
            audioBitrate: document.getElementById('audioBitrate'),
            latency: document.getElementById('latency'),
            connectionType: document.getElementById('connectionType'),
            serverStatus: document.getElementById('serverStatus'),
            viewerCount: document.getElementById('viewerCount')
        };
        
        // Control elements
        this.controlElements = {
            playPause: document.getElementById('playPauseBtn'),
            mute: document.getElementById('muteBtn'),
            volume: document.getElementById('volumeSlider'),
            fullscreen: document.getElementById('fullscreenBtn'),
            reconnect: document.getElementById('reconnectBtn'),
            autoQuality: document.getElementById('autoQuality'),
            qualitySelect: document.getElementById('qualitySelect')
        };
        
        // Toast container
        this.toastContainer = document.getElementById('toastContainer');
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Video player events
        this.videoPlayer.addEventListener('loadedmetadata', () => {
            this.updateVideoInfo();
            this.hideOverlay();
        });
        
        this.videoPlayer.addEventListener('play', () => {
            this.updatePlayPauseButton();
        });
        
        this.videoPlayer.addEventListener('pause', () => {
            this.updatePlayPauseButton();
        });
        
        this.videoPlayer.addEventListener('volumechange', () => {
            this.updateVolumeControls();
        });
        
        this.videoPlayer.addEventListener('error', (e) => {
            console.error('Video player error:', e);
            this.showToast('Video oynatma hatası', 'error');
        });
        
        // Control button events
        this.controlElements.playPause.addEventListener('click', () => {
            this.togglePlayPause();
        });
        
        this.controlElements.mute.addEventListener('click', () => {
            this.toggleMute();
        });
        
        this.controlElements.volume.addEventListener('input', (e) => {
            this.setVolume(parseFloat(e.target.value));
        });
        
        this.controlElements.fullscreen.addEventListener('click', () => {
            this.toggleFullscreen();
        });
        
        this.controlElements.reconnect.addEventListener('click', () => {
            this.reconnect();
        });
        
        // Quality controls
        this.controlElements.autoQuality.addEventListener('change', (e) => {
            this.settings.autoQuality = e.target.checked;
            this.controlElements.qualitySelect.disabled = e.target.checked;
            if (e.target.checked) {
                this.controlElements.qualitySelect.value = 'auto';
            }
        });
        
        this.controlElements.qualitySelect.addEventListener('change', (e) => {
            if (!this.settings.autoQuality) {
                this.changeQuality(e.target.value);
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
        
        // Window events
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
        
        // Visibility change (tab focus)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseStatsUpdates();
            } else {
                this.resumeStatsUpdates();
            }
        });
    }
    
    /**
     * Setup health check for server status
     */
    setupHealthCheck() {
        this.healthCheckInterval = setInterval(() => {
            this.checkServerHealth();
        }, 30000); // Check every 30 seconds
        
        // Initial check
        this.checkServerHealth();
    }
    
    /**
     * Check server health status
     */
    async checkServerHealth() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            this.statusElements.serverStatus.textContent = data.status === 'healthy' ? 'Online' : 'Offline';
            this.statusElements.serverStatus.className = `status-value ${data.status === 'healthy' ? 'online' : 'offline'}`;
            this.statusElements.viewerCount.textContent = data.active_peers || '-';
            
            if (data.status !== 'healthy' && this.isConnected) {
                this.showToast('Sunucu bağlantı problemi tespit edildi', 'warning');
            }
        } catch (error) {
            console.error('Health check failed:', error);
            this.statusElements.serverStatus.textContent = 'Offline';
            this.statusElements.serverStatus.className = 'status-value offline';
        }
    }
    
    /**
     * Start WebRTC connection
     */
    async startConnection() {
        try {
            // Cleanup existing connection
            if (this.peerConnection) {
                this.peerConnection.close();
                this.peerConnection = null;
            }
            
            this.receivedTracks = 0;
            this.updateConnectionStatus('Bağlantı kuruluyor...', 'connecting');
            this.showOverlay();
            
            // Create peer connection
            this.peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' }
                ]
            });
            
            // Setup peer connection event handlers
            this.setupPeerConnectionEvents();
            
            // Add transceivers
            this.peerConnection.addTransceiver('video', { direction: 'recvonly' });
            this.peerConnection.addTransceiver('audio', { direction: 'recvonly' });
            
            // Create and send offer
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);
            
            const response = await fetch('/offer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sdp: this.peerConnection.localDescription.sdp,
                    type: this.peerConnection.localDescription.type,
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const answer = await response.json();
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
            
            // Reset reconnect attempts on successful connection setup
            this.reconnectAttempts = 0;
            
        } catch (error) {
            console.error('Connection error:', error);
            this.updateConnectionStatus('Bağlantı hatası', 'error');
            this.showToast(`Bağlantı hatası: ${error.message}`, 'error');
            this.handleConnectionError();
        }
    }
    
    /**
     * Setup peer connection event handlers
     */
    setupPeerConnectionEvents() {
        // ICE connection state changes
        this.peerConnection.addEventListener('iceconnectionstatechange', () => {
            const state = this.peerConnection.iceConnectionState;
            console.log('ICE Connection State:', state);
            
            switch (state) {
                case 'connected':
                case 'completed':
                    this.isConnected = true;
                    this.updateConnectionStatus('Yayın bekleniyor...', 'connected');
                    this.hideReconnectButton();
                    this.startStatsUpdates();
                    break;
                    
                case 'disconnected':
                    this.isConnected = false;
                    this.updateConnectionStatus('Bağlantı kesildi', 'disconnected');
                    this.showToast('Bağlantı kesildi, yeniden bağlanmaya çalışılıyor...', 'warning');
                    this.handleConnectionError();
                    break;
                    
                case 'failed':
                    this.isConnected = false;
                    this.updateConnectionStatus('Bağlantı başarısız', 'error');
                    this.showToast('Bağlantı başarısız oldu', 'error');
                    this.handleConnectionError();
                    break;
                    
                case 'closed':
                    this.isConnected = false;
                    this.updateConnectionStatus('Bağlantı kapalı', 'disconnected');
                    this.stopStatsUpdates();
                    break;
            }
        });
        
        // Track received
        this.peerConnection.addEventListener('track', (event) => {
            console.log('Track received:', event.track.kind);
            
            // Attach stream to video element
            if (!this.videoPlayer.srcObject) {
                this.videoPlayer.srcObject = event.streams[0];
            }
            
            this.receivedTracks++;
            
            // Apply initial settings
            this.videoPlayer.muted = this.settings.muted;
            this.videoPlayer.volume = this.settings.volume;
            
            // Update UI when all tracks are received
            if (this.receivedTracks === 2) { // 1 video + 1 audio
                this.updateConnectionStatus('Yayın aktif', 'streaming');
                this.showToast('Yayın başarıyla bağlandı', 'success');
                
                // Try to play (may fail due to autoplay policies)
                this.videoPlayer.play().catch(e => {
                    console.log('Autoplay prevented:', e);
                    this.showToast('Yayını başlatmak için tıklayın', 'info');
                });
            }
        });
        
        // Data channel (if needed for future features)
        this.peerConnection.addEventListener('datachannel', (event) => {
            console.log('Data channel received:', event.channel.label);
        });
    }
    
    /**
     * Handle connection errors and implement reconnection logic
     */
    handleConnectionError() {
        this.showReconnectButton();
        this.stopStatsUpdates();
        
        // Auto-reconnect logic
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
            
            setTimeout(() => {
                if (!this.isConnected) {
                    console.log(`Auto-reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
                    this.startConnection();
                }
            }, delay);
        } else {
            this.showToast('Maksimum yeniden bağlanma denemesi aşıldı', 'error');
        }
    }
    
    /**
     * Manual reconnection
     */
    reconnect() {
        this.reconnectAttempts = 0; // Reset counter for manual reconnection
        this.startConnection();
    }
    
    /**
     * Update connection status UI
     */
    updateConnectionStatus(message, state) {
        this.statusElements.connection.textContent = message;
        
        // Update status dot
        this.statusElements.dot.className = 'status-dot';
        switch (state) {
            case 'connected':
            case 'streaming':
                this.statusElements.dot.classList.add('connected');
                break;
            case 'error':
            case 'failed':
                this.statusElements.dot.classList.add('error');
                break;
            default:
                // Keep default (warning/connecting) state
                break;
        }
    }
    
    /**
     * Media Control Functions
     */
    togglePlayPause() {
        if (this.videoPlayer.paused) {
            this.videoPlayer.play().catch(e => {
                console.error('Play failed:', e);
                this.showToast('Oynatma başlatılamadı', 'error');
            });
        } else {
            this.videoPlayer.pause();
        }
    }
    
    toggleMute() {
        this.videoPlayer.muted = !this.videoPlayer.muted;
        this.settings.muted = this.videoPlayer.muted;
    }
    
    setVolume(volume) {
        this.videoPlayer.volume = volume;
        this.settings.volume = volume;
        if (volume === 0) {
            this.videoPlayer.muted = true;
        } else if (this.videoPlayer.muted) {
            this.videoPlayer.muted = false;
        }
    }
    
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.videoPlayer.requestFullscreen().catch(e => {
                console.error('Fullscreen failed:', e);
                this.showToast('Tam ekran modu desteklenmiyor', 'warning');
            });
        } else {
            document.exitFullscreen();
        }
    }
    
    changeQuality(quality) {
        // Quality changes would need server-side support
        console.log('Quality change requested:', quality);
        this.showToast(`Kalite değiştiriliyor: ${quality}`, 'info');
    }
    
    /**
     * Update UI elements
     */
    updatePlayPauseButton() {
        const icon = this.controlElements.playPause.querySelector('i');
        if (this.videoPlayer.paused) {
            icon.className = 'fas fa-play';
            this.controlElements.playPause.title = 'Oynat';
        } else {
            icon.className = 'fas fa-pause';
            this.controlElements.playPause.title = 'Durdur';
        }
    }
    
    updateVolumeControls() {
        const icon = this.controlElements.mute.querySelector('i');
        if (this.videoPlayer.muted || this.videoPlayer.volume === 0) {
            icon.className = 'fas fa-volume-mute';
            this.controlElements.mute.title = 'Sesi Aç';
        } else if (this.videoPlayer.volume < 0.5) {
            icon.className = 'fas fa-volume-down';
            this.controlElements.mute.title = 'Sesi Kapat';
        } else {
            icon.className = 'fas fa-volume-up';
            this.controlElements.mute.title = 'Sesi Kapat';
        }
        
        this.controlElements.volume.value = this.videoPlayer.volume;
    }
    
    updateVideoInfo() {
        const video = this.videoPlayer;
        if (video.videoWidth && video.videoHeight) {
            this.statusElements.resolution.textContent = `${video.videoWidth}x${video.videoHeight}`;
        }
    }
    
    /**
     * Stats and monitoring
     */
    startStatsUpdates() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
        }
        
        this.statsInterval = setInterval(() => {
            this.updateStats();
        }, 1000);
    }
    
    stopStatsUpdates() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
        
        // Reset stats display
        this.resetStatsDisplay();
    }
    
    pauseStatsUpdates() {
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
    }
    
    resumeStatsUpdates() {
        if (this.isConnected && !this.statsInterval) {
            this.startStatsUpdates();
        }
    }
    
    async updateStats() {
        if (!this.peerConnection) return;
        
        try {
            const stats = await this.peerConnection.getStats();
            
            stats.forEach(report => {
                if (report.type === 'inbound-rtp') {
                    if (report.kind === 'video') {
                        this.updateVideoStats(report);
                    } else if (report.kind === 'audio') {
                        this.updateAudioStats(report);
                    }
                }
            });
            
        } catch (error) {
            console.error('Stats update failed:', error);
        }
    }
    
    updateVideoStats(report) {
        // FPS
        if (report.framesPerSecond) {
            this.stats.video.fps = Math.round(report.framesPerSecond);
            this.statusElements.fps.textContent = `${this.stats.video.fps}`;
        }
        
        // Bitrate calculation
        if (report.bytesReceived && this.stats.video.lastBytesReceived) {
            const bytesDiff = report.bytesReceived - this.stats.video.lastBytesReceived;
            const bitrate = Math.round((bytesDiff * 8) / 1000); // kbps
            this.stats.video.bitrate = bitrate;
            this.statusElements.videoBitrate.textContent = `${bitrate} kbps`;
        }
        this.stats.video.lastBytesReceived = report.bytesReceived;
    }
    
    updateAudioStats(report) {
        // Audio bitrate
        if (report.bytesReceived && this.stats.audio.lastBytesReceived) {
            const bytesDiff = report.bytesReceived - this.stats.audio.lastBytesReceived;
            const bitrate = Math.round((bytesDiff * 8) / 1000); // kbps
            this.stats.audio.bitrate = bitrate;
            this.statusElements.audioBitrate.textContent = `${bitrate} kbps`;
        }
        this.stats.audio.lastBytesReceived = report.bytesReceived;
    }
    
    resetStatsDisplay() {
        this.statusElements.fps.textContent = '-';
        this.statusElements.videoBitrate.textContent = '-';
        this.statusElements.audioBitrate.textContent = '-';
        this.statusElements.latency.textContent = '-';
        this.statusElements.connectionType.textContent = '-';
    }
    
    /**
     * UI Helper Functions
     */
    showOverlay() {
        this.videoOverlay.classList.remove('hidden');
    }
    
    hideOverlay() {
        this.videoOverlay.classList.add('hidden');
    }
    
    showReconnectButton() {
        this.controlElements.reconnect.style.display = 'inline-flex';
    }
    
    hideReconnectButton() {
        this.controlElements.reconnect.style.display = 'none';
    }
    
    /**
     * Toast notification system
     */
    showToast(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <i class="${icon}"></i>
            <span>${message}</span>
        `;
        
        this.toastContainer.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, duration);
        
        // Click to dismiss
        toast.addEventListener('click', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }
    
    getToastIcon(type) {
        switch (type) {
            case 'success': return 'fas fa-check-circle';
            case 'error': return 'fas fa-exclamation-circle';
            case 'warning': return 'fas fa-exclamation-triangle';
            case 'info': default: return 'fas fa-info-circle';
        }
    }
    
    /**
     * Keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        // Ignore if user is typing in an input
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }
        
        switch (event.key) {
            case ' ':
            case 'k':
                event.preventDefault();
                this.togglePlayPause();
                break;
            case 'm':
                event.preventDefault();
                this.toggleMute();
                break;
            case 'f':
                event.preventDefault();
                this.toggleFullscreen();
                break;
            case 'r':
                if (event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    this.reconnect();
                }
                break;
            case 'ArrowUp':
                event.preventDefault();
                this.setVolume(Math.min(1, this.videoPlayer.volume + 0.1));
                break;
            case 'ArrowDown':
                event.preventDefault();
                this.setVolume(Math.max(0, this.videoPlayer.volume - 0.1));
                break;
        }
    }
    
    /**
     * Cleanup function
     */
    cleanup() {
        // Clear intervals
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
        }
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
        }
        
        // Close peer connection
        if (this.peerConnection) {
            this.peerConnection.close();
        }
        
        // Clear media
        if (this.videoPlayer.srcObject) {
            this.videoPlayer.srcObject.getTracks().forEach(track => track.stop());
            this.videoPlayer.srcObject = null;
        }
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.streamingApp = new StreamingApp();
    console.log('Streaming application initialized');
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.streamingApp) {
        window.streamingApp.cleanup();
    }
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StreamingApp;
} 