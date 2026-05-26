document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    const welcomeScreen = document.getElementById('welcome-screen');
    const messagesContainer = document.getElementById('messages-container');
    const statusIndicator = document.getElementById('status-indicator');
    const resetBtn = document.getElementById('reset-btn');
    const loader = submitBtn.querySelector('.loader');
    const btnText = submitBtn.querySelector('.btn-text');

    // Dashboard Elements
    const systemName = document.getElementById('system-name');
    const metaBoard = document.getElementById('meta-board');
    const metaOs = document.getElementById('meta-os');
    const tasksTableBody = document.getElementById('tasks-table-body');
    const queuesTableBody = document.getElementById('queues-table-body');
    
    // New granular elements
    const mutexesTableBody = document.getElementById('mutexes-table-body');
    const binarySemsTableBody = document.getElementById('binary-sems-table-body');
    const countingSemsTableBody = document.getElementById('counting-sems-table-body');
    const peripheralsTableBody = document.getElementById('peripherals-table-body');
    const interruptsTableBody = document.getElementById('interrupts-table-body');
    
    const statusValidation = document.getElementById('status-validation');
    const statusCompile = document.getElementById('status-compile');
    const statusSummary = document.getElementById('status-summary');
    
    const modificationChipsRow = document.getElementById('modification-chips-row');

    // State Variables
    let sessionId = '';
    let conversationHistory = [];
    let activeSnapshot = null;

    // Initialize State
    initSession();

    // ─────────────────────────────────────────────────────────────────────────
    // SESSION & INITIALIZATION LOGIC
    // ─────────────────────────────────────────────────────────────────────────

    function initSession() {
        // Load or generate Session ID
        let storedSessionId = localStorage.getItem('copilot_session_id');
        if (!storedSessionId) {
            storedSessionId = generateUUID();
            localStorage.setItem('copilot_session_id', storedSessionId);
        }
        sessionId = storedSessionId;

        // Restore messages history
        const storedHistory = localStorage.getItem('copilot_messages');
        if (storedHistory) {
            try {
                conversationHistory = JSON.parse(storedHistory);
            } catch (e) {
                conversationHistory = [];
            }
        }

        // Restore snapshot
        const storedSnapshot = localStorage.getItem('copilot_snapshot');
        if (storedSnapshot) {
            try {
                activeSnapshot = JSON.parse(storedSnapshot);
            } catch (e) {
                activeSnapshot = null;
            }
        }

        // Render UI based on restored state
        if (conversationHistory.length > 0) {
            welcomeScreen.classList.add('hidden');
            messagesContainer.classList.remove('hidden');
            renderAllMessages();
            if (activeSnapshot) {
                updateDashboard(activeSnapshot);
                renderModificationChips(activeSnapshot);
            }
        } else {
            showWelcome();
        }
    }

    function generateUUID() {
        if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
            return crypto.randomUUID();
        }
        // Fallback generator
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    function showWelcome() {
        welcomeScreen.classList.remove('hidden');
        messagesContainer.classList.add('hidden');
        resetDashboard();
    }

    function resetSession() {
        localStorage.removeItem('copilot_session_id');
        localStorage.removeItem('copilot_messages');
        localStorage.removeItem('copilot_snapshot');
        conversationHistory = [];
        activeSnapshot = null;
        queryInput.value = '';
        initSession();
    }

    // ─────────────────────────────────────────────────────────────────────────
    // SUBMIT & API FLOW
    // ─────────────────────────────────────────────────────────────────────────

    async function handleSubmit() {
        const query = queryInput.value.trim();
        if (!query) return;

        // Hide modification chips during query processing
        modificationChipsRow.classList.add('hidden');

        // Clear input box
        queryInput.value = '';

        // Add user message to UI state
        const userMsg = {
            sender: 'user',
            text: query,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        conversationHistory.push(userMsg);
        persistState();

        // Render user message bubble immediately
        welcomeScreen.classList.add('hidden');
        messagesContainer.classList.remove('hidden');
        appendMessageBubble(userMsg);
        scrollToBottom();

        // Start step-by-step indicator flow
        submitBtn.disabled = true;
        loader.classList.remove('hidden');
        btnText.innerText = 'Sending...';

        const stages = [
            'Analyzing query constraints...',
            'Validating FreeRTOS scheduling rules...',
            'Verifying LPC2148 peripheral maps...',
            'Compiling firmware skeleton (arm-gcc)...'
        ];
        
        let currentStage = 0;
        statusIndicator.classList.remove('hidden');
        statusIndicator.innerText = stages[currentStage];
        
        const stageInterval = setInterval(() => {
            currentStage = (currentStage + 1) % stages.length;
            statusIndicator.innerText = stages[currentStage];
        }, 1500);

        try {
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, text: query })
            });

            clearInterval(stageInterval);

            if (response.status === 200) {
                const data = await response.json();
                
                statusIndicator.innerText = 'Validating compilation payload...';
                
                setTimeout(() => {
                    statusIndicator.classList.add('hidden');
                    const assistantMsg = {
                        sender: 'assistant',
                        text: data.response,
                        diff: data.diff || null,
                        snapshot: data.architecture_snapshot || null,
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    };
                    conversationHistory.push(assistantMsg);
                    
                    if (data.architecture_snapshot) {
                        activeSnapshot = data.architecture_snapshot;
                    }
                    
                    persistState();
                    appendMessageBubble(assistantMsg);
                    
                    if (data.architecture_snapshot) {
                        updateDashboard(data.architecture_snapshot);
                        renderModificationChips(data.architecture_snapshot);
                    }
                    
                    scrollToBottom();
                }, 400);

            } else {
                clearInterval(stageInterval);
                statusIndicator.classList.add('hidden');
                const errText = await response.text();
                const errJson = safeParseJson(errText);
                const errMsg = errJson ? errJson.response : 'Server processing failed.';
                
                addErrorMessage(errMsg);
            }

        } catch (error) {
            clearInterval(stageInterval);
            statusIndicator.classList.add('hidden');
            addErrorMessage('Failed to connect to backend server. Make sure FastAPI app is running on port 8000.');
        } finally {
            loader.classList.add('hidden');
            btnText.innerText = 'Send';
            submitBtn.disabled = false;
        }
    }

    function addErrorMessage(msg) {
        const errorMsg = {
            sender: 'assistant',
            text: `⚠️ **System Verification Failure**\n\n${msg}`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isError: true
        };
        conversationHistory.push(errorMsg);
        persistState();
        appendMessageBubble(errorMsg);
        scrollToBottom();
    }

    function safeParseJson(str) {
        try {
            return JSON.parse(str);
        } catch (e) {
            return null;
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // STATE PERSISTENCE
    // ─────────────────────────────────────────────────────────────────────────

    function persistState() {
        localStorage.setItem('copilot_messages', JSON.stringify(conversationHistory));
        if (activeSnapshot) {
            localStorage.setItem('copilot_snapshot', JSON.stringify(activeSnapshot));
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // UI RENDERING LOGIC
    // ─────────────────────────────────────────────────────────────────────────

    function renderAllMessages() {
        messagesContainer.innerHTML = '';
        conversationHistory.forEach(msg => {
            appendMessageBubble(msg);
        });
        scrollToBottom();
    }

    function appendMessageBubble(msg) {
        const bubble = document.createElement('div');
        bubble.classList.add('message-bubble', msg.sender);
        if (msg.isError) {
            bubble.style.borderLeft = '3px solid var(--error)';
        }

        // Header meta
        const meta = document.createElement('div');
        meta.classList.add('bubble-meta');
        meta.innerHTML = `<span>${msg.sender === 'user' ? 'Engineering Input' : 'Firmware Copilot'}</span><span>${msg.timestamp}</span>`;
        bubble.appendChild(meta);

        // Body content
        const body = document.createElement('div');
        body.classList.add('bubble-body');
        if (msg.sender === 'user') {
            body.innerText = msg.text;
        } else {
            body.innerHTML = marked.parse(msg.text);
        }
        bubble.appendChild(body);

        // Diff patch block rendering
        if (msg.sender === 'assistant' && msg.diff && msg.diff.length > 0) {
            const diffHtml = renderDiffBlock(msg.diff);
            const diffDiv = document.createElement('div');
            diffDiv.innerHTML = diffHtml;
            bubble.appendChild(diffDiv);
        }

        messagesContainer.appendChild(bubble);

        // Highlight syntax
        bubble.querySelectorAll('pre code').forEach((el) => {
            hljs.highlightElement(el);
        });
    }

    function renderDiffBlock(diffList) {
        let html = '<div class="diff-container">';
        html += `
        <div class="diff-card">
            <div class="diff-card-header">
                <span class="diff-section">Code Change Patch</span>
            </div>
            <div class="diff-body">
        `;
        
        diffList.forEach(entry => {
            let className = 'context';
            let marker = ' ';
            if (entry.type === 'add') {
                className = 'added';
                marker = '+';
            } else if (entry.type === 'remove') {
                className = 'removed';
                marker = '-';
            }
            html += `<div class="diff-line ${className}"><span class="diff-marker">${marker}</span><span class="diff-code-text">${escapeHtml(entry.line)}</span></div>`;
        });
        
        html += `
            </div>
        </div>
        `;
        html += '</div>';
        return html;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // DASHBOARD RENDERING LOGIC
    // ─────────────────────────────────────────────────────────────────────────

    function renderModificationChips(snapshot) {
        if (!snapshot) {
            modificationChipsRow.classList.add('hidden');
            return;
        }
        
        modificationChipsRow.innerHTML = '';
        
        const suggestions = [
            { label: 'Add Watchdog', query: 'Add watchdog timer to keep task execution healthy' },
            { label: 'Reduce Stack', query: 'Reduce task stack usage to reclaim RAM' },
            { label: 'RMS Priorities', query: 'Optimize task priorities for Rate Monotonic Scheduling (RMS)' },
            { label: 'Retry Logic', query: 'Add retry logic to communication queue writes' }
        ];
        
        const hasWatchdog = snapshot.tasks && snapshot.tasks.some(t => t.name === 'Watchdog' || t.function === 'vWatchdogTask');
        if (hasWatchdog) {
            suggestions[0] = { label: 'Remove Watchdog', query: 'Remove watchdog timer and its task' };
        }
        
        if (snapshot.queues && snapshot.queues.length > 0) {
            suggestions.push({ label: 'Increase Queue Depth', query: `Increase queue depth of ${snapshot.queues[0].name} to 32` });
            suggestions.push({ label: 'Overflow Protection', query: `Add queue overflow protection to ${snapshot.queues[0].name}` });
        }
        
        suggestions.forEach(s => {
            const chip = document.createElement('span');
            chip.classList.add('tag', 'chip');
            chip.innerText = s.label;
            chip.addEventListener('click', () => {
                queryInput.value = s.query;
                handleSubmit();
            });
            modificationChipsRow.appendChild(chip);
        });
        
        modificationChipsRow.classList.remove('hidden');
    }

    function updateDashboard(snapshot) {
        if (!snapshot) return;

        // System information
        systemName.innerText = snapshot.system_name || 'Embedded System';
        
        // Populate Tasks Table
        if (snapshot.tasks && snapshot.tasks.length > 0) {
            tasksTableBody.innerHTML = '';
            snapshot.tasks.forEach(t => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(t.name)}</strong></td>
                    <td><code>${escapeHtml(t.function)}</code></td>
                    <td>${t.priority}</td>
                    <td>${t.period_ms ? t.period_ms + ' ms' : 'event-driven'}</td>
                    <td>${t.stack_words} w</td>
                `;
                tasksTableBody.appendChild(tr);
            });
        } else {
            tasksTableBody.innerHTML = `<tr><td colspan="5" class="empty-row">No active tasks</td></tr>`;
        }

        // Populate Queues Table
        if (snapshot.queues && snapshot.queues.length > 0) {
            queuesTableBody.innerHTML = '';
            snapshot.queues.forEach(q => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(q.name)}</strong></td>
                    <td>${q.depth}</td>
                    <td><code>${escapeHtml(q.item_type)}</code></td>
                `;
                queuesTableBody.appendChild(tr);
            });
        } else {
            queuesTableBody.innerHTML = `<tr><td colspan="3" class="empty-row">No active queues</td></tr>`;
        }

        // Populate Mutexes
        if (snapshot.mutexes && snapshot.mutexes.length > 0) {
            mutexesTableBody.innerHTML = '';
            snapshot.mutexes.forEach(m => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(m.name)}</strong></td>
                    <td><code>${escapeHtml(m.resource)}</code></td>
                `;
                mutexesTableBody.appendChild(tr);
            });
        } else {
            mutexesTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active mutexes</td></tr>`;
        }

        // Populate Binary Semaphores
        if (snapshot.binary_semaphores && snapshot.binary_semaphores.length > 0) {
            binarySemsTableBody.innerHTML = '';
            snapshot.binary_semaphores.forEach(b => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(b.name)}</strong></td>
                    <td>${escapeHtml(b.owner)}</td>
                `;
                binarySemsTableBody.appendChild(tr);
            });
        } else {
            binarySemsTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active binary semaphores</td></tr>`;
        }

        // Populate Counting Semaphores
        if (snapshot.counting_semaphores && snapshot.counting_semaphores.length > 0) {
            countingSemsTableBody.innerHTML = '';
            snapshot.counting_semaphores.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(c.name)}</strong></td>
                    <td>${escapeHtml(c.owner)}</td>
                `;
                countingSemsTableBody.appendChild(tr);
            });
        } else {
            countingSemsTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active counting semaphores</td></tr>`;
        }

        // Populate Peripherals
        if (snapshot.peripherals && snapshot.peripherals.length > 0) {
            peripheralsTableBody.innerHTML = '';
            snapshot.peripherals.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(p.peripheral)}</strong></td>
                    <td>${escapeHtml(p.owner_task)}</td>
                    <td><code>${escapeHtml(p.pinsel_reg)}</code></td>
                    <td>${escapeHtml(p.pinsel_bits)} (value: ${p.pinsel_val})</td>
                `;
                peripheralsTableBody.appendChild(tr);
            });
        } else {
            peripheralsTableBody.innerHTML = `<tr><td colspan="4" class="empty-row">No active peripherals</td></tr>`;
        }

        // Populate Interrupts
        if (snapshot.isr_topology && snapshot.isr_topology.length > 0) {
            interruptsTableBody.innerHTML = '';
            snapshot.isr_topology.forEach(i => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(i.handler_fn || i.isr_name)}</strong></td>
                    <td>Channel ${i.vic_channel}</td>
                    <td>Slot ${i.vic_channel} (IRQ)</td>
                `;
                interruptsTableBody.appendChild(tr);
            });
        } else {
            interruptsTableBody.innerHTML = `<tr><td colspan="3" class="empty-row">No active interrupts</td></tr>`;
        }

        // Populate Diagnostics Status & Metrics
        statusValidation.innerText = snapshot.validation_status || 'Valid';
        statusCompile.innerText = snapshot.compile_status || 'Valid';
        statusSummary.innerText = snapshot.summary || 'Architecture active.';
    }

    function extractCCode(markdown) {
        if (!markdown) return '';
        const pattern = /```c\s*([\s\S]*?)\s*```/gi;
        let match;
        let lastCodeBlock = '';
        while ((match = pattern.exec(markdown)) !== null) {
            const block = match[1];
            if (block.includes('#include') && (block.includes('xTaskCreate') || block.includes('main'))) {
                return block;
            }
            lastCodeBlock = block;
        }
        return lastCodeBlock || '';
    }

    function resetDashboard() {
        systemName.innerText = 'No active system';
        metaBoard.innerText = 'LPC2148';
        metaOs.innerText = 'FreeRTOS 8.x';
        tasksTableBody.innerHTML = `<tr><td colspan="5" class="empty-row">No active tasks</td></tr>`;
        queuesTableBody.innerHTML = `<tr><td colspan="3" class="empty-row">No active queues</td></tr>`;
        mutexesTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active mutexes</td></tr>`;
        binarySemsTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active binary semaphores</td></tr>`;
        countingSemsTableBody.innerHTML = `<tr><td colspan="2" class="empty-row">No active counting semaphores</td></tr>`;
        peripheralsTableBody.innerHTML = `<tr><td colspan="4" class="empty-row">No active peripherals</td></tr>`;
        interruptsTableBody.innerHTML = `<tr><td colspan="3" class="empty-row">No active interrupts</td></tr>`;
        statusValidation.innerText = 'N/A';
        statusCompile.innerText = 'N/A';
        statusSummary.innerText = 'Generate an architecture to see summary.';
        modificationChipsRow.classList.add('hidden');
    }

    // ─────────────────────────────────────────────────────────────────────────
    // EVENT LISTENERS & INTERACTION
    // ─────────────────────────────────────────────────────────────────────────

    submitBtn.addEventListener('click', handleSubmit);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSubmit();
    });

    // Hide modification chips when user starts typing
    queryInput.addEventListener('input', () => {
        if (queryInput.value.trim() !== '') {
            modificationChipsRow.classList.add('hidden');
        } else {
            if (activeSnapshot) {
                modificationChipsRow.classList.remove('hidden');
            }
        }
    });

    resetBtn.addEventListener('click', resetSession);

    // Tag clicks trigger search input focus
    document.querySelectorAll('.tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const q = tag.getAttribute('data-query');
            queryInput.value = q;
            queryInput.focus();
            
            // Hide chips when selecting a quick tag too
            modificationChipsRow.classList.add('hidden');
        });
    });
});
