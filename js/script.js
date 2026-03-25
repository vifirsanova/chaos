// script.js - Fixed WebSocket Implementation (No duplicates)

const API_BASE = window.location.origin;
let currentUser = null;

const state = {
    currentView: 'global',
    currentUser: {
        id: null,
        name: null,
        pubkey: null
    },
    messages: {
        global: [],
        private: [],
        feed: [],
        myvoid: []
    },
    users: [],
    chains: {
        global: null,
        feed: null,
        myvoid: null,
        private: {}
    },
    contacts: [],
    pendingMessages: new Set(),
    sentMessages: new Set(), // Track messages sent by current user to prevent duplicates
    wsConnections: {},
    wsReconnectAttempts: {},
    wsReconnectTimeouts: {}
};

const views = {
    global: document.getElementById('view-global'),
    private: document.getElementById('view-private'),
    feed: document.getElementById('view-feed'),
    myvoid: document.getElementById('view-myvoid'),
    manifest: document.getElementById('view-manifest')
};

const navItems = document.querySelectorAll('.nav-item');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
let attachedFiles = [];

// ============= API HELPER FUNCTIONS =============

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    const isPublicEndpoint = endpoint === '/users/' || 
        endpoint.startsWith('/users/by-pubkey/') ||
        endpoint === '/users/search';
    
    if (currentUser && currentUser.pubkey && !isPublicEndpoint) {
        headers['X-User-Pubkey'] = currentUser.pubkey;
    }
    
    const config = {
        ...options,
        headers
    };
    
    try {
        const response = await fetch(url, config);
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

// ============= WEB SOCKET SUPPORT =============

function getWebSocketUrl(chainId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws/${chainId}?pubkey=${encodeURIComponent(currentUser.pubkey)}`;
}

async function connectToChainWebSocket(chainId, chainType) {
    if (!currentUser || !currentUser.pubkey) {
        return;
    }

    if (state.wsConnections[chainId]) {
        try {
            if (state.wsConnections[chainId].readyState === WebSocket.OPEN ||
                state.wsConnections[chainId].readyState === WebSocket.CONNECTING) {
                state.wsConnections[chainId].close();
            }
        } catch(e) {
            // Ignore
        }
        delete state.wsConnections[chainId];
    }

    if (state.wsReconnectTimeouts[chainId]) {
        clearTimeout(state.wsReconnectTimeouts[chainId]);
        delete state.wsReconnectTimeouts[chainId];
    }

    const wsUrl = getWebSocketUrl(chainId);
    console.log(`Connecting WebSocket to chain ${chainId} (${chainType})`);
    
    const ws = new WebSocket(wsUrl);
    state.wsConnections[chainId] = ws;

    const connectionTimeout = setTimeout(() => {
        if (ws.readyState === WebSocket.CONNECTING) {
            console.warn(`WebSocket connection timeout for chain ${chainId}`);
            ws.close();
        }
    }, 10000);

    ws.onopen = () => {
        clearTimeout(connectionTimeout);
        console.log(`WebSocket connected to chain ${chainId} (${chainType})`);
        
        state.wsReconnectAttempts[chainId] = 0;
        
        if (ws.pingInterval) clearInterval(ws.pingInterval);
        ws.pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                try {
                    ws.send(JSON.stringify({ type: "ping" }));
                } catch (e) {
                    // Ignore
                }
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === "new_message") {
                handleNewMessage(data.message, chainType);
            } else if (data.type === "connected") {
                console.log(`WebSocket connected: ${data.message}`);
            }
        } catch (error) {
            console.error('Error processing WebSocket message:', error);
        }
    };

    ws.onerror = (error) => {
        console.error(`WebSocket error for chain ${chainId}:`, error);
    };

    ws.onclose = (event) => {
        clearTimeout(connectionTimeout);
        
        if (ws.pingInterval) {
            clearInterval(ws.pingInterval);
            ws.pingInterval = null;
        }
        
        if (state.wsConnections[chainId] === ws) {
            delete state.wsConnections[chainId];
        }
        
        if (!window.isUnloading && event.code !== 1000) {
            const attempts = (state.wsReconnectAttempts[chainId] || 0) + 1;
            state.wsReconnectAttempts[chainId] = attempts;
            
            const delay = Math.min(1000 * Math.pow(2, Math.min(attempts - 1, 5)), 30000);
            console.log(`Reconnecting to chain ${chainId} in ${delay}ms (attempt ${attempts})`);
            
            state.wsReconnectTimeouts[chainId] = setTimeout(() => {
                if (currentUser && currentUser.pubkey && !window.isUnloading) {
                    connectToChainWebSocket(chainId, chainType);
                }
                delete state.wsReconnectTimeouts[chainId];
            }, delay);
        }
    };
}

function handleNewMessage(message, chainType) {
    const messageId = message.id;
    
    // CRITICAL FIX: Skip if this message was sent by current user
    // This prevents showing your own message twice (optimistic + WebSocket)
    if (message.sender_id === currentUser.id) {
        console.log(`Skipping own message ${messageId} from WebSocket broadcast`);
        return;
    }
    
    // Check for duplicate message
    if (state.pendingMessages.has(messageId)) {
        console.log(`Duplicate message detected: ${messageId}, skipping`);
        return;
    }
    
    // Add to pending messages
    state.pendingMessages.add(messageId);
    
    // Remove from pending after 5 seconds
    setTimeout(() => {
        state.pendingMessages.delete(messageId);
    }, 5000);
    
    // Check if message already exists in state
    let messageArray = null;
    if (chainType === 'global') messageArray = state.messages.global;
    else if (chainType === 'feed') messageArray = state.messages.feed;
    else if (chainType === 'myvoid') messageArray = state.messages.myvoid;
    else if (chainType === 'private') messageArray = state.messages.private;
    
    if (messageArray) {
        const exists = messageArray.some(m => m.id === messageId);
        if (exists) {
            console.log(`Message ${messageId} already exists in ${chainType}, skipping`);
            return;
        }
    }
    
    // Create message object
    const newMessage = {
        id: message.id,
        user: message.sender?.username || 'Unknown',
        text: message.content,
        type: chainType === 'private' ? 'whisper' : (chainType === 'feed' ? 'feed' : 'chat'),
        time: formatTime(message.created_at),
        hash: message.hash,
        signature: message.signature
    };
    
    // Add to appropriate message array
    if (chainType === 'global') {
        state.messages.global.push(newMessage);
        if (state.currentView === 'global') {
            renderView('global');
            scrollToBottom('global');
        }
    } else if (chainType === 'feed') {
        state.messages.feed.push(newMessage);
        if (state.currentView === 'feed') {
            renderView('feed');
            scrollToBottom('feed');
        }
    } else if (chainType === 'myvoid') {
        state.messages.myvoid.push(newMessage);
        if (state.currentView === 'myvoid') {
            renderView('myvoid');
            scrollToBottom('myvoid');
        }
    } else if (chainType === 'private') {
        state.messages.private.push(newMessage);
        if (state.currentView === 'private') {
            renderView('private');
            scrollToBottom('private');
        }
    }
    
    console.log(`Message ${messageId} added to ${chainType} chat`);
}

function scrollToBottom(viewName) {
    const view = views[viewName];
    if (view) {
        const messagesDiv = view.querySelector('div:last-child');
        if (messagesDiv && messagesDiv.scrollHeight) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    }
}

function disconnectAllWebSockets() {
    console.log('Disconnecting all WebSockets...');
    Object.values(state.wsReconnectTimeouts).forEach(timeout => {
        if (timeout) clearTimeout(timeout);
    });
    state.wsReconnectTimeouts = {};
    state.wsReconnectAttempts = {};
    
    Object.entries(state.wsConnections).forEach(([chainId, ws]) => {
        if (ws) {
            if (ws.pingInterval) clearInterval(ws.pingInterval);
            try {
                ws.close(1000, "Page unloading");
            } catch(e) {
                // Ignore
            }
        }
    });
    state.wsConnections = {};
}

// ============= USER AUTHENTICATION =============

async function createOrGetUser() {
    let pubkey = localStorage.getItem('chaos_pubkey');
    let username = localStorage.getItem('chaos_username') || generateRandomUsername();
    
    if (!pubkey) {
        pubkey = generatePubkey();
        localStorage.setItem('chaos_pubkey', pubkey);
        console.log('Generated new pubkey:', pubkey.slice(0, 16) + '...');
    }
    
    console.log('Checking if user exists...');
    let userExists = false;
    
    try {
        const existingUser = await apiRequest(`/users/by-pubkey/${pubkey}`);
        currentUser = {
            id: existingUser.id,
            pubkey: existingUser.pubkey,
            name: existingUser.username || username
        };
        console.log('Found existing user:', currentUser.name, '(ID:', currentUser.id, ')');
        userExists = true;
    } catch (error) {
        if (error.message.includes('404')) {
            console.log('User not found, will create new user...');
        } else {
            console.error('Error checking user existence:', error);
        }
    }
    
    if (!userExists) {
        try {
            const newUser = await apiRequest('/users/', {
                method: 'POST',
                body: JSON.stringify({
                    pubkey: pubkey,
                    username: username
                })
            });
            
            currentUser = {
                id: newUser.id,
                pubkey: newUser.pubkey,
                name: newUser.username || username
            };
            
            console.log('Created new user:', currentUser.name, '(ID:', currentUser.id, ')');
            localStorage.setItem('chaos_username', currentUser.name);
            
        } catch (createError) {
            console.error('Failed to create user:', createError);
            
            if (createError.message.includes('409') || createError.message.includes('already exists')) {
                console.log('User was created by another request, fetching again...');
                const existingUser = await apiRequest(`/users/by-pubkey/${pubkey}`);
                currentUser = {
                    id: existingUser.id,
                    pubkey: existingUser.pubkey,
                    name: existingUser.username || username
                };
                console.log('Found existing user after conflict:', currentUser.name);
            } else {
                throw createError;
            }
        }
    }
    
    // Update last seen
    try {
        await fetch(`${API_BASE}/users/me`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Pubkey': currentUser.pubkey
            },
            body: JSON.stringify({ username: currentUser.name })
        });
    } catch (e) {
        // Non-critical
    }
    
    updateStatusBar();
}

function generatePubkey() {
    const timestamp = Date.now().toString();
    const random = Math.random().toString();
    const combined = timestamp + random + navigator.userAgent;
    
    let hash = 0;
    for (let i = 0; i < combined.length; i++) {
        const char = combined.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    
    const hexHash = Math.abs(hash).toString(16).padStart(32, '0');
    const randomBytes = new Uint8Array(16);
    crypto.getRandomValues(randomBytes);
    const randomHex = Array.from(randomBytes, b => b.toString(16).padStart(2, '0')).join('');
    
    return hexHash + randomHex.slice(0, 32);
}

function generateRandomUsername() {
    const prefixes = ['VOID', 'ECHO', 'STATIC', 'PIXEL', 'NOISE', 'WAVE', 'GHOST', 'SHADOW', 'RADIO', 'SIGNAL'];
    const suffix = Math.floor(Math.random() * 10000);
    return `${prefixes[Math.floor(Math.random() * prefixes.length)]}_${suffix}`;
}

function updateStatusBar() {
    const statusSpan = document.querySelector('.status');
    if (statusSpan && currentUser) {
        const firstPart = statusSpan.querySelector('a') || statusSpan;
        if (firstPart) {
            firstPart.innerHTML = `${currentUser.name} :: ${currentUser.pubkey.slice(0, 8)}...`;
        }
    }
}

// ============= CHAIN MANAGEMENT =============

async function initializeChains() {
    if (!currentUser) return;
    
    console.log('Initializing chains for user:', currentUser.id);
    
    // Get or create global chain
    try {
        let globalChains = await apiRequest('/chains/?chain_type=global');
        if (globalChains.length === 0) {
            console.log('Creating global chain...');
            const chain = await apiRequest('/chains/', {
                method: 'POST',
                body: JSON.stringify({
                    chain_type: 'global',
                    chain_name: 'global'
                })
            });
            state.chains.global = chain;
        } else {
            state.chains.global = globalChains[0];
        }
        console.log('Global chain ready:', state.chains.global.id);
        await connectToChainWebSocket(state.chains.global.id, 'global');
    } catch (error) {
        console.error('Failed to initialize global chain:', error);
    }
    
    // Get or create feed chain
    try {
        let feedChains = await apiRequest('/chains/?chain_type=feed');
        if (feedChains.length === 0) {
            console.log('Creating feed chain...');
            const chain = await apiRequest('/chains/', {
                method: 'POST',
                body: JSON.stringify({
                    chain_type: 'feed',
                    chain_name: 'feed'
                })
            });
            state.chains.feed = chain;
        } else {
            state.chains.feed = feedChains[0];
        }
        console.log('Feed chain ready:', state.chains.feed.id);
        await connectToChainWebSocket(state.chains.feed.id, 'feed');
    } catch (error) {
        console.error('Failed to initialize feed chain:', error);
    }
    
    // Get or create myvoid chain
    try {
        let myvoidChains = await apiRequest('/chains/?chain_type=myvoid');
        if (myvoidChains.length === 0) {
            console.log('Creating myvoid chain...');
            const chain = await apiRequest('/chains/', {
                method: 'POST',
                body: JSON.stringify({
                    chain_type: 'myvoid',
                    chain_name: `myvoid_${currentUser.id}`
                })
            });
            state.chains.myvoid = chain;
        } else {
            state.chains.myvoid = myvoidChains[0];
        }
        console.log('MyVoid chain ready:', state.chains.myvoid.id);
        await connectToChainWebSocket(state.chains.myvoid.id, 'myvoid');
    } catch (error) {
        console.error('Failed to initialize myvoid chain:', error);
    }
    
    await loadContacts();
}

// ============= MESSAGES =============

async function loadMessages(chainId, viewName) {
    if (!chainId) return;
    
    try {
        const messages = await apiRequest(`/messages/chains/${chainId}?limit=200`);
        
        // Clear existing messages
        state.messages[viewName] = [];
        
        // Add messages to state
        messages.forEach(msg => {
            const messageObj = {
                id: msg.id,
                user: msg.sender?.username || 'Unknown',
                text: msg.content,
                type: viewName === 'private' ? 'whisper' : (viewName === 'feed' ? 'feed' : 'chat'),
                time: formatTime(msg.created_at),
                hash: msg.hash,
                signature: msg.signature
            };
            state.messages[viewName].push(messageObj);
            state.pendingMessages.add(msg.id);
        });
        
        // Cleanup pending after 5 seconds
        setTimeout(() => {
            messages.forEach(msg => {
                state.pendingMessages.delete(msg.id);
            });
        }, 5000);
        
        if (state.currentView === viewName) {
            renderView(viewName);
        }
        
        console.log(`Loaded ${messages.length} messages for ${viewName}`);
    } catch (error) {
        console.error(`Failed to load ${viewName} messages:`, error);
    }
}

async function loadContacts() {
    if (!currentUser) return;
    
    try {
        const contacts = await apiRequest('/users/me/contacts');
        state.contacts = contacts;
        state.users = contacts.map(c => c.contact.username);
        console.log('Loaded contacts:', state.users.length);
        
        // Create private chains for each contact
        for (const contact of contacts) {
            const chainKey = [currentUser.id, contact.contact_id].sort().join('-');
            if (!state.chains.private[chainKey]) {
                try {
                    let chains = await apiRequest(`/chains/?chain_type=private`);
                    const existingChain = chains.find(c => 
                        (c.participant1_id === currentUser.id && c.participant2_id === contact.contact_id) ||
                        (c.participant1_id === contact.contact_id && c.participant2_id === currentUser.id)
                    );
                    
                    if (existingChain) {
                        state.chains.private[chainKey] = existingChain;
                        await connectToChainWebSocket(existingChain.id, 'private');
                    } else {
                        const chain = await apiRequest('/chains/', {
                            method: 'POST',
                            body: JSON.stringify({
                                chain_type: 'private',
                                participant1_id: currentUser.id,
                                participant2_id: contact.contact_id
                            })
                        });
                        state.chains.private[chainKey] = chain;
                        await connectToChainWebSocket(chain.id, 'private');
                    }
                } catch (error) {
                    console.error('Failed to create private chain:', error);
                }
            }
        }
    } catch (error) {
        console.error('Failed to load contacts:', error);
    }
}

async function sendMessageToAPI(text, type, chainId, prevHash = null) {
    const signature = await generateSignature(text, prevHash);
    
    const messageData = {
        content: text,
        signature: signature,
        prev_hash: prevHash
    };
    
    if (attachedFiles.length > 0) {
        const formData = new FormData();
        formData.append('content', text);
        formData.append('signature', signature);
        if (prevHash) formData.append('prev_hash', prevHash);
        
        for (const file of attachedFiles) {
            formData.append('files', file);
        }
        
        const url = `${API_BASE}/messages/chains/${chainId}/with-attachments`;
        const headers = {
            'X-User-Pubkey': currentUser.pubkey
        };
        
        const response = await fetch(url, {
            method: 'POST',
            headers: headers,
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Failed to send message');
        }
        return await response.json();
    } else {
        return await apiRequest(`/messages/chains/${chainId}`, {
            method: 'POST',
            body: JSON.stringify(messageData)
        });
    }
}

async function generateSignature(content, prevHash) {
    const data = `${content}${prevHash || ''}${currentUser.pubkey}`;
    const encoder = new TextEncoder();
    const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(data));
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

// ============= UI RENDERING =============

function createMessageElement(msg) {
    const div = document.createElement('div');
    div.className = 'message';
    div.setAttribute('data-message-id', msg.id);
    
    if (msg.type === 'whisper') div.classList.add('whisper');
    if (msg.type === 'system') div.classList.add('system');
    
    let username = msg.user;
    if (msg.type === 'feed') username = '>' + username;
    else if (msg.type === 'whisper') username = '*' + username;
    
    let contentHtml = escapeHtml(msg.text);
    
    // Handle image embeds
    contentHtml = contentHtml.replace(/\[IMG:([^\]]+)\]/g, (match, filename) => {
        const cleanFilename = filename.trim();
        return `<img src="assets/images/${cleanFilename}" 
            style="max-width: 200px; max-height: 150px; border: 1px solid #00d480; border-radius: 16px; margin: 5px 0;" 
            onerror="this.onerror=null; this.src='https://i.imgur.com/${cleanFilename}';"
            >`;
    });
    
    // Handle URLs
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    contentHtml = contentHtml.replace(urlRegex, url => {
        if (url.match(/\.(jpeg|jpg|gif|png|webp|bmp|svg)$/i)) {
            return `<img src="${url}" 
                style="max-width: 200px; max-height: 150px; border-radius: 16px; border: 1px solid #00d480; margin: 5px 0;" 
                alt="image">`;
        } else if (url.match(/\.(mp4|webm|ogg|mov)$/i)) {
            return `<video controls style="max-width: 300px; max-height: 200px; border-radius: 16px; border: 1px solid #00d480;">
                <source src="${url}" type="video/${url.split('.').pop()}">
            </video>`;
        } else {
            return `<a href="${url}" target="_blank" style="color:#8ff" rel="noopener noreferrer">[LINK]</a>`;
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderView(viewName) {
    const view = views[viewName];
    if (!view) return;
    if (viewName === 'manifest') return;
    
    view.innerHTML = '';
    
    if (viewName === 'private') {
        const usersDiv = document.createElement('div');
        usersDiv.className = 'users-list';
        if (state.users.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'message system';
            emptyMsg.innerHTML = '<div class="content">* No contacts yet. Add contacts from global chat to start private messages.</div>';
            view.appendChild(emptyMsg);
        } else {
            state.users.forEach(user => {
                const span = document.createElement('span');
                span.textContent = user;
                span.onclick = () => {
                    messageInput.value = `@${user} `;
                    messageInput.focus();
                };
                usersDiv.appendChild(span);
            });
            view.appendChild(usersDiv);
        }
    }
    
    const messagesDiv = document.createElement('div');
    messagesDiv.style.height = viewName === 'private' ? 'calc(100% - 100px)' : '100%';
    messagesDiv.style.overflowY = 'auto';
    
    const messages = state.messages[viewName] || [];
    if (messages.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'message system';
        emptyMsg.innerHTML = '<div class="content">* No messages yet. Be the first to speak.</div>';
        messagesDiv.appendChild(emptyMsg);
    } else {
        messages.forEach(msg => {
            messagesDiv.appendChild(createMessageElement(msg));
        });
    }
    
    view.appendChild(messagesDiv);
    
    setTimeout(() => {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }, 100);
}

function switchView(viewName) {
    navItems.forEach(item => item.classList.remove('active'));
    Object.values(views).forEach(v => { if(v) v.classList.remove('active'); });
    const activeNav = document.querySelector(`[data-view="${viewName}"]`);
    if (activeNav) activeNav.classList.add('active');
    if (views[viewName]) views[viewName].classList.add('active');
    state.currentView = viewName;
    
    renderView(viewName);
}

// ============= MESSAGE SENDING =============

async function sendMessage() {
    let text = messageInput.value.trim();
    if (!text && attachedFiles.length === 0) return;
    
    const now = new Date();
    const time = formatTime(now);
    let type = 'chat';
    let targetChainId = null;
    let recipient = null;
    
    // Parse message type
    if (text.startsWith('> ')) {
        type = 'feed';
        text = text.substring(2);
        targetChainId = state.chains.feed?.id;
    } else if (text.startsWith('@')) {
        const match = text.match(/^@(\w+)\s+(.+)$/);
        if (match) {
            type = 'private';
            recipient = match[1];
            text = match[2];
            
            const contact = state.contacts.find(c => c.contact.username === recipient);
            if (contact) {
                const chainKey = [currentUser.id, contact.contact_id].sort().join('-');
                targetChainId = state.chains.private[chainKey]?.id;
            } else {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'message system';
                errorMsg.innerHTML = `<div class="content" style="color: #ff4444;">* ${recipient} is not in your contacts. Add them first by messaging in global chat.</div>`;
                const container = document.getElementById(`view-${state.currentView}`);
                if (container) container.appendChild(errorMsg);
                setTimeout(() => errorMsg.remove(), 3000);
                return;
            }
        }
    }
    
    // Default to global
    if (!targetChainId) {
        targetChainId = state.chains.global?.id;
        type = 'global';
    }
    
    if (!targetChainId) {
        console.error('No chain available');
        return;
    }
    
    // Get last message hash for prev_hash
    let prevHash = null;
    const messages = state.messages[type === 'private' ? 'private' : type];
    if (messages.length > 0 && messages[messages.length - 1].hash) {
        prevHash = messages[messages.length - 1].hash;
    }
    
    // Generate temp ID for optimistic update
    const tempId = Date.now();
    
    // Show optimistic message
    const optimisticMsg = {
        id: tempId,
        user: currentUser.name,
        text: text,
        type: type === 'private' ? 'whisper' : (type === 'feed' ? 'feed' : 'chat'),
        time: time,
        sending: true
    };
    
    // Add to pending to prevent duplicates
    state.pendingMessages.add(tempId);
    
    if (type === 'feed') {
        state.messages.feed.push(optimisticMsg);
        if (state.currentView === 'feed') renderView('feed');
    } else if (type === 'private') {
        state.messages.private.push(optimisticMsg);
        if (state.currentView === 'private') renderView('private');
    } else {
        state.messages.global.push(optimisticMsg);
        if (state.currentView === 'global') renderView('global');
    }
    
    messageInput.value = '';
    
    try {
        // Send to API
        const result = await sendMessageToAPI(text, type, targetChainId, prevHash);
        
        // Remove optimistic message
        const targetArray = type === 'feed' ? state.messages.feed :
                          type === 'private' ? state.messages.private :
                          state.messages.global;
        
        const index = targetArray.findIndex(m => m.id === tempId);
        if (index !== -1) {
            targetArray.splice(index, 1);
        }
        
        // Add real message
        const realMsg = {
            id: result.id,
            user: currentUser.name,
            text: text,
            type: type === 'private' ? 'whisper' : (type === 'feed' ? 'feed' : 'chat'),
            time: time,
            hash: result.hash,
            signature: result.signature
        };
        
        targetArray.push(realMsg);
        state.pendingMessages.add(result.id);
        
        // Mark this message as sent by current user
        state.sentMessages.add(result.id);
        
        setTimeout(() => {
            state.pendingMessages.delete(result.id);
            state.sentMessages.delete(result.id);
        }, 5000);
        
        renderView(state.currentView);
        
        // Clear attachments
        attachedFiles = [];
        fileInput.value = '';
        const preview = document.querySelector('.attach-preview');
        if (preview) preview.remove();
        
    } catch (error) {
        console.error('Failed to send message:', error);
        
        // Remove optimistic message
        const targetArray = type === 'feed' ? state.messages.feed :
                          type === 'private' ? state.messages.private :
                          state.messages.global;
        
        const index = targetArray.findIndex(m => m.id === tempId);
        if (index !== -1) {
            targetArray.splice(index, 1);
        }
        
        renderView(state.currentView);
        
        // Show error
        const errorMsg = document.createElement('div');
        errorMsg.className = 'message system';
        errorMsg.innerHTML = `<div class="content" style="color: #ff4444;">* FAILED TO SEND: ${error.message}</div>`;
        const container = document.getElementById(`view-${state.currentView}`);
        if (container) container.appendChild(errorMsg);
        setTimeout(() => errorMsg.remove(), 3000);
    }
}

// ============= ATTACHMENTS =============

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

// ============= NAVIGATION =============

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

// ============= INITIALIZATION =============

async function init() {
    const chatContainer = document.getElementById('chatContainer');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message system';
    loadingDiv.innerHTML = '<div class="content">* CONNECTING TO CHAOS NETWORK...</div>';
    if (chatContainer) chatContainer.appendChild(loadingDiv);
    
    try {
        await createOrGetUser();
        await initializeChains();
        
        if (state.chains.global) await loadMessages(state.chains.global.id, 'global');
        if (state.chains.feed) await loadMessages(state.chains.feed.id, 'feed');
        if (state.chains.myvoid) await loadMessages(state.chains.myvoid.id, 'myvoid');
        
        if (loadingDiv) loadingDiv.remove();
        
        const welcomeMsg = {
            id: Date.now(),
            user: 'SYSTEM',
            text: `* CONNECTED AS ${currentUser.name} :: ${currentUser.pubkey.slice(0, 16)}...`,
            type: 'system',
            time: formatTime(new Date())
        };
        state.messages.global.unshift(welcomeMsg);
        renderView('global');
        
        console.log('Initialization complete');
        
    } catch (error) {
        console.error('Initialization failed:', error);
        if (loadingDiv) {
            loadingDiv.innerHTML = `<div class="content" style="color: #ff4444;">* CONNECTION FAILED: ${error.message}. RETRYING IN 5 SECONDS...</div>`;
        }
        
        setTimeout(() => {
            if (loadingDiv) loadingDiv.remove();
            init();
        }, 5000);
        return;
    }
    
    navItems.forEach(item => {
        item.addEventListener('click', () => switchView(item.dataset.view));
    });
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => { 
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        attachedFiles = Array.from(e.target.files);
        showAttachPreview();
    });
    
    initMouseNavigation();
    
    window.isUnloading = false;
    window.addEventListener('beforeunload', () => {
        window.isUnloading = true;
        disconnectAllWebSockets();
    });
    
    addConnectionStatusIndicator();
}

function addConnectionStatusIndicator() {
    const statusBar = document.querySelector('.status');
    if (statusBar && !document.getElementById('ws-status')) {
        const indicator = document.createElement('span');
        indicator.id = 'ws-status';
        indicator.style.marginLeft = '10px';
        indicator.style.padding = '2px 6px';
        indicator.style.borderRadius = '12px';
        indicator.style.fontSize = '10px';
        indicator.style.backgroundColor = '#00d480';
        indicator.style.color = '#000';
        indicator.textContent = '● CONNECTED';
        statusBar.appendChild(indicator);
        
        setInterval(() => {
            const hasConnections = Object.keys(state.wsConnections).length > 0;
            if (indicator) {
                if (hasConnections) {
                    indicator.style.backgroundColor = '#00d480';
                    indicator.textContent = '● CONNECTED';
                } else {
                    indicator.style.backgroundColor = '#ff4444';
                    indicator.textContent = '● DISCONNECTED';
                }
            }
        }, 5000);
    }
}

window.toggleSwitch = function(element) {
    element.classList.toggle('active');
    const label = element.closest('.toggle-label')?.querySelector('span')?.textContent;
    if (label) console.log(`[TOGGLE] ${label}: ${element.classList.contains('active') ? 'ON' : 'OFF'}`);
};

document.addEventListener('DOMContentLoaded', init);
