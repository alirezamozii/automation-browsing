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
        
        switch (message.type) {
            case 'state_changed':
                store.engineState = message.data.state;
                store.engineStateText = message.data.state_text || message.data.state;
                if (message.data.workflow) {
                    store.currentWorkflow = message.data.workflow;
                }
                break;
                
            case 'step_progress':
                store.currentStepIndex = message.data.step_index;
                store.totalSteps = message.data.total_steps;
                break;
                
            case 'log_entry':
                window.dispatchEvent(new CustomEvent('new-log', { detail: message.data }));
                break;
                
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
