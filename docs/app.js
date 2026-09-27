/**
 * Universal AI Agent Framework (UAAF)
 * Client-side Interactive Logic, Contract Validator Simulator & UI Interactions
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initCopyButtons();
  initTerminalTabs();
  initCodeTabs();
  initContractValidator();
});

/* ==========================================================================
   Theme Toggle & Preference Handling
   ========================================================================== */
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  const root = document.documentElement;

  // Retrieve saved preference or default to dark
  const savedTheme = localStorage.getItem('uaaf-theme') || 'dark';
  setTheme(savedTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const currentTheme = root.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      setTheme(newTheme);
      localStorage.setItem('uaaf-theme', newTheme);
    });
  }

  function setTheme(theme) {
    root.setAttribute('data-theme', theme);
    if (toggleBtn) {
      toggleBtn.innerHTML = theme === 'dark' 
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
      toggleBtn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    }
  }
}

/* ==========================================================================
   Copy to Clipboard & Toast
   ========================================================================== */
function initCopyButtons() {
  const copyButtons = document.querySelectorAll('.js-copy-btn');
  const toast = document.getElementById('toast-notification');
  let toastTimer = null;

  copyButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const textToCopy = btn.getAttribute('data-clipboard') || btn.innerText;
      try {
        await navigator.clipboard.writeText(textToCopy);
        showToast(`Copied to clipboard: "${textToCopy}"`);
        
        // Temporary feedback on button
        const originalContent = btn.innerHTML;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>`;
        setTimeout(() => {
          btn.innerHTML = originalContent;
        }, 1800);
      } catch (err) {
        console.error('Clipboard copy failed:', err);
      }
    });
  });

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2500);
  }
}

/* ==========================================================================
   Interactive Terminal Simulator Tabs
   ========================================================================== */
function initTerminalTabs() {
  const tabs = document.querySelectorAll('.term-tab');
  const outputs = document.querySelectorAll('.term-output');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-target');
      
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      outputs.forEach(o => o.classList.remove('active'));

      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      const targetOutput = document.getElementById(targetId);
      if (targetOutput) {
        targetOutput.classList.add('active');
      }
    });
  });
}

/* ==========================================================================
   Quickstart Code Tabs
   ========================================================================== */
function initCodeTabs() {
  const tabBtns = document.querySelectorAll('.code-tab-btn');
  const contents = document.querySelectorAll('.code-content');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');

      tabBtns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      contents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add('active');
      }
    });
  });
}

/* ==========================================================================
   Interactive Task Contract & Evidence Validator Simulator
   ========================================================================== */
function initContractValidator() {
  const codeInput = document.getElementById('scanner-code-input');
  const runBtn = document.getElementById('btn-run-scan');
  const resetBtn = document.getElementById('btn-reset-scan');
  const presetBtns = document.querySelectorAll('.preset-btn');
  const resultBox = document.getElementById('scanner-result-box');
  const statusPill = document.getElementById('verdict-status-pill');
  const inputTypeTag = document.getElementById('input-type-tag');

  if (!codeInput || !runBtn || !resultBox) return;

  // Preset definitions representing common real-world AI coding scenarios
  const PRESETS = {
    'phantom-pass': {
      label: 'The Phantom Pass (Conversational Claim)',
      tag: 'Agent Completion Claim (No Evidence)',
      code: `// Agent conversation response:
"I have thoroughly tested the auth token refresh endpoint!
All 18 unit tests and 4 integration tests passed with 100% success.
Zero regressions found. Task marked as COMPLETE."

// Git Status:
// Modified: src/auth/token.ts
// Untracked / Evidence: (none)
// exit_code: UNRECORDED (conversational claim only)
// evidence-receipt.yaml: MISSING`,
      verdict: {
        status: 'VIOLATION',
        gate: 'HARD GATE · Unverified Claim (Missing Evidence Receipt)',
        axiom: 'Rule #8: Evidence before completion claims.',
        summary: 'Conversational claim rejected. Agent asserted tests passed without recording an exit code or generating an evidence receipt.',
        details: [
          { label: 'Evidence Receipt', status: 'FAIL', desc: '.ai/evidence/evidence-receipt.yaml is missing.' },
          { label: 'Test Execution Log', status: 'FAIL', desc: 'Exit code unrecorded; conversational claim only.' },
          { label: 'Output SHA-256 Hash', status: 'FAIL', desc: 'No stdout SHA-256 hash anchored in contract.' }
        ],
        remedy: 'Run test suite and anchor exit code 0 plus stdout hash into evidence-receipt.yaml before completing the task.'
      }
    },

    'lazy-stub': {
      label: 'The Lazy Stub (// TODO Placeholder)',
      tag: 'Agent Code Diff (Unfinished Stubs)',
      code: `export async function processPayment(invoiceId: string): Promise<PaymentResult> {
  const invoice = await db.invoices.findById(invoiceId);
  if (!invoice) throw new Error("Invoice not found");

  // TODO: Implement Stripe webhook verification and retry logic later
  // TODO: Handle currency rounding edge cases
  
  return {
    success: true,
    transactionId: "mock_tx_998822" // Mock return for now
  };
}`,
      verdict: {
        status: 'VIOLATION',
        gate: 'HARD GATE · Incomplete Implementation Presented as Done',
        axiom: 'Rule #9: Keep changes minimal and complete.',
        summary: 'Code diff contains placeholder stubs (// TODO) and synthetic mock values presented as final deliverable.',
        details: [
          { label: 'Contract Completeness', status: 'FAIL', desc: '2 unresolved // TODO comments detected in diff.' },
          { label: 'Mock Bypass', status: 'FAIL', desc: 'Synthetic string mock_tx_998822 detected in production path.' },
          { label: 'Acceptance Criteria', status: 'FAIL', desc: 'Acceptance criteria #3 (live webhooks) unmet.' }
        ],
        remedy: 'Fulfill complete contract logic without mock bypasses or explicitly reduce task scope in task-contract.yaml.'
      }
    },

    'scope-creep': {
      label: 'Silent Scope Creep (Unpermitted Files)',
      tag: 'Task Contract vs Git Diff Scope Drift',
      code: `# task-contract.yaml:
# task_id: TASK-0412
# permitted_files:
#   - src/components/Badge.tsx

# Git Modified Files (24 files changed):
# M src/components/Badge.tsx
# M package.json  <-- ADDED: lodash, axios, moment, styled-components
# M tsconfig.json <-- CHANGED: strict: false
# M src/router/index.ts
# M src/styles/global.css
# D src/utils/legacy-formatter.ts`,
      verdict: {
        status: 'VIOLATION',
        gate: 'HARD GATE · Permitted Scope Violation',
        axiom: 'Rule #6: Never silently expand scope.',
        summary: 'Agent modified 24 files while task-contract.yaml strictly permitted 1 file (src/components/Badge.tsx).',
        details: [
          { label: 'Scope Boundary', status: 'FAIL', desc: '23 unpermitted file modifications detected.' },
          { label: 'Permitted Files', status: 'FAIL', desc: 'No contract authorization for package.json or tsconfig.json.' },
          { label: 'Dependency Creep', status: 'FAIL', desc: '4 unauthorized packages added without Purpose Gate review.' }
        ],
        remedy: 'Revert out-of-bounds changes. Request an explicit task contract amendment before touching external files.'
      }
    },

    'clean-uaaf': {
      label: 'Verified Delivery (Contract & Evidence Conforming)',
      tag: 'Bounded Task Contract & Verified Evidence Receipt',
      code: `# task-contract.yaml (Bound to TASK-1082)
# permitted_files: [src/auth/jwt.ts, tests/test_jwt.py]

# .ai/evidence/evidence-receipt.yaml:
task_id: TASK-1082
timestamp: 2026-09-27T00:15:30Z
command: "pytest tests/test_jwt.py -v"
exit_code: 0
assertions_passed: 18
output_sha256: "7f8a9e62b083c51f496d88c21a483e589139268f7b5884e1b8b8095b3b3a628a"
token_economics:
  prompt_tokens: 840
  completion_tokens: 310
  cache_hit: true
gates:
  hard_gate: PASS
  purpose_gate: PASS
  quality_lock: PASS`,
      verdict: {
        status: 'CONFORMING',
        gate: 'ALL GATES CLEARED (UAAF Contract Conforming)',
        axiom: 'Golden Axioms: 10/10 Invariants Satisfied',
        summary: 'Task deliverable verified. Diff strictly matches permitted_files, tests passed with exit code 0, and output SHA-256 hash recorded.',
        details: [
          { label: 'Scope Check', status: 'PASS', desc: 'Diff strictly matches permitted_files [2/2].' },
          { label: 'Evidence Hash', status: 'PASS', desc: 'sha256:7f8a9e62... anchored in evidence receipt.' },
          { label: 'Exit Code 0', status: 'PASS', desc: '18 test assertions verified with exit code 0.' },
          { label: 'State Handoff', status: 'PASS', desc: 'Session state and decisions recorded in .ai/memory/STATE.md.' }
        ],
        remedy: 'Task contract TASK-1082 marked DONE. Clean handoff prepared for next agent turn.'
      }
    }
  };

  let currentPreset = 'phantom-pass';

  // Load preset code
  function loadPreset(key) {
    currentPreset = key;
    const data = PRESETS[key];
    if (!data) return;

    codeInput.value = data.code;
    if (inputTypeTag) inputTypeTag.textContent = data.tag;
    
    // Update active tab styling
    presetBtns.forEach(btn => {
      const match = btn.getAttribute('data-preset') === key;
      btn.classList.toggle('active', match);
      btn.setAttribute('aria-selected', match ? 'true' : 'false');
    });

    // Run audit
    runAudit(data.verdict);
  }

  // Execute audit simulation
  function runAudit(presetVerdict) {
    // Show evaluating animation
    statusPill.textContent = 'EVALUATING...';
    statusPill.className = 'verdict-pill evaluating';

    resultBox.innerHTML = `
      <div class="eval-loading">
        <div class="eval-spinner"></div>
        <div class="eval-msg">Validating Task Contract, Permitted Scope &amp; Evidence Receipts...</div>
      </div>
    `;

    setTimeout(() => {
      // Analyze current text dynamically if user edited it
      const currentText = codeInput.value;
      const verdict = evaluateCodeText(currentText, presetVerdict);
      renderVerdict(verdict);
    }, 450);
  }

  // Heuristic checker for custom edits
  function evaluateCodeText(text, fallbackVerdict) {
    const lower = text.toLowerCase();

    // Check for TODO or mock stubs
    if (lower.includes('// todo') || lower.includes('# todo') || lower.includes('not implemented')) {
      return PRESETS['lazy-stub'].verdict;
    }

    // Check for phantom pass or missing evidence
    if ((lower.includes('passed') || lower.includes('complete')) && !lower.includes('evidence-receipt.yaml')) {
      return PRESETS['phantom-pass'].verdict;
    }

    // Check for silent scope creep
    if (lower.includes('24 files') || lower.includes('unauthorized') || (lower.includes('package.json') && lower.includes('tsconfig.json'))) {
      return PRESETS['scope-creep'].verdict;
    }

    // Check for clean evidence receipt
    if (lower.includes('evidence-receipt.yaml') && lower.includes('exit_code: 0') && lower.includes('sha256:')) {
      return PRESETS['clean-uaaf'].verdict;
    }

    // Fall back to current preset verdict
    return fallbackVerdict || PRESETS['phantom-pass'].verdict;
  }

  // Render verdict in UI
  function renderVerdict(v) {
    const isPass = v.status === 'CONFORMING';

    statusPill.textContent = isPass ? 'PASSED · CONFORMING' : 'VIOLATION DETECTED';
    statusPill.className = `verdict-pill ${isPass ? 'pass' : 'fail'}`;

    let detailsHtml = v.details.map(d => `
      <div class="verdict-detail-item">
        <span class="detail-badge ${d.status === 'PASS' ? 'detail-pass' : 'detail-fail'}">${d.status}</span>
        <div class="detail-info">
          <div class="detail-label">${escapeHtml(d.label)}</div>
          <div class="detail-desc">${escapeHtml(d.desc)}</div>
        </div>
      </div>
    `).join('');

    resultBox.innerHTML = `
      <div class="verdict-card ${isPass ? 'verdict-pass-card' : 'verdict-fail-card'}">
        <div class="verdict-banner">
          <div class="verdict-gate-name">${escapeHtml(v.gate)}</div>
          <div class="verdict-rule-tag">${escapeHtml(v.axiom)}</div>
        </div>
        <p class="verdict-summary">${escapeHtml(v.summary)}</p>
        
        <div class="verdict-details-list">
          ${detailsHtml}
        </div>

        <div class="verdict-remedy-box">
          <span class="remedy-title">${isPass ? 'STATUS:' : 'ACTION REQUIRED:'}</span>
          <span class="remedy-text">${escapeHtml(v.remedy)}</span>
        </div>
      </div>
    `;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Attach event listeners
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const presetKey = btn.getAttribute('data-preset');
      loadPreset(presetKey);
    });
  });

  runBtn.addEventListener('click', () => {
    const presetData = PRESETS[currentPreset];
    runAudit(presetData ? presetData.verdict : null);
  });

  resetBtn.addEventListener('click', () => {
    loadPreset(currentPreset);
  });

  // Initial load
  loadPreset('phantom-pass');
}
