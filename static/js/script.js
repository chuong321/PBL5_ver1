/**
 * Script.js - Frontend logic cho ứng dụng phân loại rác
 * Xử lý WebSocket, real-time updates, và interactions
 */

// Global socket connection
let socket = null;

/**
 * Initialize socket.io connection
 */
function initSocket() {
    if (typeof io === 'undefined') {
        console.warn('Socket.IO client not loaded; skipping socket connection.');
        setServerStatus(false, 'Socket.IO client chưa được nạp');
        return;
    }

    // Xác định protocol (ws hay wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // Kết nối đến Flask-SocketIO server
    socket = io(null, {
        transports: ['websocket', 'polling'],
        reconnect: true,
        reconnection_delay: 1000,
        reconnection_delay_max: 5000,
        reconnection_attempts: 5
    });

    // Event: Connection established
    socket.on('connect', () => {
        console.log('✓ WebSocket connected');
        updateConnectionBadge(true);
        setServerStatus(true);
        showNotification('Đã kết nối thành công', 'success');
    });

    // Event: Connection lost
    socket.on('disconnect', () => {
        console.log('✗ WebSocket disconnected');
        updateConnectionBadge(false);
        setServerStatus(false, '✗ Mất kết nối server');
        showNotification('Mất kết nối', 'error');
    });

    // Event: Receive result from backend
    socket.on('result', (data) => {
        console.log('New result:', data);
        handleNewResult(data);
    });

    // Event: Receive response from backend
    socket.on('response', (data) => {
        console.log('Response:', data);
    });

    // Event: Error
    socket.on('error', (error) => {
        console.error('Socket error:', error);
        setServerStatus(false, '✗ Lỗi kết nối server');
        showNotification('Lỗi kết nối', 'error');
    });
}

/**
 * Update connection badge status
 */
function updateConnectionBadge(connected) {
    const badge = document.getElementById('connection-status');
    const message = document.getElementById('status-message');

    if (!badge || !message) return;

    if (connected) {
        badge.className = 'status-badge connected';
        badge.innerHTML = '🟢 Đã kết nối';
        message.textContent = 'ESP32-CAM đã kết nối - Sẵn sàng phân loại';
    } else {
        badge.className = 'status-badge disconnected';
        badge.innerHTML = '⚪ Chưa kết nối';
        message.textContent = 'Chờ kết nối từ ESP32-CAM...';
    }
}

/**
 * Update server connection indicator
 */
function setServerStatus(connected, textOverride = null) {
    const dot = document.getElementById('server-status');
    const text = document.getElementById('server-status-text');

    if (!dot || !text) return;

    dot.style.background = connected ? '#10B981' : '#f44336';
    text.textContent = textOverride || (connected ? '✓ Kết nối thành công' : '✗ Mất kết nối server');
}

/**
 * Update ESP32 connection indicator
 */
function setEsp32Status(connected) {
    const dot = document.getElementById('esp-status');
    const text = document.getElementById('esp-status-text');
    const videoStatus = document.getElementById('video-status');

    if (!dot || !text) return;

    if (connected) {
        dot.style.background = '#10B981';
        dot.style.animation = 'none';
        text.textContent = 'Đã kết nối';
        if (videoStatus) {
            videoStatus.textContent = '🟢 ESP32-CAM đã kết nối';
            videoStatus.style.color = '#10B981';
        }
    } else {
        dot.style.background = '#f44336';
        dot.style.animation = 'blink 1s infinite';
        text.textContent = 'Ngắt kết nối';
        if (videoStatus) {
            videoStatus.textContent = '⚫ Chờ kết nối...';
            videoStatus.style.color = '#4ECDC4';
        }
    }
}

/**
 * Poll ESP32 connection status from server
 */
function fetchEsp32Status() {
    fetch('/api/esp32/status')
        .then(response => {
            if (!response.ok) {
                throw new Error('Status fetch failed');
            }
            return response.json();
        })
        .then(data => {
            setServerStatus(true);
            setEsp32Status(!!data.connected);
        })
        .catch(() => {
            setServerStatus(false, '✗ Mất kết nối server');
            setEsp32Status(false);
        });
}

/**
 * Start ESP32 status polling
 */
function startEsp32StatusPolling() {
    fetchEsp32Status();
    setInterval(fetchEsp32Status, 2000);
}

/**
 * Handle new classification result
 */
function handleNewResult(data) {
    console.log('Processing new result:', data);

    // Thêm animation vào recent records
    const recentRecords = document.getElementById('recent-records');
    if (recentRecords) {
        addRecentRecord(data);
    }

    // Refresh stats
    refreshStats();

    // Show notification
    showNotification(`Phân loại thành công: ${data.label} (${data.confidence})`, 'success');
}

/**
 * Add new record to recent records list
 */
function addRecentRecord(record) {
    const container = document.getElementById('recent-records');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'table-row new-record';
    row.innerHTML = `
        <div class="col-id">#${record.id || 'N/A'}</div>
        <div class="col-label">
            <span class="badge badge-${record.label}">${record.label}</span>
        </div>
        <div class="col-confidence">${record.confidence}</div>
        <div class="col-time">${new Date().toLocaleString('vi-VN')}</div>
    `;

    container.insertBefore(row, container.firstChild);

    // Animation
    row.style.animation = 'slideIn 0.3s ease-in-out';

    // Remove oldest record if more than 10
    const rows = container.querySelectorAll('.table-row');
    if (rows.length > 10) {
        rows[rows.length - 1].remove();
    }
}

/**
 * Refresh statistics
 */
function refreshStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Update total count
            const totalCount = document.getElementById('total-count');
            if (totalCount) {
                totalCount.textContent = data.total;
            }

            // Update unique labels
            const uniqueLabels = document.getElementById('unique-labels');
            if (uniqueLabels) {
                uniqueLabels.textContent = data.labels.length;
            }

            console.log('Stats updated:', data);
        })
        .catch(error => console.error('Error refreshing stats:', error));
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    // Tạo notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;

    // Thêm vào page
    document.body.appendChild(notification);

    // Remove sau 5 giây
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

/**
 * Setup filter controls
 */
function setupFilters() {
    const labelFilter = document.getElementById('filter-label');
    const confidenceSlider = document.getElementById('filter-confidence');
    const confidenceValue = document.getElementById('confidence-value');
    const applyBtn = document.getElementById('apply-filter-btn');

    if (!confidenceSlider) return;

    // Update confidence display
    confidenceSlider.addEventListener('input', (e) => {
        confidenceValue.textContent = e.target.value + '%';
    });

    // Apply filters
    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            const label = labelFilter ? labelFilter.value : '';
            const confidence = confidenceSlider.value;

            console.log('Filters applied:', { label, confidence });
            // TODO: Thêm API call để filter
        });
    }
}

/**
 * Setup chart for dashboard
 */
function setupChart() {
    const ctx = document.getElementById('distribution-chart');
    if (!ctx) return;

    // Make sure Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded');
        return;
    }

    // Get data from page
    const labels = Array.from(document.querySelectorAll('.label-name')).map(el => el.textContent);
    const counts = Array.from(document.querySelectorAll('.label-count')).map(el => 
        parseInt(el.textContent.match(/\d+/)[0])
    );

    // Create chart
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    '#FF6B6B', '#4ECDC4', '#45B7D1',
                    '#FFA07A', '#98D8C8', '#F7DC6F'
                ],
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: {
                            size: 14
                        }
                    }
                }
            }
        }
    });
}

/**
 * Load detail statistics
 */
function loadDetailStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            const statsDiv = document.getElementById('detail-stats');
            if (!statsDiv) return;

            if (data.labels && data.labels.length > 0) {
                statsDiv.innerHTML = data.labels.map(label => `
                    <div class="stat-item">
                        <span class="stat-label">${label.label}</span>
                        <span class="stat-value">${label.count}</span>
                        <span class="stat-sub">Avg: ${(label.avg_confidence * 100).toFixed(1)}%</span>
                    </div>
                `).join('');
            } else {
                statsDiv.innerHTML = '<p>Chưa có dữ liệu</p>';
            }
        })
        .catch(error => console.error('Error loading stats:', error));
}

/**
 * Start auto-refresh timer
 */
function startAutoRefresh() {
    // Refresh every 30 seconds
    setInterval(() => {
        refreshStats();
    }, 30000);
}

/**
 * Keyboard shortcuts
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl + R: Manual refresh
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            refreshStats();
            showNotification('Đã làm mới dữ liệu', 'success');
        }

        // Ctrl + H: Go to history
        if (e.ctrlKey && e.key === 'h') {
            e.preventDefault();
            window.location.href = '/history';
        }
    });
}

/**
 * Initialize dashboard on page load
 */
function initDashboard() {
    console.log('Initializing dashboard...');

    // Update timestamp
    const timestamp = document.getElementById('update-time');
    if (timestamp) {
        timestamp.textContent = new Date().toLocaleString('vi-VN');
    }

    // Setup connections and event handlers
    initSocket();
    startEsp32StatusPolling();
    setupFilters();
    setupChart();
    setupKeyboardShortcuts();
    startAutoRefresh();

    console.log('✓ Dashboard initialized');
}

/**
 * Initialize history page
 */
function initHistory() {
    console.log('Initializing history page...');

    // Update timestamp
    const timestamp = document.getElementById('update-time');
    if (timestamp) {
        timestamp.textContent = new Date().toLocaleString('vi-VN');
    }

    // Setup filters and stats
    setupFilters();
    loadDetailStats();

    console.log('✓ History page initialized');
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Determine current page
    const path = window.location.pathname;

    if (path === '/' || path === '/index.html') {
        initDashboard();
    } else if (path === '/history') {
        initHistory();
    }
});

// Add CSS for notifications and animations
const styles = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        animation: slideInRight 0.3s ease-in-out;
    }

    .notification-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 15px;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    .notification-success .notification-content {
        background: #D1FAE5;
        color: #065F46;
    }

    .notification-error .notification-content {
        background: #FEE2E2;
        color: #991B1B;
    }

    .notification-info .notification-content {
        background: #DBEAFE;
        color: #0C4A6E;
    }

    .notification-close {
        background: none;
        border: none;
        font-size: 1.5em;
        cursor: pointer;
        color: inherit;
        opacity: 0.7;
    }

    .notification-close:hover {
        opacity: 1;
    }

    .new-record {
        animation: highlightRow 0.5s ease;
    }

    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideIn {
        from {
            transform: translateX(-30px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes highlightRow {
        0% {
            background: #FFE5B4;
        }
        100% {
            background: transparent;
        }
    }
`;

// Inject CSS
const styleElement = document.createElement('style');
styleElement.textContent = styles;
document.head.appendChild(styleElement);
