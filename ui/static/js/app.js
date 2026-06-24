document.addEventListener('alpine:init', () => {
    Alpine.store('globalStore', {
        theme: localStorage.getItem('theme') || 'light',
        sidebarOpen: true,
        uiLevel: localStorage.getItem('uiLevel') || 'normal', // simple, normal, developer
        currentRoute: 'dashboard',
        
        // Engine State
        engineState: 'IDLE', // IDLE, RUNNING, PAUSED, ERROR, OFFLINE
        engineStateText: 'آماده',
        currentWorkflow: null,
        currentStepIndex: 0,
        totalSteps: 0,
        
        init() {
            // Set initial theme
            if (this.theme === 'dark') {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        },
        
        toggleTheme() {
            this.theme = this.theme === 'light' ? 'dark' : 'light';
            localStorage.setItem('theme', this.theme);
            if (this.theme === 'dark') {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        },
        
        setUiLevel(level) {
            this.uiLevel = level;
            localStorage.setItem('uiLevel', level);
        },
        
        // Layout-safe Monochromatic Notification System (Toast)
        showToast(message, type = 'info', duration = 4000) {
            const container = document.getElementById('toast-container');
            if (!container) return;
            
            const id = 'toast-' + Date.now();
            const toast = document.createElement('div');
            
            // Minimal Icon mapping
            let icon = '';
            let borderClass = 'border-gray-200 dark:border-gray-800';
            
            if (type === 'success') {
                icon = '<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            } else if (type === 'error') {
                icon = '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
                borderClass = 'border-red-200 dark:border-red-950/50';
            } else if (type === 'warning') {
                icon = '<svg class="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>';
            } else {
                icon = '<svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
            }
            
            toast.id = id;
            toast.className = `toast ${borderClass} mb-2 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100`;
            toast.innerHTML = `
                <div class="flex items-center gap-3 w-full">
                    <div class="shrink-0 flex items-center justify-center">${icon}</div>
                    <div class="flex-1 font-medium text-sm leading-normal">${message}</div>
                    <button onclick="document.getElementById('${id}').remove()" class="shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
            `;
            
            container.appendChild(toast);
            
            if (duration > 0) {
                setTimeout(() => {
                    const t = document.getElementById(id);
                    if (t) {
                        t.style.opacity = '0';
                        t.style.transform = 'translateY(15px)';
                        t.style.transition = 'all 0.2s ease';
                        setTimeout(() => t.remove(), 200);
                    }
                }, duration);
            }
        },
        
        playSound(type = 'alert') {
            try {
                const audio = new Audio(`/static/js/sounds/${type}.mp3`);
                audio.play().catch(e => console.log('Audio play prevented by browser policy'));
            } catch (e) {
                console.error('Error playing sound', e);
            }
        }
    });
});
