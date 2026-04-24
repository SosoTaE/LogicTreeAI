/**
 * Branching LLM Chat Application - Frontend JavaScript
 * Enhanced with Canvas Visualization and Multi-Model Broadcast
 */

// Application State
const state = {
    conversations: [],
    currentConversation: null,
    messageTree: null,
    activeNodeId: null, // Currently selected node in canvas
    viewMode: 'split', // 'split', 'canvas', 'text'
    currentUser: null, // { id, username, role }
};

// Tree Visualizer Instance
let treeVisualizer = null;

// API Base URL
const API_BASE = '/api';

// DOM Elements
const elements = {
    conversationsList: document.getElementById('conversations-list'),
    messagesContainer: document.getElementById('messages-container'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    newChatBtn: document.getElementById('new-chat-btn'),
    settingsBtn: document.getElementById('settings-btn'),
    settingsModal: document.getElementById('settings-modal'),
    closeSettings: document.getElementById('close-settings'),
    saveSettingsBtn: document.getElementById('save-settings-btn'),
    chatTitle: document.getElementById('chat-title'),
    inputContainer: document.getElementById('input-container'),
    loadingOverlay: document.getElementById('loading-overlay'),
    deleteChatBtn: document.getElementById('delete-chat-btn'),
    toggleViewBtn: document.getElementById('toggle-view-btn'),
    canvasPanel: document.getElementById('canvas-panel'),
    textPanel: document.getElementById('text-panel'),
    zoomInBtn: document.getElementById('zoom-in-btn'),
    zoomOutBtn: document.getElementById('zoom-out-btn'),
    resetViewBtn: document.getElementById('reset-view-btn'),
    openaiKey: document.getElementById('openai-key'),
    anthropicKey: document.getElementById('anthropic-key'),
    geminiKey: document.getElementById('gemini-key'),
    localEndpointUrl: document.getElementById('local-endpoint-url'),
    localModelName: document.getElementById('local-model-name'),
    logoutBtn: document.getElementById('logout-btn'),
    userUsername: document.getElementById('user-username'),
    userRoleBadge: document.getElementById('user-role-badge'),
    manageUsersBtn: document.getElementById('manage-users-btn'),
    usersModal: document.getElementById('users-modal'),
    closeUsers: document.getElementById('close-users'),
    createUserForm: document.getElementById('create-user-form'),
    newUsername: document.getElementById('new-username'),
    newPassword: document.getElementById('new-password'),
    newRole: document.getElementById('new-role'),
    usersError: document.getElementById('users-error'),
    usersList: document.getElementById('users-list'),
};

// Initialize Application
async function init() {
    setupEventListeners();
    initializeTreeVisualizer();

    const user = await loadCurrentUser();
    if (!user) return; // redirected to /login

    applyUserToUI(user);

    await loadConversations();
    await loadSettings();
    await loadModels();
}

async function loadCurrentUser() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'same-origin' });
        if (res.status === 401) {
            window.location.href = '/login';
            return null;
        }
        if (!res.ok) throw new Error('Failed to load user');
        const user = await res.json();
        state.currentUser = user;
        return user;
    } catch (err) {
        console.error('Failed to load current user:', err);
        return null;
    }
}

function applyUserToUI(user) {
    if (elements.userUsername) elements.userUsername.textContent = user.username;
    if (elements.userRoleBadge) elements.userRoleBadge.textContent = user.role;
    if (elements.manageUsersBtn) {
        elements.manageUsersBtn.style.display = user.role === 'admin' ? 'inline-flex' : 'none';
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            credentials: 'same-origin',
        });
    } catch (err) {
        console.error('Logout error:', err);
    } finally {
        window.location.href = '/login';
    }
}

function initializeTreeVisualizer() {
    treeVisualizer = new TreeVisualizer('tree-canvas');

    // Set up node selection callback
    window.onNodeSelected = (node) => {
        state.activeNodeId = node.id;
        renderPathToNode(node.id);
    };
}

// Event Listeners
function setupEventListeners() {
    elements.newChatBtn.addEventListener('click', createNewConversation);
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    elements.settingsBtn.addEventListener('click', openSettings);
    elements.closeSettings.addEventListener('click', closeSettings);
    elements.saveSettingsBtn.addEventListener('click', saveSettings);
    elements.deleteChatBtn.addEventListener('click', deleteCurrentConversation);

    // Canvas controls (safeguarded)
    if (elements.zoomInBtn) elements.zoomInBtn.addEventListener('click', () => treeVisualizer && treeVisualizer.zoomIn());
    if (elements.zoomOutBtn) elements.zoomOutBtn.addEventListener('click', () => treeVisualizer && treeVisualizer.zoomOut());
    if (elements.resetViewBtn) elements.resetViewBtn.addEventListener('click', () => treeVisualizer && treeVisualizer.resetView());

    // Toggle view button
    elements.toggleViewBtn.addEventListener('click', toggleView);

    // Close modal when clicking outside
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            closeSettings();
        }
    });

    if (elements.logoutBtn) elements.logoutBtn.addEventListener('click', logout);

    if (elements.manageUsersBtn) elements.manageUsersBtn.addEventListener('click', openUsersModal);
    if (elements.closeUsers) elements.closeUsers.addEventListener('click', closeUsersModal);
    if (elements.usersModal) {
        elements.usersModal.addEventListener('click', (e) => {
            if (e.target === elements.usersModal) closeUsersModal();
        });
    }
    if (elements.createUserForm) {
        elements.createUserForm.addEventListener('submit', handleCreateUser);
    }
}

// ==================== User Management (admin) ====================
async function openUsersModal() {
    if (!state.currentUser || state.currentUser.role !== 'admin') return;
    elements.usersModal.classList.add('active');
    clearUsersError();
    await loadUsers();
}

function closeUsersModal() {
    elements.usersModal.classList.remove('active');
}

function showUsersError(msg) {
    if (!elements.usersError) return;
    elements.usersError.textContent = msg;
    elements.usersError.classList.remove('hidden');
}

function clearUsersError() {
    if (!elements.usersError) return;
    elements.usersError.textContent = '';
    elements.usersError.classList.add('hidden');
}

async function loadUsers() {
    try {
        const users = await apiCall('/users');
        renderUsers(users);
    } catch (err) {
        showUsersError('Failed to load users: ' + err.message);
    }
}

function renderUsers(users) {
    elements.usersList.innerHTML = '';
    if (!users.length) {
        elements.usersList.innerHTML = '<div class="px-4 py-3 text-sm text-on-surface-variant">No users yet.</div>';
        return;
    }
    users.forEach(u => {
        const row = document.createElement('div');
        row.className = 'flex items-center justify-between px-4 py-3 bg-surface-container-low';
        const isSelf = state.currentUser && u.id === state.currentUser.id;

        const left = document.createElement('div');
        left.className = 'flex flex-col';
        const name = document.createElement('span');
        name.className = 'font-mono text-sm text-on-surface';
        name.textContent = u.username + (isSelf ? '  (you)' : '');
        const meta = document.createElement('span');
        meta.className = 'text-[10px] uppercase tracking-widest text-on-surface-variant';
        meta.textContent = `${u.role} · created ${new Date(u.created_at).toLocaleDateString()}`;
        left.appendChild(name);
        left.appendChild(meta);

        const right = document.createElement('div');
        right.className = 'flex items-center gap-2';
        if (!isSelf) {
            const delBtn = document.createElement('button');
            delBtn.className = 'text-error hover:text-error-container transition-colors';
            delBtn.title = 'Delete user';
            delBtn.innerHTML = '<span class="material-symbols-outlined text-sm">delete</span>';
            delBtn.addEventListener('click', () => deleteUser(u));
            right.appendChild(delBtn);
        }

        row.appendChild(left);
        row.appendChild(right);
        elements.usersList.appendChild(row);
    });
}

async function handleCreateUser(e) {
    e.preventDefault();
    clearUsersError();
    const username = elements.newUsername.value.trim();
    const password = elements.newPassword.value;
    const role = elements.newRole.value;

    if (!username || !password) {
        showUsersError('Username and password are required');
        return;
    }
    if (password.length < 6) {
        showUsersError('Password must be at least 6 characters');
        return;
    }

    try {
        await apiCall('/users', {
            method: 'POST',
            body: JSON.stringify({ username, password, role }),
        });
        elements.newUsername.value = '';
        elements.newPassword.value = '';
        elements.newRole.value = 'user';
        await loadUsers();
    } catch (err) {
        showUsersError(err.message);
    }
}

async function deleteUser(user) {
    if (!confirm(`Delete user "${user.username}"? This also removes their conversations and settings.`)) return;
    try {
        await apiCall(`/users/${user.id}`, { method: 'DELETE' });
        await loadUsers();
    } catch (err) {
        showUsersError(err.message);
    }
}

function toggleView() {
    const canvasPanel = document.getElementById('canvas-panel');
    const textPanel = document.getElementById('text-panel');
    const canvas = document.getElementById('tree-canvas');

    if (state.viewMode === 'split') {
        // Switch to canvas only
        textPanel.style.display = 'none';
        canvasPanel.classList.remove('w-3/5');
        canvasPanel.classList.add('w-full');
        canvas.style.pointerEvents = 'auto'; // allow interaction with canvas when full
        state.viewMode = 'canvas';
        if (elements.toggleViewBtn) elements.toggleViewBtn.textContent = 'Toggle Chat';
    } else {
        // Switch back to split
        textPanel.style.display = 'flex';
        canvasPanel.classList.remove('w-full');
        canvasPanel.classList.add('w-3/5');
        canvas.style.pointerEvents = 'auto'; // Canvas is a dedicated panel, always interactable
        state.viewMode = 'split';
        if (elements.toggleViewBtn) elements.toggleViewBtn.textContent = 'Toggle View';
    }

    // Trigger canvas resize
    if (treeVisualizer) {
        setTimeout(() => treeVisualizer.resizeCanvas(), 300); // Wait for CSS transition
    }
}

// API Functions
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        });

        if (response.status === 401) {
            window.location.href = '/login';
            throw new Error('Authentication required');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || 'API request failed');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Conversations
async function loadConversations() {
    try {
        state.conversations = await apiCall('/conversations');
        renderConversations();
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

async function createNewConversation() {
    try {
        const conversation = await apiCall('/conversations', {
            method: 'POST',
            body: JSON.stringify({ title: `New Chat ${new Date().toLocaleString()}` }),
        });

        state.conversations.unshift(conversation);
        renderConversations();
        await selectConversation(conversation.id);
    } catch (error) {
        alert('Failed to create conversation: ' + error.message);
    }
}

async function selectConversation(conversationId) {
    try {
        const data = await apiCall(`/conversations/${conversationId}/tree`);
        state.currentConversation = conversationId;
        state.messageTree = data.tree;
        state.activeNodeId = null;

        elements.chatTitle.textContent = data.title;
        elements.inputContainer.style.display = 'block';
        elements.deleteChatBtn.style.display = 'block';
        elements.toggleViewBtn.style.display = 'block';

        // Load tree into canvas
        if (treeVisualizer) {
            treeVisualizer.loadTree(state.messageTree, state.activeNodeId);
        }

        // Find and render the latest leaf node path
        const latestLeaf = findLatestLeafNode(state.messageTree);
        if (latestLeaf) {
            state.activeNodeId = latestLeaf.id;
            renderPathToNode(latestLeaf.id);
        } else {
            renderMessages([]);
        }

        renderConversations(); // Update active state
    } catch (error) {
        alert('Failed to load conversation: ' + error.message);
    }
}

async function deleteCurrentConversation() {
    if (!state.currentConversation) return;

    if (!confirm('Are you sure you want to delete this conversation?')) return;

    try {
        await apiCall(`/conversations/${state.currentConversation}`, {
            method: 'DELETE',
        });

        state.currentConversation = null;
        state.messageTree = null;
        state.activeNodeId = null;

        await loadConversations();

        elements.messagesContainer.innerHTML = '<div class="empty-state"><p>Conversation deleted. Start a new one!</p></div>';
        elements.inputContainer.style.display = 'none';
        elements.deleteChatBtn.style.display = 'none';
        elements.toggleViewBtn.style.display = 'none';
        elements.chatTitle.textContent = 'Select or create a conversation';

        if (treeVisualizer) {
            treeVisualizer.loadTree(null);
        }
    } catch (error) {
        alert('Failed to delete conversation: ' + error.message);
    }
}

function renderConversations() {
    elements.conversationsList.innerHTML = '';

    if (state.conversations.length === 0) {
        elements.conversationsList.innerHTML = '<p style="padding: 15px; color: var(--text-muted); font-size: 14px;">No conversations yet</p>';
        return;
    }

    state.conversations.forEach(conv => {
        const div = document.createElement('div');
        div.className = 'conversation-item';
        if (conv.id === state.currentConversation) {
            div.classList.add('active');
        }

        const title = document.createElement('h3');
        title.textContent = conv.title;

        const date = document.createElement('p');
        date.textContent = new Date(conv.created_at).toLocaleString();

        div.appendChild(title);
        div.appendChild(date);

        div.addEventListener('click', () => selectConversation(conv.id));

        elements.conversationsList.appendChild(div);
    });
}

// Message Tree Navigation
function findLatestLeafNode(tree) {
    if (!tree || tree.length === 0) return null;

    let latestNode = null;
    let latestTime = new Date(0);

    function traverse(nodes) {
        nodes.forEach(node => {
            const nodeTime = new Date(node.created_at);
            if (!node.children || node.children.length === 0) {
                if (nodeTime > latestTime) {
                    latestTime = nodeTime;
                    latestNode = node;
                }
            } else {
                traverse(node.children);
            }
        });
    }

    traverse(tree);
    return latestNode;
}

function findNodeById(tree, nodeId) {
    if (!tree) return null;

    for (const node of tree) {
        if (node.id === nodeId) return node;
        if (node.children && node.children.length > 0) {
            const found = findNodeById(node.children, nodeId);
            if (found) return found;
        }
    }
    return null;
}

function getPathToNode(tree, targetId) {
    const path = [];

    function traverse(nodes, currentPath) {
        for (const node of nodes) {
            const newPath = [...currentPath, node];

            if (node.id === targetId) {
                path.push(...newPath);
                return true;
            }

            if (node.children && node.children.length > 0) {
                if (traverse(node.children, newPath)) {
                    return true;
                }
            }
        }
        return false;
    }

    traverse(tree, []);
    return path;
}

function renderPathToNode(nodeId) {
    const path = getPathToNode(state.messageTree, nodeId);
    renderMessages(path);

    if (treeVisualizer) {
        treeVisualizer.selectedNodeId = nodeId;
        treeVisualizer.draw();
    }
}

// Message Rendering
function renderMessages(messagesPath) {
    elements.messagesContainer.innerHTML = '';

    if (!messagesPath || messagesPath.length === 0) {
        elements.messagesContainer.innerHTML = '<div class="empty-state"><p>No messages yet. Start the conversation!</p></div>';
        return;
    }

    messagesPath.forEach(message => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        messageDiv.dataset.messageId = message.id;

        const header = document.createElement('div');
        header.className = 'message-header';

        const role = document.createElement('div');
        role.className = 'message-role';
        role.textContent = message.role.charAt(0).toUpperCase() + message.role.slice(1);

        header.appendChild(role);

        if (message.model_used) {
            const model = document.createElement('div');
            model.className = 'message-model';
            model.textContent = message.model_used;
            header.appendChild(model);
        }

        const content = document.createElement('div');
        content.className = 'message-content prose prose-sm prose-invert max-w-none';
        // Configure marked to render newlines as breaks and sanitize HTML
        marked.setOptions({ breaks: true });
        content.innerHTML = marked.parse(message.content);

        messageDiv.appendChild(header);
        messageDiv.appendChild(content);

        // Add click handler to select this node
        messageDiv.addEventListener('click', () => {
            state.activeNodeId = message.id;
            renderPathToNode(message.id);
        });

        elements.messagesContainer.appendChild(messageDiv);
    });

    // Auto-scroll to bottom
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

// Sending Messages (Multi-Model Broadcast)
async function sendMessage() {
    const content = elements.messageInput.value.trim();
    if (!content || !state.currentConversation) return;

    // Get selected models from checkboxes and their corresponding selects
    const selectedModels = Array.from(document.querySelectorAll('.provider-checkbox:checked'))
        .map(cb => {
            const provider = cb.dataset.provider;
            const select = document.getElementById(`select-model-${provider}`);
            return select ? select.value : cb.value;
        });

    if (selectedModels.length === 0) {
        alert('Please select at least one AI model');
        return;
    }

    // Get the parent ID (current active node or null for root)
    const parentId = state.activeNodeId;

    // Clear input and show loading
    elements.messageInput.value = '';
    showLoading(true);

    try {
        const result = await apiCall('/messages', {
            method: 'POST',
            body: JSON.stringify({
                conversation_id: state.currentConversation,
                parent_id: parentId,
                content: content,
                target_models: selectedModels,
            }),
        });

        // Show errors if any models failed
        if (result.errors && result.errors.length > 0) {
            const errorMsg = result.errors.map(e => `${e.model}: ${e.error}`).join('\n');
            alert(`Some models failed:\n${errorMsg}`);
        }

        // Reload the conversation tree
        await selectConversation(state.currentConversation);

        // Select the user message as the new active node
        if (result.user_message) {
            state.activeNodeId = result.user_message.id;
            renderPathToNode(result.user_message.id);
        }

    } catch (error) {
        alert('Failed to send message: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Settings
async function loadSettings() {
    try {
        const settings = await apiCall('/settings');
        elements.openaiKey.value = settings.openai_key || '';
        elements.anthropicKey.value = settings.anthropic_key || '';
        elements.geminiKey.value = settings.gemini_key || '';
        if (elements.localEndpointUrl) elements.localEndpointUrl.value = settings.local_endpoint_url || '';
        if (elements.localModelName) elements.localModelName.value = settings.local_model_name || '';
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    try {
        const payload = {
            openai_key: elements.openaiKey.value,
            anthropic_key: elements.anthropicKey.value,
            gemini_key: elements.geminiKey.value,
        };
        if (elements.localEndpointUrl) payload.local_endpoint_url = elements.localEndpointUrl.value;
        if (elements.localModelName) payload.local_model_name = elements.localModelName.value;

        await apiCall('/settings', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        alert('Settings saved successfully!');
        closeSettings();
        await loadModels(); // Reload models in case API keys changed
    } catch (error) {
        alert('Failed to save settings: ' + error.message);
    }
}

function openSettings() {
    elements.settingsModal.classList.add('active');
}

function closeSettings() {
    elements.settingsModal.classList.remove('active');
}

async function loadModels() {
    try {
        const models = await apiCall('/models');
        renderModelSelectors(models);
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

function renderModelSelectors(models) {
    const container = document.getElementById('model-checkboxes');
    if (!container) return;
    
    // Save current selection state if any
    const currentState = {};
    document.querySelectorAll('.provider-checkbox').forEach(cb => {
        const provider = cb.dataset.provider;
        const select = document.getElementById(`select-model-${provider}`);
        currentState[provider] = {
            checked: cb.checked,
            model: select ? select.value : null
        };
    });

    container.innerHTML = '';
    
    const providers = [
        { id: 'openai', label: 'OpenAI', defaultCheck: false, defaultModel: 'gpt-4o' },
        { id: 'anthropic', label: 'Anthropic', defaultCheck: true, defaultModel: 'claude-3-5-sonnet-20241022' },
        { id: 'gemini', label: 'Google', defaultCheck: false, defaultModel: 'gemini-3.1-pro-preview' },
        { id: 'local', label: 'Local AI', defaultCheck: false, defaultModel: 'qwen2.5' }
    ];

    providers.forEach(provider => {
        const providerModels = models[provider.id] || [];
        if (providerModels.length === 0) providerModels.push(provider.defaultModel);

        const savedState = currentState[provider.id] || {};
        const isChecked = savedState.checked !== undefined ? savedState.checked : provider.defaultCheck;
        const selectedModel = savedState.model || provider.defaultModel;

        const div = document.createElement('div');
        div.className = 'flex items-center gap-1 bg-surface-container rounded-full border border-outline-variant/30 pr-2 pl-2 py-1';
        
        const label = document.createElement('label');
        label.className = 'text-[10px] flex items-center gap-1 cursor-pointer text-on-surface-variant hover:text-on-surface font-bold transition-all';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'provider-checkbox hidden';
        checkbox.dataset.provider = provider.id;
        checkbox.checked = isChecked;
        
        const indicator = document.createElement('span');
        indicator.className = `w-2 h-2 rounded-full ${isChecked ? 'bg-primary' : 'bg-outline'} transition-colors`;
        
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                indicator.classList.remove('bg-outline');
                indicator.classList.add('bg-primary');
            } else {
                indicator.classList.remove('bg-primary');
                indicator.classList.add('bg-outline');
            }
        });
        
        const spanText = document.createElement('span');
        spanText.textContent = provider.label;
        
        label.appendChild(checkbox);
        label.appendChild(indicator);
        label.appendChild(spanText);
        
        const select = document.createElement('select');
        select.className = 'bg-transparent border-none text-[10px] text-on-surface focus:ring-0 p-0 py-0 pl-1 w-24 overflow-hidden text-ellipsis whitespace-nowrap cursor-pointer hover:text-primary transition-colors';
        select.id = `select-model-${provider.id}`;
        
        providerModels.forEach(m => {
            const option = document.createElement('option');
            option.value = m;
            option.textContent = m;
            option.className = 'bg-surface text-on-surface';
            if (m === selectedModel) option.selected = true;
            select.appendChild(option);
        });
        
        div.appendChild(label);
        div.appendChild(select);
        container.appendChild(div);
    });
}

// UI Helpers
function showLoading(show) {
    elements.loadingOverlay.style.display = show ? 'flex' : 'none';
}

// ==================== Navigation Bar Selection ====================

function setActiveNavLink(linkId) {
    // Remove active state from all nav links
    const allNavLinks = document.querySelectorAll('.nav-link');
    allNavLinks.forEach(link => {
        link.classList.remove('text-[#85adff]', 'border-b-2', 'border-[#85adff]', 'pb-1', 'pt-1');
        link.classList.add('text-[#dee5ff]/60', 'px-2');
    });

    // Add active state to clicked link
    const activeLink = document.getElementById(linkId);
    if (activeLink) {
        activeLink.classList.remove('text-[#dee5ff]/60', 'px-2');
        activeLink.classList.add('text-[#85adff]', 'border-b-2', 'border-[#85adff]', 'pb-1', 'pt-1');
    }
}

// ==================== Logs Functionality ====================

async function fetchLogs() {
    try {
        const response = await fetch('/api/logs?lines=500', {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Failed to fetch logs');
        }

        const data = await response.json();

        document.getElementById('logs-content').textContent = data.logs;
        document.getElementById('logs-total').textContent = data.total_lines;
        document.getElementById('logs-displayed').textContent = data.returned_lines;
        document.getElementById('logs-count').textContent = data.returned_lines;

        // Auto-scroll to bottom
        const logsContent = document.getElementById('logs-content');
        logsContent.parentElement.scrollTop = logsContent.parentElement.scrollHeight;

    } catch (error) {
        console.error('Error fetching logs:', error);
        document.getElementById('logs-content').textContent = 'Error loading logs: ' + error.message;
    }
}

function openLogsModal() {
    const modal = document.getElementById('logs-modal');
    if (modal) {
        modal.classList.add('active');
        fetchLogs();
    }
}

function closeLogsModal() {
    const modal = document.getElementById('logs-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    // Switch back to Models nav
    setActiveNavLink('models-nav-link');
}

// Event listeners for navigation and logs
document.addEventListener('DOMContentLoaded', function() {
    // Models nav link
    const modelsNavLink = document.getElementById('models-nav-link');
    if (modelsNavLink) {
        modelsNavLink.addEventListener('click', function(e) {
            e.preventDefault();
            setActiveNavLink('models-nav-link');
            // Models view is the default, nothing else needed
        });
    }

    // Logs nav link
    const logsNavLink = document.getElementById('logs-nav-link');
    if (logsNavLink) {
        logsNavLink.addEventListener('click', function(e) {
            e.preventDefault();
            setActiveNavLink('logs-nav-link');
            openLogsModal();
        });
    }

    const closeLogsBtn = document.getElementById('close-logs');
    if (closeLogsBtn) {
        closeLogsBtn.addEventListener('click', closeLogsModal);
    }

    const closeLogsBtn2 = document.getElementById('close-logs-2');
    if (closeLogsBtn2) {
        closeLogsBtn2.addEventListener('click', closeLogsModal);
    }

    const refreshLogsBtn = document.getElementById('refresh-logs-btn');
    if (refreshLogsBtn) {
        refreshLogsBtn.addEventListener('click', fetchLogs);
    }

    // Close modal on background click
    const logsModal = document.getElementById('logs-modal');
    if (logsModal) {
        logsModal.addEventListener('click', function(e) {
            if (e.target === logsModal) {
                closeLogsModal();
            }
        });
    }
});

// Initialize the app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
