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
    const moderatorSelect = document.getElementById('ma-moderator');
    if (moderatorSelect) moderatorSelect.value = '';
    updateModeDescription();
    updateModeratorAvailability();
    document.getElementById('ma-error').classList.add('hidden');

    modal.classList.add('active');
}

// The moderator picker only makes sense in sequential mode (parallel
// runs every model each round, so there's no "next speaker" to choose).
function updateModeratorAvailability() {
    const mode = document.getElementById('ma-mode').value;
    const select = document.getElementById('ma-moderator');
    const section = document.getElementById('ma-moderator-section');
    if (!select || !section) return;
    if (mode === 'parallel') {
        select.value = '';
        select.disabled = true;
        section.classList.add('opacity-50');
    } else {
        select.disabled = false;
        section.classList.remove('opacity-50');
    }
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

// Pick one representative model per provider to pre-check in the modal so
// a new session spans multiple providers (OpenAI + Anthropic + Gemini +
// local) without the user clicking through a long list.
function _pickDefaultModel(modelList, preferenceSubstrings) {
    if (!Array.isArray(modelList) || modelList.length === 0) return null;
    const lowered = modelList.map(m => ({ name: m, lc: m.toLowerCase() }));
    for (const pref of preferenceSubstrings) {
        const hit = lowered.find(m => m.lc.includes(pref));
        if (hit) return hit.name;
    }
    return modelList[0];
}

// Load models for multi-agent selection
async function loadModelsForMultiAgent() {
    const container = document.getElementById('ma-models-container');
    if (!container) return;

    try {
        const response = await fetch('/api/models', { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to load models');

        const models = await response.json();

        // Per-provider default (pre-checked). Preferences are the
        // substrings we try in order; first match wins, else fall back to
        // the first model in the list.
        const defaultByProvider = {
            openai: _pickDefaultModel(models.openai, ['gpt-4o', 'gpt-4.1', 'gpt-4', 'gpt-3.5']),
            anthropic: _pickDefaultModel(models.anthropic, ['sonnet', 'opus', 'haiku']),
            gemini: _pickDefaultModel(models.gemini, ['gemini-3', 'gemini-2.5-pro', 'gemini-2.5', 'gemini-2.0', 'gemini-1.5-pro']),
            local: _pickDefaultModel(models.local, []),
        };
        const defaults = new Set(
            Object.values(defaultByProvider).filter(Boolean)
        );

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

        container.innerHTML = allModels.map((model) => {
            const checked = defaults.has(model.name) ? 'checked' : '';
            return `
            <label class="flex items-center gap-2 p-2 bg-surface-container rounded cursor-pointer hover:bg-surface-bright transition-colors">
                <input type="checkbox" name="ma-model" value="${escapeHtml(model.name)}" ${checked}
                       class="w-4 h-4 text-tertiary bg-surface-container-low border-outline-variant rounded focus:ring-tertiary focus:ring-2">
                <span class="text-xs text-on-surface truncate" title="${escapeHtml(model.name)}">${escapeHtml(model.name)}</span>
            </label>
        `;
        }).join('');

        // Keep the per-model role editor in sync with which checkboxes
        // are checked.
        container.querySelectorAll('input[name="ma-model"]').forEach(cb => {
            cb.addEventListener('change', renderRolesEditor);
        });
        renderRolesEditor();

        // Populate the moderator dropdown from the same flat list, plus
        // a "None" option for the default round-robin behavior.
        populateModeratorOptions(allModels);

    } catch (error) {
        console.error('Error loading models:', error);
        container.innerHTML = '<div class="col-span-2 text-sm text-error">Error loading models</div>';
    }
}

// Fill the moderator <select> with the same models the user can pick
// as participants. Preserves the current selection across reloads.
function populateModeratorOptions(allModels) {
    const select = document.getElementById('ma-moderator');
    if (!select) return;
    const previous = select.value;
    select.innerHTML = '<option value="">None — round-robin</option>';
    allModels.forEach(model => {
        const opt = document.createElement('option');
        opt.value = model.name;
        opt.textContent = model.name;
        select.appendChild(opt);
    });
    if (previous && allModels.some(m => m.name === previous)) {
        select.value = previous;
    }
}

// Render one role/system-prompt input per checked model. Preserves any
// text the user already typed across re-renders.
function renderRolesEditor() {
    const rolesContainer = document.getElementById('ma-roles-container');
    if (!rolesContainer) return;

    // Snapshot existing role inputs so toggling checkboxes doesn't wipe
    // values the user already typed.
    const existing = {};
    rolesContainer.querySelectorAll('input[data-role-for]').forEach(inp => {
        existing[inp.getAttribute('data-role-for')] = inp.value;
    });

    const checked = Array.from(document.querySelectorAll('input[name="ma-model"]:checked'))
        .map(cb => cb.value);

    if (checked.length === 0) {
        rolesContainer.innerHTML = '<div class="text-xs text-on-surface-variant">Select models above to assign roles/personas (e.g. "senior developer", "devil\'s advocate", "skeptical politician").</div>';
        return;
    }

    rolesContainer.innerHTML = checked.map(model => {
        const existingValue = escapeHtml(existing[model] || '');
        return `
            <div class="flex items-center gap-3">
                <span class="text-xs font-mono text-tertiary min-w-[160px] truncate" title="${escapeHtml(model)}">${escapeHtml(model)}</span>
                <input type="text"
                    data-role-for="${escapeHtml(model)}"
                    value="${existingValue}"
                    placeholder="e.g. senior developer, politician, sceptic — leave blank for none"
                    class="flex-1 bg-surface-container border-0 border-b-2 border-outline-variant focus:border-tertiary focus:ring-0 text-on-surface px-3 py-2 text-xs transition-all outline-none rounded-t shadow-inner"/>
            </div>
        `;
    }).join('');
}

// Read the role editor into a { modelName: roleString } map, dropping
// empty entries so the backend's optional field stays clean.
function collectModelRoles() {
    const roles = {};
    document.querySelectorAll('input[data-role-for]').forEach(inp => {
        const model = inp.getAttribute('data-role-for');
        const value = (inp.value || '').trim();
        if (model && value) roles[model] = value;
    });
    return roles;
}

// Start multi-agent discussion
async function startMultiAgentDiscussion(event) {
    event.preventDefault();

    const title = document.getElementById('ma-title').value.trim();
    const problem = document.getElementById('ma-problem').value.trim();
    const maxRounds = parseInt(document.getElementById('ma-rounds').value);
    const conversationMode = document.getElementById('ma-mode').value;
    const moderatorModel = (document.getElementById('ma-moderator')?.value || '').trim();
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
        // auto_start=false keeps session creation near-instant (no LLM
        // call blocks the response). We open the view modal right away
        // and kick off the first turn in the background below, so the
        // user sees progress instead of waiting on a frozen button.
        const response = await fetch('/api/multi-agent/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                title: title || `Multi-Agent Discussion ${new Date().toLocaleString()}`,
                initial_problem: problem,
                participating_models: selectedModels,
                model_roles: collectModelRoles(),
                max_rounds: maxRounds,
                conversation_mode: conversationMode,
                // Only send moderator if sequential — backend rejects it otherwise.
                moderator_model: conversationMode === 'sequential' ? (moderatorModel || null) : null,
                auto_start: false
            })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to create session');
        }

        const data = await response.json();

        // Close the creation modal and open the discussion view
        // immediately — the session exists, the first turn is running in
        // the background.
        closeMultiAgentModal();
        loadMultiAgentSessions();  // non-blocking sidebar refresh
        await viewMultiAgentSession(data.session.id);

        // Kick off turn 1 now that the view is on-screen. The discussion
        // container already shows "The first turn is being processed..."
        // while this runs, and viewMultiAgentSession re-renders on return.
        continueMultiAgentSession();

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
        const moderatorText = session.moderator_model
            ? ` • Moderator: ${session.moderator_model}`
            : '';
        document.getElementById('ma-view-status').textContent =
            `${modeText} • ${session.status} • Turn ${session.current_round}/${session.max_rounds}${moderatorText}`;
        document.getElementById('ma-view-problem').textContent = session.initial_problem;

        // Render discussion
        renderMultiAgentDiscussion(session);

        // Update buttons
        const continueBtn = document.getElementById('ma-continue-btn');
        const stopBtn = document.getElementById('ma-stop-btn');

        // "Rounds used" on the backend tracks AI turns only (human turns
        // and moderator decisions don't burn the budget), but the
        // session object exposes current_round as a total turn counter.
        // Compute AI-turn count here so the UI matches backend
        // completion semantics.
        const aiTurnCount = (session.turns || []).filter(t => {
            const name = (t.model_name || '').toLowerCase();
            return name !== 'user' && name !== 'moderator' && !t.error;
        }).length;
        const canContinue = session.status === 'active' && aiTurnCount < session.max_rounds;

        if (canContinue) {
            continueBtn.classList.remove('hidden');
            stopBtn.classList.remove('hidden');
        } else {
            continueBtn.classList.add('hidden');
            stopBtn.classList.add('hidden');
        }

        // Composer is only useful while the session is active; lock it
        // when stopped/completed.
        const composer = document.getElementById('ma-user-composer');
        if (composer) {
            if (session.status === 'active') {
                composer.classList.remove('hidden');
            } else {
                composer.classList.add('hidden');
            }
        }

        // Populate synthesis model dropdown
        populateSynthesisModelSelector();

        // Reset Problem Statement to expanded for each session view so
        // a previously collapsed state from another session doesn't
        // hide the new problem.
        const problemBtn = document.getElementById('ma-problem-toggle');
        const problemBody = document.getElementById('ma-view-problem');
        const problemIcon = document.getElementById('ma-problem-toggle-icon');
        if (problemBtn && problemBody && problemIcon) {
            problemBtn.setAttribute('aria-expanded', 'true');
            problemBody.classList.remove('hidden');
            problemIcon.textContent = 'expand_less';
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
        container.innerHTML = `
            <div class="flex items-center gap-3 text-sm text-on-surface-variant">
                <span class="inline-block w-4 h-4 border-2 border-tertiary/40 border-t-tertiary rounded-full animate-spin"></span>
                <span>The first turn is being generated — this usually takes a few seconds per model.</span>
            </div>`;
        return;
    }

    if (session.conversation_mode === 'sequential') {
        // Sequential mode: show turns in chronological order
        let turnsHtml = session.turns.map((turn) => {
            const nameLower = (turn.model_name || '').toLowerCase();
            const isUser = nameLower === 'user';
            const isModerator = nameLower === 'moderator';

            if (turn.error) {
                return `
                    <div class="border border-error/20 rounded-lg p-4">
                        <div class="text-xs font-mono text-error mb-1">Turn ${turn.turn_number}: ${escapeHtml(turn.model_name)}</div>
                        <div class="text-sm text-error opacity-80">Error: ${escapeHtml(turn.error)}</div>
                    </div>
                `;
            }

            if (isModerator) {
                // Slim banner showing who the moderator picked. The
                // model_role field carries "-> <chosen_model>" so the
                // user can see the decision at a glance; reasoning is
                // tucked inside <details> to avoid cluttering the
                // discussion view.
                const chosen = (turn.model_role || '').replace(/^->\s*/, '');
                const moderatorBy = session.moderator_model
                    ? ` (${escapeHtml(session.moderator_model)})`
                    : '';
                const reasoning = (turn.content || '').trim();
                return `
                    <div class="border border-secondary/30 bg-secondary/5 rounded-lg px-4 py-2">
                        <details ${reasoning ? '' : 'open'} class="group">
                            <summary class="flex items-center gap-2 cursor-pointer list-none select-none">
                                <span class="material-symbols-outlined text-[14px] text-secondary">gavel</span>
                                <span class="text-xs font-mono text-secondary font-bold">Moderator${moderatorBy}</span>
                                <span class="text-xs text-on-surface-variant">picked</span>
                                <span class="text-xs font-mono text-tertiary">${escapeHtml(chosen) || '—'}</span>
                                ${reasoning ? `<span class="ml-auto text-[10px] text-on-surface-variant group-open:hidden">show reasoning ▾</span><span class="ml-auto text-[10px] text-on-surface-variant hidden group-open:inline">hide reasoning ▴</span>` : ''}
                            </summary>
                            ${reasoning ? `<div class="mt-2 pl-6 text-xs text-on-surface-variant leading-relaxed prose prose-invert max-w-none">${marked.parse(reasoning)}</div>` : ''}
                        </details>
                    </div>
                `;
            }

            if (isUser) {
                // Human interjection — styled to feel like "you said this"
                // so it stands out from AI turns.
                return `
                    <div class="border border-primary/30 rounded-lg p-4 bg-primary/5">
                        <div class="flex items-center gap-2 mb-3">
                            <span class="material-symbols-outlined text-[16px] text-primary">person</span>
                            <span class="text-xs font-mono text-primary font-bold">Turn ${turn.turn_number}</span>
                            <span class="text-xs font-mono text-primary">You</span>
                        </div>
                        <div class="text-sm text-on-surface leading-relaxed prose prose-invert max-w-none border-l-2 border-primary pl-4">
                            ${marked.parse(turn.content)}
                        </div>
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

        // Add synthesis section if available
        if (session.synthesis) {
            turnsHtml += `
                <div class="border-2 border-tertiary/40 rounded-lg overflow-hidden bg-tertiary/5 mt-6">
                    <div class="bg-gradient-to-r from-tertiary/20 to-tertiary/10 px-4 py-3 border-b border-tertiary/30">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-[16px] text-tertiary">auto_awesome</span>
                            <div class="font-headline font-bold text-sm text-tertiary">Synthesis</div>
                            ${session.synthesis_model ? `<span class="text-xs text-on-surface-variant">by ${escapeHtml(session.synthesis_model)}</span>` : ''}
                        </div>
                    </div>
                    <div class="p-4">
                        <div class="text-sm text-on-surface leading-relaxed prose prose-invert max-w-none">
                            ${marked.parse(session.synthesis)}
                        </div>
                    </div>
                </div>
            `;
        }

        container.innerHTML = turnsHtml;
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

    // Add synthesis section if available
    if (session.synthesis) {
        container.innerHTML += `
            <div class="border-2 border-tertiary/40 rounded-lg overflow-hidden bg-tertiary/5 mt-6">
                <div class="bg-gradient-to-r from-tertiary/20 to-tertiary/10 px-4 py-3 border-b border-tertiary/30">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-[16px] text-tertiary">auto_awesome</span>
                        <div class="font-headline font-bold text-sm text-tertiary">Synthesis</div>
                        ${session.synthesis_model ? `<span class="text-xs text-on-surface-variant">by ${escapeHtml(session.synthesis_model)}</span>` : ''}
                    </div>
                </div>
                <div class="p-4">
                    <div class="text-sm text-on-surface leading-relaxed prose prose-invert max-w-none">
                        ${marked.parse(session.synthesis)}
                    </div>
                </div>
            </div>
        `;
    }
}

// Post a human message into the running session and immediately trigger
// the next AI turn so the rotation picks up where the user left off.
async function sendUserMessageToMultiAgent() {
    if (!multiAgentState.currentSession) return;
    const sessionId = multiAgentState.currentSession.id;
    const input = document.getElementById('ma-user-input');
    const sendBtn = document.getElementById('ma-user-send-btn');
    if (!input || !sendBtn) return;

    const content = (input.value || '').trim();
    if (!content) return;

    const originalLabel = sendBtn.textContent;
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';
    input.disabled = true;

    try {
        const response = await fetch(
            `/api/multi-agent/sessions/${sessionId}/user-message`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ content }),
            },
        );
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.message || `Failed to send (HTTP ${response.status})`);
        }

        input.value = '';
        // Re-render the view with the newly-inserted user turn…
        await viewMultiAgentSession(sessionId);
        // …then kick the rotation so an AI replies to what we said.
        continueMultiAgentSession();
    } catch (error) {
        console.error('Send failed:', error);
        alert(`Could not send: ${error.message}`);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = originalLabel;
        input.disabled = false;
        input.focus();
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

// Populate synthesis model selector
function populateSynthesisModelSelector() {
    const selector = document.getElementById('ma-synthesis-model');
    if (!selector || !multiAgentState.availableModels) return;

    // Clear existing options except the placeholder
    selector.innerHTML = '<option value="">Select synthesis model...</option>';

    // Add all available models
    multiAgentState.availableModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model.name;
        option.textContent = model.name;

        // Pre-select a good default model for synthesis
        if (model.name.includes('gpt-4o') || model.name.includes('claude-3-7-sonnet') || model.name.includes('claude-sonnet-4')) {
            option.selected = true;
        }

        selector.appendChild(option);
    });

    // If no default was selected, select the first available model
    if (selector.selectedIndex === 0 && multiAgentState.availableModels.length > 0) {
        selector.selectedIndex = 1;
    }
}

// Synthesize multi-agent discussion
async function synthesizeMultiAgentSession() {
    if (!multiAgentState.currentSession) return;

    const sessionId = multiAgentState.currentSession.id;
    const synthesizeBtn = document.getElementById('ma-synthesize-btn');
    const modelSelector = document.getElementById('ma-synthesis-model');
    const originalText = synthesizeBtn.textContent;

    // Get selected model from dropdown
    const synthesisModel = modelSelector.value;
    if (!synthesisModel) {
        alert('Please select a model for synthesis');
        return;
    }

    synthesizeBtn.textContent = 'Synthesizing...';
    synthesizeBtn.disabled = true;
    modelSelector.disabled = true;

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

        // Refresh the session to show updated synthesis
        await viewMultiAgentSession(sessionId);

    } catch (error) {
        console.error('Error synthesizing session:', error);
        alert('Error synthesizing session: ' + error.message);
    } finally {
        synthesizeBtn.textContent = originalText;
        synthesizeBtn.disabled = false;
        modelSelector.disabled = false;
    }
}

// Delete multi-agent session
async function deleteMultiAgentSession() {
    if (!multiAgentState.currentSession) return;

    const sessionId = multiAgentState.currentSession.id;
    const sessionTitle = multiAgentState.currentSession.title;

    // Confirm deletion
    if (!confirm(`Are you sure you want to delete the session "${sessionTitle}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/multi-agent/sessions/${sessionId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to delete session');
        }

        // Close the view modal
        document.getElementById('multi-agent-view-modal').classList.remove('active');

        // Reload sessions list
        await loadMultiAgentSessions();

        // Clear current session
        multiAgentState.currentSession = null;

    } catch (error) {
        console.error('Error deleting session:', error);
        alert('Error deleting session: ' + error.message);
    }
}

// Toggle the Problem Statement section so the user can free up
// vertical space for the discussion. Stores nothing — defaults to
// expanded each time the modal opens.
function toggleProblemStatement() {
    const btn = document.getElementById('ma-problem-toggle');
    const body = document.getElementById('ma-view-problem');
    const icon = document.getElementById('ma-problem-toggle-icon');
    if (!btn || !body || !icon) return;
    const isExpanded = btn.getAttribute('aria-expanded') !== 'false';
    const next = !isExpanded;
    btn.setAttribute('aria-expanded', String(next));
    if (next) {
        body.classList.remove('hidden');
        icon.textContent = 'expand_less';
    } else {
        body.classList.add('hidden');
        icon.textContent = 'expand_more';
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
        modeSelect.addEventListener('change', () => {
            updateModeDescription();
            updateModeratorAvailability();
        });
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

    const problemToggleBtn = document.getElementById('ma-problem-toggle');
    if (problemToggleBtn) {
        problemToggleBtn.addEventListener('click', toggleProblemStatement);
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

    const deleteBtn = document.getElementById('ma-delete-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', deleteMultiAgentSession);
    }

    const exportDocxBtn = document.getElementById('ma-export-docx-btn');
    if (exportDocxBtn) {
        exportDocxBtn.addEventListener('click', () => exportMultiAgentSession('docx'));
    }

    const exportPdfBtn = document.getElementById('ma-export-pdf-btn');
    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', () => exportMultiAgentSession('pdf'));
    }

    const userSendBtn = document.getElementById('ma-user-send-btn');
    if (userSendBtn) {
        userSendBtn.addEventListener('click', sendUserMessageToMultiAgent);
    }

    const userInput = document.getElementById('ma-user-input');
    if (userInput) {
        // Ctrl/Cmd+Enter submits — gives multi-line freedom plus a fast path.
        userInput.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                sendUserMessageToMultiAgent();
            }
        });
    }
});

// Trigger a download of the current multi-agent session as docx or pdf.
// Uses fetch + Blob so the session cookie goes along and the browser save
// dialog honors the Content-Disposition filename from the server.
async function exportMultiAgentSession(format) {
    if (!multiAgentState.currentSession) return;
    const sessionId = multiAgentState.currentSession.id;
    const url = `/api/multi-agent/sessions/${sessionId}/export?format=${encodeURIComponent(format)}`;
    try {
        const response = await fetch(url, { credentials: 'include' });
        if (!response.ok) {
            let msg = `Export failed (HTTP ${response.status})`;
            try {
                const data = await response.json();
                if (data && data.message) msg = data.message;
            } catch (_) { /* non-JSON body */ }
            throw new Error(msg);
        }
        const blob = await response.blob();

        // Pull filename out of Content-Disposition if present, else synthesize.
        let filename = `discussion_${sessionId}.${format}`;
        const disp = response.headers.get('Content-Disposition') || '';
        const starMatch = disp.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
        const plainMatch = disp.match(/filename\s*=\s*"([^"]+)"/i);
        if (starMatch) {
            try { filename = decodeURIComponent(starMatch[1]); } catch (_) {}
        } else if (plainMatch) {
            filename = plainMatch[1];
        }

        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objectUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(objectUrl);
    } catch (error) {
        console.error('Export failed:', error);
        alert(`Could not export discussion: ${error.message}`);
    }
}
