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
            
            // Show connection toast if we were disconnected
            if (this.reconnectAttempts > 0) {
                Alpine.store('globalStore').showToast('اتصال به سرور برقرار شد', 'success', 3000);
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
            this.handleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket Error', error);
            // onclose will be called after onerror usually
        };
    }

    handleMessage(message) {
        const store = Alpine.store('globalStore');
        
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
                // We'll dispatch a custom event that logs.html or dashboard.html can listen to
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
                
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            
            if (this.reconnectAttempts === 1) {
                Alpine.store('globalStore').showToast('ارتباط با سرور قطع شد، در حال اتصال مجدد...', 'warning', 0);
            }
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay * this.reconnectAttempts);
        } else {
            Alpine.store('globalStore').showToast('اتصال به سرور کاملا قطع شده است. لطفا برنامه را دوباره اجرا کنید.', 'error', 0);
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
    // Determine WS URL based on current host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Using default port 8765 if we are opening directly, or window.location.host if served from FastAPI
    const host = window.location.host || 'localhost:8765';
    const wsUrl = `${protocol}//${host}/ws`;
    
    window.autoWs = new AutomationWebSocket(wsUrl);
    
    // Defer connection slightly to ensure Alpine is fully mounted
    setTimeout(() => {
        window.autoWs.connect();
    }, 500);
});
