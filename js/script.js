const state = {
    currentView: 'global',
    currentUser: {
        name: 'GHOST',
        pubkey: null
    },
    messages: {
        global: [
            { id: 1, user: 'SYSTEM', text: '* P2P mesh network initialized', type: 'system', time: '23:47:12' },
            { id: 2, user: 'VOID', text: 'кто тут есть?', type: 'chat', time: '23:47:15' },
            { id: 3, user: 'ECHO', text: 'всегда тут', type: 'chat', time: '23:47:42' },
            { id: 4, user: 'STATIC', text: 'приём', type: 'chat', time: '23:48:03' },
            { id: 6, user: 'NOISE', text: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', type: 'chat', time: '23:49:12' },
            { id: 7, user: 'SYSTEM', text: '* peer joined: WAVE', type: 'system', time: '23:49:45' },
            { id: 8, user: 'SYSTEM', text: '* тестовые картинки в /assets/images/', type: 'system', time: '23:49:50' },
            { id: 9, user: 'GHOST', text: 'смотрите [IMG: img.png]', type: 'chat', time: '23:50:00' },
            { id: 10, user: 'GHOST', text: 'а это гифка [IMG: img.gif]', type: 'chat', time: '23:50:05' },
        ],
        private: [
            { id: 1, user: 'STATIC', text: 'ты получил тот файл?', type: 'whisper', time: '23:50:15' },
            { id: 2, user: 'GHOST', text: 'да. что это?', type: 'whisper', time: '23:50:42' },
            { id: 3, user: 'STATIC', text: 'просто сохрани, пригодится', type: 'whisper', time: '23:51:03' }
        ],
        feed: [
            { id: 1, user: 'VOID', text: 'сегодня нашел старый модем. работает', type: 'feed', time: '23:52:10' },
            { id: 2, user: 'ECHO', text: 'вышел из сети. вернусь когда остынут сервера', type: 'feed', time: '23:53:22' },
            { id: 4, user: 'NOISE', text: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ ', type: 'feed', time: '23:55:30' },
            { id: 5, user: 'PIXEL', text: '// TODO: выпить кофе, взломать мэйнфрейм, лечь спать', type: 'feed', time: '23:56:18' },
            { id: 6, user: 'WAVE', text: 'кто знает как вставить картинку? [IMG: skull.gif]', type: 'feed', time: '23:57:44' },
            { id: 7, user: 'PIXEL', text: 'локальный файл assets/images/img.png', type: 'feed', time: '23:58:00' },
        ],
        myvoid: [
            { id: 1, user: 'YOU', text: 'это моя стена. никто не видит пока не зайдет', type: 'myvoid', time: '23:58:00' },
            { id: 2, user: 'YOU', text: 'p2p чат. без серверов. просто так.', type: 'myvoid', time: '23:58:30' },
            { id: 3, user: 'YOU', text: 'надо переписать ядро. завтра.', type: 'myvoid', time: '23:59:15' },
        ]
    },
    users: ['GHOST', 'VOID', 'ECHO', 'STATIC', 'PIXEL', 'NOISE', 'WAVE']
};

const views = {
    global: document.getElementById('view-global'),
    private: document.getElementById('view-private'),
    feed: document.getElementById('view-feed'),
    myvoid: document.getElementById('view-myvoid'),
    manifest: document.getElementById('view-manifest')
};
const privateUsersList = document.getElementById('privateUsersList');
const navItems = document.querySelectorAll('.nav-item');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
let attachedFiles = [];

function init() {
    renderView('global');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            switchView(view);
        });
    });
    
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    initMouseNavigation();
    
    setInterval(spawnRandomMessage, 30000);
    attachBtn.addEventListener('click', () => {
	    fileInput.click();
    });
    fileInput.addEventListener('change', (e) => {
	    attachedFiles = Array.from(e.target.files);
	    showAttachPreview(); 
    });
}

function switchView(viewName) {
    navItems.forEach(item => item.classList.remove('active'));
    Object.values(views).forEach(view => {
        if (view) view.classList.remove('active');
    });
    
    const activeNav = document.querySelector(`[data-view="${viewName}"]`);
    if (activeNav) activeNav.classList.add('active');
    
    const activeView = views[viewName];
    if (activeView) activeView.classList.add('active');
    
    state.currentView = viewName;
    renderView(viewName);
}

function renderView(viewName) {
    const view = views[viewName];
    if (!view) return;
    
    if (viewName === 'manifest') return;
    
    view.innerHTML = '';
    
    if (viewName === 'private') {
        const usersDiv = document.createElement('div');
        usersDiv.className = 'users-list';
        usersDiv.style.marginBottom = '15px';
        
        state.users.forEach(user => {
            if (user !== state.currentUser.name) {
                const span = document.createElement('span');
                span.textContent = user;
                span.style.cursor = 'pointer';
                span.onclick = () => {
                    messageInput.value = `@${user} `;
                    messageInput.focus();
                };
                usersDiv.appendChild(span);
            }
        });
        
        view.appendChild(usersDiv);
    }
    
    const messagesDiv = document.createElement('div');
    messagesDiv.style.height = viewName === 'private' ? 'calc(100% - 100px)' : '100%';
    messagesDiv.style.overflowY = 'auto';
    
    const messages = state.messages[viewName] || [];
    messages.forEach(msg => {
        messagesDiv.appendChild(createMessageElement(msg));
    });
    
    view.appendChild(messagesDiv);
    view.scrollTop = view.scrollHeight;
}

function getColorFromString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = 120 + (hash % 60);
    const sat = 70 + (hash % 30);   
    const light = 40 + (hash % 20); 
    return `hsl(${hue}, ${sat}%, ${light}%)`;
}

function createMessageElement(msg) {
    const div = document.createElement('div');
    div.className = 'message';

    const userColor = msg.user === 'SYSTEM' ? '#ff0' : getColorFromString(msg.user);
    div.style.borderLeftColor = userColor;

    if (msg.type === 'system') div.classList.add('system');
    else if (msg.type === 'whisper') div.classList.add('whisper');
    else if (msg.type === 'feed') div.classList.add('feed');
    
    let username = msg.user;
    if (msg.type === 'feed') username = '>' + username;
    else if (msg.type === 'whisper') username = '*' + username;
    
    let contentHtml = msg.text;

    contentHtml = contentHtml.replace(/\[IMG:([^\]]+)\]/g, (match, filename) => {

        const cleanFilename = filename.trim();
        return `<img src="assets/images/${cleanFilename}" 
            style="max-width: 200px; max-height: 150px; border: 1px solid #00d480; margin: 5px 0;" 
            onerror="this.onerror=null; this.src='https://i.imgur.com/${cleanFilename}';"
            >`;
    });

    const urlRegex = /(https?:\/\/[^\s]+)/g;
    contentHtml = contentHtml.replace(urlRegex, url => {
	    if (url.match(/\.(jpeg|jpg|gif|png|webp|bmp|svg)$/i)) {

            const filename = url.split('/').pop();
            return `<img src="assets/images/${filename}" 
                style="max-width: 200px; max-height: 150px; border: 1px solid #00d480; margin: 5px 0;" 
                onerror="this.onerror=null; this.src='${url}';"
                alt="${filename}">`;
        }

	    else if (url.match(/\.(mp4|webm|ogg|mov)$/i)) {
	    return `<video controls style="max-width: 300px; max-height: 200px; border: 1px solid #00d480;">
            <source src="${url}" type="video/${url.split('.').pop()}">
        </video>`;
	    }
	    else {
		    return `<a href="${url}" target="_blank" style="color:#8ff"link/>[LINK]</a>`;
	    }
	    });
    div.innerHTML = `
        <div class="meta">
            ${username} <span class="time">${msg.time}</span>
        </div>
        <div class="content">
            ${contentHtml}
        </div>
    `;
    
    return div;
}

function showAttachPreview() {

    const oldPreview = document.querySelector('.attach-preview');
    if (oldPreview) oldPreview.remove();

    if (attachedFiles.length === 0) return;

    const preview = document.createElement('div');
    preview.className = 'attach-preview';

    attachedFiles.forEach(file => {
        if (file.type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.onload = () => URL.revokeObjectURL(img.src);
            preview.appendChild(img);
        } else {
            const span = document.createElement('span');
            span.textContent = `📄 ${file.name}`;
            preview.appendChild(span);
        }
    });

    const inputArea = document.getElementById('inputArea');
    inputArea.parentNode.insertBefore(preview, inputArea);
}

function sendMessage() {
    const text = messageInput.value.trim();
    if (attachedFiles.length > 0) {
        attachedFiles.forEach(file => {
            const fileMsg = `[FILE: ${file.name}] (${(file.size/1024).toFixed(1)}KB)`;
            text = text ? text + ' ' + fileMsg : fileMsg;
            
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    setTimeout(() => {
                        const imgMsg = {
                            id: Date.now(),
                            user: state.currentUser.name,
                            text: `[IMG: ${e.target.result}]`,
                            type: 'chat',
                            time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
                        };
                        state.messages.global.push(imgMsg);
                        if (state.currentView === 'global') renderView('global');
                    }, 100);
                };
                reader.readAsDataURL(file);
            }
        });
        
        attachedFiles = [];
        fileInput.value = '';
        const preview = document.querySelector('.attach-preview');
        if (preview) preview.remove();
    }
    
    if (!text) return;
    const now = new Date();
    const time = now.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false 
    });
    
    let type = 'chat';
    let user = state.currentUser.name;
    
    if (text.startsWith('> ')) {
        type = 'feed';
        text = text.substring(2);
        user = '>' + user;
    } else if (text.startsWith('@')) {
        const match = text.match(/^@(\w+)\s+(.+)$/);
        if (match) {
            type = 'whisper';
            text = match[2];
            user = '*' + user + '→' + match[1];
        }
    }
    
    const newMsg = {
        id: Date.now(),
        user: user.replace('>', '').replace(/\*.*/, '') || state.currentUser.name,
        text: text,
        type: type === 'chat' ? 'chat' : type,
        time: time
    };
    
    if (type === 'feed') {
        state.messages.feed.push(newMsg);
        if (state.currentView === 'feed') renderView('feed');
    } else if (type === 'whisper') {
        state.messages.private.push(newMsg);
        if (state.currentView === 'private') renderView('private');
    } else {
        state.messages.global.push(newMsg);
        if (state.currentView === 'global') renderView('global');
    }
    
    messageInput.value = '';
}

function spawnRandomMessage() {
    if (Math.random() > 0.5) return; // 50% шанс
    
    const users = state.users.filter(u => u !== state.currentUser.name);
    if (users.length === 0) return;
    
    const randomUser = users[Math.floor(Math.random() * users.length)];
    const messages = [
        '...',
        'ни о чем',
        'кто здесь',
        'получен сигнал',
        'я тебя вижу',
        '⧗',
        '/dev/null',
        '42',
        'error: core dumped'
    ];
    
    const now = new Date();
    const time = now.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false 
    });
    
    const newMsg = {
        id: Date.now(),
        user: randomUser,
        text: messages[Math.floor(Math.random() * messages.length)],
        type: 'chat',
        time: time
    };
    
    state.messages.global.push(newMsg);
    if (state.currentView === 'global') {
        renderView('global');
    }
}

function initMouseNavigation() {
    const viewOrder = ['global', 'private', 'feed', 'myvoid', 'manifest'];
    
    window.addEventListener('mouseup', function(e) {
        if (e.button === 3 || e.which === 3) {
            e.preventDefault();
            const currentIndex = viewOrder.indexOf(state.currentView);
            let newIndex = currentIndex - 1;
            if (newIndex < 0) newIndex = viewOrder.length - 1;
            switchView(viewOrder[newIndex]);
        } else if (e.button === 4 || e.which === 4) {
            e.preventDefault();
            const currentIndex = viewOrder.indexOf(state.currentView);
            let newIndex = currentIndex + 1;
            if (newIndex >= viewOrder.length) newIndex = 0;
            switchView(viewOrder[newIndex]);
        }
    });
    
    window.addEventListener('auxclick', function(e) {
        if (e.button === 3 || e.button === 4) e.preventDefault();
    });
}

document.addEventListener('DOMContentLoaded', init);
