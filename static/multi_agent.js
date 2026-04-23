/**
 * Multi-Agent Discussion Frontend Logic
 */

// Multi-Agent State
const multiAgentState = {
    sessions: [],
    currentSession: null,
    availableModels: [],
};

// Load multi-agent sessions
async function loadMultiAgentSessions() {
    try {
        const response = await fetch('/api/multi-agent/sessions', {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Failed to load multi-agent sessions');
        }

        multiAgentState.sessions = await response.json();
        renderMultiAgentSessions();
    } catch (error) {
        console.error('Error loading multi-agent sessions:', error);
    }
}

// Render multi-agent sessions list
function renderMultiAgentSessions() {
    const listEl = document.getElementById('multi-agent-sessions-list');
    if (!listEl) return;

    if (multiAgentState.sessions.length === 0) {
        listEl.innerHTML = '<div class="p-4 text-sm text-on-surface-variant">No multi-agent sessions yet. Click "+ New" to start one.</div>';
        return;
    }

    listEl.innerHTML = multiAgentState.sessions.map(session => {
        const statusColor = session.status === 'active' ? 'text-secondary' :
                           session.status === 'completed' ? 'text-primary' : 'text-on-surface-variant';
        const statusIcon = session.status === 'active' ? 'sync' :
                          session.status === 'completed' ? 'check_circle' : 'cancel';

        return `
            <div class="conversation-item" onclick="viewMultiAgentSession(${session.id})">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-on-surface text-sm truncate">${escapeHtml(session.title)}</div>
                        <div class="text-xs text-on-surface-variant mt-1">
                            Round ${session.current_round}/${session.max_rounds} • ${session.participating_models.length} models
                        </div>
                    </div>
                    <span class="material-symbols-outlined text-sm ${statusColor}">${statusIcon}</span>
                </div>
            </div>
        `;
    }).join('');
}

// Open multi-agent modal
function openMultiAgentModal() {
    const modal = document.getElementById('multi-agent-modal');
    if (!modal) return;

    // Load available models
    loadModelsForMultiAgent();

    // Reset form
    document.getElementById('ma-title').value = '';
    document.getElementById('ma-problem').value = '';
    document.getElementById('ma-rounds').value = '9';
    document.getElementById('ma-mode').value = 'sequential';
    updateModeDescription();
    document.getElementById('ma-error').classList.add('hidden');

    modal.classList.add('active');
}

// Update mode description
function updateModeDescription() {
    const mode = document.getElementById('ma-mode').value;
    const description = document.getElementById('ma-mode-description');

    if (mode === 'sequential') {
        description.textContent = 'Models take turns responding to each other in sequence - like a real conversation';
    } else {
        description.textContent = 'All models answer in parallel rounds - get multiple perspectives per round';
    }
}

// Close multi-agent modal
function closeMultiAgentModal() {
    const modal = document.getElementById('multi-agent-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Load models for multi-agent selection
async function loadModelsForMultiAgent() {
    const container = document.getElementById('ma-models-container');
    if (!container) return;

    try {
        const response = await fetch('/api/models', { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to load models');

        const models = await response.json();

        // Flatten all models from all providers
        const allModels = [];
        for (const [provider, modelList] of Object.entries(models)) {
            if (Array.isArray(modelList)) {
                allModels.push(...modelList.map(m => ({ name: m, provider })));
            }
        }

        multiAgentState.availableModels = allModels;

        if (allModels.length === 0) {
            container.innerHTML = '<div class="col-span-2 text-sm text-error">No models available. Please configure API keys in settings.</div>';
            return;
        }

        container.innerHTML = allModels.map((model, idx) => `
            <label class="flex items-center gap-2 p-2 bg-surface-container rounded cursor-pointer hover:bg-surface-bright transition-colors">
                <input type="checkbox" name="ma-model" value="${escapeHtml(model.name)}"
                       class="w-4 h-4 text-tertiary bg-surface-container-low border-outline-variant rounded focus:ring-tertiary focus:ring-2">
                <span class="text-xs text-on-surface truncate" title="${escapeHtml(model.name)}">${escapeHtml(model.name)}</span>
            </label>
        `).join('');

    } catch (error) {
        console.error('Error loading models:', error);
        container.innerHTML = '<div class="col-span-2 text-sm text-error">Error loading models</div>';
    }
}

// Start multi-agent discussion
async function startMultiAgentDiscussion(event) {
    event.preventDefault();

    const title = document.getElementById('ma-title').value.trim();
    const problem = document.getElementById('ma-problem').value.trim();
    const maxRounds = parseInt(document.getElementById('ma-rounds').value);
    const conversationMode = document.getElementById('ma-mode').value;
    const errorEl = document.getElementById('ma-error');

    // Get selected models
    const selectedModels = Array.from(document.querySelectorAll('input[name="ma-model"]:checked'))
        .map(cb => cb.value);

    // Validation
    if (!problem) {
        errorEl.textContent = 'Please enter a problem or question';
        errorEl.classList.remove('hidden');
        return;
    }

    if (selectedModels.length < 2) {
        errorEl.textContent = 'Please select at least 2 models';
        errorEl.classList.remove('hidden');
        return;
    }

    if (maxRounds < 1 || maxRounds > 30) {
        errorEl.textContent = 'Max rounds must be between 1 and 30';
        errorEl.classList.remove('hidden');
        return;
    }

    errorEl.classList.add('hidden');

    try {
        const response = await fetch('/api/multi-agent/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                title: title || `Multi-Agent Discussion ${new Date().toLocaleString()}`,
                initial_problem: problem,
                participating_models: selectedModels,
                max_rounds: maxRounds,
                conversation_mode: conversationMode,
                auto_start: true
            })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to create session');
        }

        const data = await response.json();

        // Close modal and reload sessions
        closeMultiAgentModal();
        await loadMultiAgentSessions();

        // Open the session view
        viewMultiAgentSession(data.session.id);

    } catch (error) {
        console.error('Error starting multi-agent discussion:', error);
        errorEl.textContent = error.message;
        errorEl.classList.remove('hidden');
    }
}

// View multi-agent session
async function viewMultiAgentSession(sessionId) {
    try {
        const response = await fetch(`/api/multi-agent/sessions/${sessionId}`, {
            credentials: 'include'
        });

        if (!response.ok) throw new Error('Failed to load session');

        const session = await response.json();
        multiAgentState.currentSession = session;

        // Update modal
        document.getElementById('ma-view-title').textContent = session.title;
        const modeText = session.conversation_mode === 'sequential' ? 'Sequential' : 'Parallel';
        document.getElementById('ma-view-status').textContent =
            `${modeText} • ${session.status} • Turn ${session.current_round}/${session.max_rounds}`;
        document.getElementById('ma-view-problem').textContent = session.initial_problem;

        // Render discussion
        renderMultiAgentDiscussion(session);

        // Update buttons
        const continueBtn = document.getElementById('ma-continue-btn');
        const stopBtn = document.getElementById('ma-stop-btn');

        if (session.status === 'active' && session.current_round < session.max_rounds) {
            continueBtn.classList.remove('hidden');
            stopBtn.classList.remove('hidden');
        } else {
            continueBtn.classList.add('hidden');
            stopBtn.classList.add('hidden');
        }

        // Show modal
        document.getElementById('multi-agent-view-modal').classList.add('active');

    } catch (error) {
        console.error('Error viewing session:', error);
        alert('Error loading session: ' + error.message);
    }
}

// Render multi-agent discussion
function renderMultiAgentDiscussion(session) {
    const container = document.getElementById('ma-view-discussion');
    if (!container) return;

    if (!session.turns || session.turns.length === 0) {
        container.innerHTML = '<div class="text-sm text-on-surface-variant">No discussion yet. The first turn is being processed...</div>';
        return;
    }

    if (session.conversation_mode === 'sequential') {
        // Sequential mode: show turns in chronological order
        container.innerHTML = session.turns.map((turn, index) => {
            if (turn.error) {
                return `
                    <div class="border border-error/20 rounded-lg p-4">
                        <div class="text-xs font-mono text-error mb-1">Turn ${turn.turn_number}: ${escapeHtml(turn.model_name)}</div>
                        <div class="text-sm text-error opacity-80">Error: ${escapeHtml(turn.error)}</div>
                    </div>
                `;
            }

            return `
                <div class="border border-outline-variant/20 rounded-lg p-4">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-mono text-tertiary font-bold">Turn ${turn.turn_number}</span>
                            <span class="text-xs font-mono text-on-surface">${escapeHtml(turn.model_name)}</span>
                            ${turn.model_role ? `<span class="text-xs text-on-surface-variant">• ${escapeHtml(turn.model_role)}</span>` : ''}
                        </div>
                        ${turn.duration ? `<span class="text-xs text-on-surface-variant">${turn.duration.toFixed(1)}s</span>` : ''}
                    </div>
                    <div class="text-sm text-on-surface leading-relaxed prose prose-invert max-w-none border-l-2 border-tertiary pl-4">
                        ${marked.parse(turn.content)}
                    </div>
                </div>
            `;
        }).join('');
    } else {
        // Parallel mode: group by rounds
        if (!session.turns_by_round || Object.keys(session.turns_by_round).length === 0) {
            container.innerHTML = '<div class="text-sm text-on-surface-variant">No discussion yet...</div>';
            return;
        }

        const rounds = Object.entries(session.turns_by_round).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));

        container.innerHTML = rounds.map(([roundNum, turns]) => `
            <div class="border border-outline-variant/20 rounded-lg overflow-hidden">
                <div class="bg-surface-container-low px-4 py-3 border-b border-outline-variant/20">
                    <div class="font-headline font-bold text-sm text-tertiary">Round ${roundNum}</div>
                </div>
                <div class="p-4 space-y-4">
                    ${turns.map(turn => {
                        if (turn.error) {
                            return `
                                <div class="border-l-2 border-error pl-4 py-2">
                                    <div class="text-xs font-mono text-error mb-1">${escapeHtml(turn.model_name)}</div>
                                    <div class="text-sm text-error opacity-80">Error: ${escapeHtml(turn.error)}</div>
                                </div>
                            `;
                        }

                        return `
                            <div class="border-l-2 border-tertiary pl-4 py-2">
                                <div class="flex items-center gap-2 mb-2">
                                    <span class="text-xs font-mono text-tertiary font-bold">${escapeHtml(turn.model_name)}</span>
                                    ${turn.model_role ? `<span class="text-xs text-on-surface-variant">• ${escapeHtml(turn.model_role)}</span>` : ''}
                                    ${turn.duration ? `<span class="text-xs text-on-surface-variant">• ${turn.duration.toFixed(1)}s</span>` : ''}
                                </div>
                                <div class="text-sm text-on-surface leading-relaxed prose prose-invert max-w-none">${marked.parse(turn.content)}</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `).join('');
    }
}

// Continue multi-agent session
async function continueMultiAgentSession() {
    if (!multiAgentState.currentSession) return;

    const sessionId = multiAgentState.currentSession.id;
    const continueBtn = document.getElementById('ma-continue-btn');
    const originalText = continueBtn.textContent;

    continueBtn.textContent = 'Processing...';
    continueBtn.disabled = true;

    try {
        const response = await fetch(`/api/multi-agent/sessions/${sessionId}/continue`, {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to continue session');
        }

        // Reload the session view
        await viewMultiAgentSession(sessionId);
        await loadMultiAgentSessions();

    } catch (error) {
        console.error('Error continuing session:', error);
        alert('Error continuing session: ' + error.message);
    } finally {
        continueBtn.textContent = originalText;
        continueBtn.disabled = false;
    }
}

// Stop multi-agent session
async function stopMultiAgentSession() {
    if (!multiAgentState.currentSession) return;

    if (!confirm('Are you sure you want to stop this session?')) return;

    const sessionId = multiAgentState.currentSession.id;

    try {
        const response = await fetch(`/api/multi-agent/sessions/${sessionId}/stop`, {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to stop session');
        }

        // Reload the session view
        await viewMultiAgentSession(sessionId);
        await loadMultiAgentSessions();

    } catch (error) {
        console.error('Error stopping session:', error);
        alert('Error stopping session: ' + error.message);
    }
}

// Synthesize multi-agent discussion
async function synthesizeMultiAgentSession() {
    if (!multiAgentState.currentSession) return;

    const sessionId = multiAgentState.currentSession.id;
    const synthesizeBtn = document.getElementById('ma-synthesize-btn');
    const originalText = synthesizeBtn.textContent;

    // Ask for synthesis model
    const synthesisModel = prompt('Enter the model to use for synthesis (e.g., gpt-4o, claude-3-7-sonnet):', 'gpt-4o');
    if (!synthesisModel) return;

    synthesizeBtn.textContent = 'Synthesizing...';
    synthesizeBtn.disabled = true;

    try {
        const response = await fetch(`/api/multi-agent/sessions/${sessionId}/synthesize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ synthesis_model: synthesisModel })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to synthesize');
        }

        const data = await response.json();

        // Show synthesis in an alert or modal (you can improve this)
        const synthesis = data.synthesis.synthesis || data.synthesis.error;
        alert('Synthesis:\n\n' + synthesis);

    } catch (error) {
        console.error('Error synthesizing session:', error);
        alert('Error synthesizing session: ' + error.message);
    } finally {
        synthesizeBtn.textContent = originalText;
        synthesizeBtn.disabled = false;
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize multi-agent functionality when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load sessions on startup
    loadMultiAgentSessions();

    // Event listeners
    const newMultiAgentBtn = document.getElementById('new-multi-agent-btn');
    if (newMultiAgentBtn) {
        newMultiAgentBtn.addEventListener('click', openMultiAgentModal);
    }

    const modeSelect = document.getElementById('ma-mode');
    if (modeSelect) {
        modeSelect.addEventListener('change', updateModeDescription);
    }

    const closeButtons = ['close-multi-agent', 'close-multi-agent-2'];
    closeButtons.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', closeMultiAgentModal);
        }
    });

    const closeViewBtn = document.getElementById('close-multi-agent-view');
    if (closeViewBtn) {
        closeViewBtn.addEventListener('click', () => {
            document.getElementById('multi-agent-view-modal').classList.remove('active');
        });
    }

    const startBtn = document.getElementById('start-multi-agent-btn');
    if (startBtn) {
        startBtn.addEventListener('click', startMultiAgentDiscussion);
    }

    const continueBtn = document.getElementById('ma-continue-btn');
    if (continueBtn) {
        continueBtn.addEventListener('click', continueMultiAgentSession);
    }

    const stopBtn = document.getElementById('ma-stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', stopMultiAgentSession);
    }

    const synthesizeBtn = document.getElementById('ma-synthesize-btn');
    if (synthesizeBtn) {
        synthesizeBtn.addEventListener('click', synthesizeMultiAgentSession);
    }
});
