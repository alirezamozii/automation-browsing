class AutomationWebSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.heartbeatInterval = null;
    }

    connect() {
        console.log(`Connecting to WebSocket: ${this.url}`);
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log('WebSocket Connected');
            this.reconnectAttempts = 0;
            this.startHeartbeat();
            
            // Set engine status to what it actually is (or fetch it)
            const store = Alpine.store('globalStore');
            if (store) {
                // If it was offline, restore status
                if (store.engineState === 'OFFLINE') {
                    store.engineState = 'IDLE';
                    store.engineStateText = 'آماده';
                }
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Error parsing WebSocket message', e, event.data);
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket Disconnected');
            this.stopHeartbeat();
            
            const store = Alpine.store('globalStore');
            if (store) {
                store.engineState = 'OFFLINE';
                store.engineStateText = 'آفلاین (قطع اتصال)';
            }
            
            this.handleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket Error', error);
        };
    }

    handleMessage(message) {
        const store = Alpine.store('globalStore');
        if (!store) return;
        
        // Map engine states to simplified UI states
        const stateMap = {
            'idle': 'IDLE',
            'starting': 'RUNNING',
            'login': 'RUNNING',
            'navigating': 'RUNNING',
            'searching': 'RUNNING',
            'open_form': 'RUNNING',
            'fill_form': 'RUNNING',
            'saving': 'RUNNING',
            'verifying': 'RUNNING',
            'done': 'IDLE',
            'error': 'ERROR',
            'paused': 'PAUSED',
        };
        
        // Map engine states to Persian text
        const stateTextMap = {
            'idle': 'آماده',
            'starting': 'در حال شروع...',
            'login': 'ورود به سیستم',
            'navigating': 'ناوبری',
            'searching': 'جستجو',
            'open_form': 'باز کردن فرم',
            'fill_form': 'پر کردن فرم',
            'saving': 'ذخیره‌سازی',
            'verifying': 'تأیید',
            'done': 'تکمیل شد',
            'error': 'خطا',
            'paused': 'متوقف',
        };
        
        switch (message.type) {
            case 'state_changed': {
                const rawState = (message.data.state || '').toLowerCase();
                store.engineState = stateMap[rawState] || 'IDLE';
                store.engineStateText = stateTextMap[rawState] || message.data.state_text || message.data.state || 'نامشخص';
                if (message.data.workflow_name) {
                    store.currentWorkflow = message.data.workflow_name;
                }
                if (message.data.workflow) {
                    store.currentWorkflow = message.data.workflow;
                }
                break;
            }
                
            case 'step_progress':
                if (message.data.step_index !== undefined) {
                    store.currentStepIndex = message.data.step_index;
                }
                if (message.data.total_steps !== undefined) {
                    store.totalSteps = message.data.total_steps;
                }
                break;
                
            case 'log_entry': {
                const logData = message.data;
                
                // Extract step progress from log messages
                if (logData.message) {
                    // Update step progress from step_started/step_completed events
                    if (logData.step_index !== undefined) {
                        store.currentStepIndex = logData.step_index;
                    }
                    if (logData.total_steps !== undefined) {
                        store.totalSteps = logData.total_steps;
                    }
                }
                
                // Dispatch for live logs in dashboard
                window.dispatchEvent(new CustomEvent('new-log', { detail: logData }));
                break;
            }
                
            case 'error':
                store.showToast(message.data.message || 'خطای غیرمنتظره رخ داد', 'error');
                store.playSound('error');
                break;
                
            case 'notification':
                store.showToast(message.data.message, message.data.level || 'info');
                if (message.data.play_sound) {
                    store.playSound('alert');
                }
                break;
                
            case 'update_progress':
                if (store.updateModal) {
                    store.updateModal.percent = message.data.percent || message.percent || 0;
                    store.updateModal.speed = message.data.speed || message.speed || '0 MB/s';
                    store.updateModal.status = message.data.status || message.status || 'downloading';
                }
                break;
                
            case 'heartbeat':
            case 'pong':
                // Silently ignore heartbeat and pong
                break;
                
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            console.error('WebSocket Reconnection failed completely.');
        }
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 10000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
}

// Initialize WebSocket when Alpine is ready
document.addEventListener('alpine:init', () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8765';
    const wsUrl = `${protocol}//${host}/ws`;
    
    window.autoWs = new AutomationWebSocket(wsUrl);
    
    setTimeout(() => {
        window.autoWs.connect();
    }, 500);
});
