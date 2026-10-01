/* ═══════════════════════════════════════════════════════
   BioMentor AI — Core Application Logic
   Dynamic Course System with Adaptive Intelligence
   ═══════════════════════════════════════════════════════ */

const API = 'http://localhost:8000/api';

// ── State ────────────────────────────────────────────
let currentUser = null;
let currentView = 'dashboard';
let currentCourse = null;
let quizQuestions = [];
let quizAnswers = {};
let quizIndex = 0;
let chartInstances = {};

// ── Utility ──────────────────────────────────────────
async function api(path, options = {}) {
    try {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        throw e;
    }
}

function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function showView(name) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    const view = document.getElementById(`view-${name}`);
    if (view) {
        view.classList.remove('hidden');
        currentView = name;
    }
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.view === name);
    });
    if (name === 'dashboard') loadDashboard();
    if (name === 'analytics') loadAnalytics();
    if (name === 'admin') loadAdmin();
}

// ── Auth ─────────────────────────────────────────────
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');

    try {
        const data = await api('/student/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        currentUser = data.user;
        errorEl.classList.add('hidden');
        enterApp();
    } catch (e) {
        errorEl.textContent = e.message || 'Login failed';
        errorEl.classList.remove('hidden');
    }
}

async function handleRegister() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');

    if (!username || !password) {
        errorEl.textContent = 'Please enter username and password first';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const data = await api('/student/register', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        currentUser = data.user;
        errorEl.classList.add('hidden');
        toast('Account created!', 'success');
        enterApp();
    } catch (e) {
        errorEl.textContent = e.message || 'Registration failed';
        errorEl.classList.remove('hidden');
    }
}

function handleLogout() {
    currentUser = null;
    document.getElementById('login-page').classList.remove('hidden');
    document.getElementById('app-page').classList.add('hidden');
}

function enterApp() {
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('app-page').classList.remove('hidden');
    document.getElementById('nav-username').textContent = `${currentUser.role === 'admin' ? '🔧' : '🎓'} ${currentUser.username}`;

    const tabs = document.getElementById('nav-tabs');
    if (currentUser.role === 'admin') {
        tabs.innerHTML = `
            <button class="nav-tab active" data-view="admin" onclick="showView('admin')">📋 Admin Panel</button>
            <button class="nav-tab" data-view="dashboard" onclick="showView('dashboard')">📚 Courses</button>
        `;
        showView('admin');
    } else {
        tabs.innerHTML = `
            <button class="nav-tab active" data-view="dashboard" onclick="showView('dashboard')">📚 Courses</button>
            <button class="nav-tab" data-view="analytics" onclick="showView('analytics')">📊 Analytics</button>
        `;
        showView('dashboard');
    }
}


// ── Student Dashboard ────────────────────────────────
async function loadDashboard() {
    if (!currentUser) return;

    const container = document.getElementById('courses-container');
    container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading courses...</div>';

    try {
        const coursesData = await api('/student/courses');
        const courses = coursesData.courses;

        if (currentUser.role === 'student') {
            try {
                const analytics = await api(`/student/analytics/${currentUser.id}`);
                const d = analytics.dashboard;
                document.getElementById('stats-grid').innerHTML = `
                    <div class="glass-card stat-card blue">
                        <div class="stat-value">${d.overall_mastery}%</div>
                        <div class="stat-label">Overall Mastery</div>
                    </div>
                    <div class="glass-card stat-card purple">
                        <div class="stat-value">${d.courses_studied}/${d.courses_total}</div>
                        <div class="stat-label">Courses Studied</div>
                    </div>
                    <div class="glass-card stat-card green">
                        <div class="stat-value">${analytics.quiz_history.length}</div>
                        <div class="stat-label">Quizzes Taken</div>
                    </div>
                `;
            } catch (e) {
                document.getElementById('stats-grid').innerHTML = '';
            }
        } else {
            document.getElementById('stats-grid').innerHTML = '';
        }

        if (courses.length === 0) {
            container.innerHTML = `
                <div class="glass-card" style="text-align:center;padding:48px;">
                    <p style="font-size:1.5rem;margin-bottom:12px;">📭</p>
                    <p style="color:var(--text-secondary);">No courses available yet.</p>
                    <p style="color:var(--text-muted);font-size:0.85rem;margin-top:8px;">
                        ${currentUser.role === 'admin' ? 'Upload a PDF to auto-generate your first course!' : 'Ask your admin to upload study materials.'}
                    </p>
                </div>
            `;
            return;
        }

        const domains = {};
        courses.forEach(c => {
            const d = c.domain || 'General';
            if (!domains[d]) domains[d] = [];
            domains[d].push(c);
        });

        container.innerHTML = '';
        for (const [domain, domainCourses] of Object.entries(domains).sort()) {
            const section = document.createElement('div');
            section.className = 'domain-section';
            section.innerHTML = `
                <div class="domain-title">
                    ${getDomainIcon(domain)} ${domain}
                    <span class="domain-badge">${domainCourses.length} course${domainCourses.length > 1 ? 's' : ''}</span>
                </div>
                <div class="topics-grid">
                    ${domainCourses.map(c => renderCourseCard(c)).join('')}
                </div>
            `;
            container.appendChild(section);
        }
    } catch (e) {
        container.innerHTML = `<div class="glass-card" style="border-left:4px solid var(--accent-red)"><p style="color:var(--accent-red)">Failed to load courses: ${e.message}</p></div>`;
    }
}

function getDomainIcon(domain) {
    const icons = {
        'Molecular Biology': '🧬', 'Genetic Engineering': '🔬', 'Biotechnology': '🧪',
        'Bioinformatics': '💻', 'Biochemistry': '⚗️', 'Microbiology': '🦠', 'General Biology': '📖',
    };
    return icons[domain] || '📚';
}

function renderCourseCard(course) {
    const conceptsPreview = (course.concepts || []).slice(0, 3).join(' · ');
    return `
        <div class="glass-card topic-card" onclick="openCourse(${course.id})">
            <div class="topic-name">${course.title}</div>
            <div class="topic-desc">${course.summary || ''}</div>
            <div class="topic-meta">
                <span style="font-size:0.75rem;color:var(--text-muted);">${conceptsPreview}</span>
                <span class="mastery-badge ${course.difficulty ? course.difficulty.toLowerCase() : 'intermediate'}">${course.difficulty || 'Intermediate'}</span>
            </div>
        </div>
    `;
}


// ── Lesson View ──────────────────────────────────────
function askAboutConcept(concept) {
    var input = document.getElementById('chat-input');
    input.value = 'Explain the concept "' + concept + '" in simple terms. I need to understand it as a prerequisite.';
    sendChat();
}

async function openCourse(courseId) {
    currentCourse = courseId;
    showView('lesson');
    loadChatHistory();

    document.getElementById('lesson-title').textContent = 'Loading...';
    document.getElementById('lesson-mastery').textContent = '';
    document.getElementById('lesson-content').innerHTML = '<div class="loading"><div class="spinner"></div> Loading course content...</div>';

    try {
        var data = await api('/student/learn', {
            method: 'POST',
            body: JSON.stringify({ student_id: currentUser.id, course_id: courseId }),
        });

        var course = data.course;
        var sections = data.sections || [];
        var learningStatus = data.learning_status || {};

        document.getElementById('lesson-title').textContent = course.title;

        var subtitleParts = ['Mastery: ' + data.avg_mastery + '%'];
        if (course.domain && course.domain !== 'Not specified in text') subtitleParts.push(course.domain);
        subtitleParts.push(course.difficulty);
        if (sections.length > 0) subtitleParts.push(sections.length + ' sections');
        document.getElementById('lesson-mastery').textContent = subtitleParts.join(' \u00b7 ');

        var html = '';

        // Course overview
        if (course.summary) {
            html += '<div class="glass-card lesson-section" style="border-left:3px solid var(--accent-green);">' +
                '<h3>\ud83d\udcda Course Overview</h3>' +
                '<p>' + course.summary.replace(/\n/g, '<br>') + '</p>' +
                '</div>';
        }

        // View Original PDF + Action buttons
        var actionBtns = '';
        if (data.pdf_url) {
            actionBtns += '<a href="' + data.pdf_url + '" target="_blank" style="padding:8px 16px;border-radius:8px;background:rgba(99,102,241,0.1);color:var(--accent-purple);border:1px solid rgba(99,102,241,0.2);text-decoration:none;font-size:0.85rem;font-weight:600;">\ud83d\udcc4 View Original PDF</a>';
        }
        if (actionBtns) {
            html += '<div style="display:flex;gap:10px;margin-bottom:16px;">' + actionBtns + '</div>';
        }

        // Section-based content (grounded)
        if (sections.length > 0) {
            html += sections.map(function (sec, i) {
                var sectionHtml = '<div class="glass-card lesson-section" onclick="trackSectionView(' + courseId + ',' + i + ',this)" data-section="' + i + '" style="margin-bottom:16px;">';
                sectionHtml += '<h3>\ud83d\udcd6 ' + (sec.section_title || 'Section ' + (i + 1)) + '</h3>';

                // Detailed explanation
                if (sec.detailed_explanation) {
                    sectionHtml += '<div style="margin:12px 0;line-height:1.7;">' + sec.detailed_explanation.replace(/\n/g, '<br>') + '</div>';
                }

                // Key points
                if (sec.key_points && sec.key_points.length > 0) {
                    sectionHtml += '<div style="margin:12px 0;padding:12px;border-radius:8px;background:rgba(16,185,129,0.05);border:1px solid rgba(16,185,129,0.15);">' +
                        '<strong style="color:var(--accent-green);font-size:0.88rem;">\ud83c\udfaf Key Points</strong><ul style="margin:6px 0 0 0;padding-left:20px;">' +
                        sec.key_points.map(function (p) { return '<li style="margin:4px 0;">' + p + '</li>'; }).join('') +
                        '</ul></div>';
                }

                // Explicit concepts (inline pills)
                if (sec.explicit_concepts && sec.explicit_concepts.length > 0) {
                    sectionHtml += '<div style="margin:8px 0;display:flex;flex-wrap:wrap;gap:6px;">' +
                        sec.explicit_concepts.map(function (c) {
                            return '<span style="padding:4px 10px;border-radius:14px;background:rgba(99,102,241,0.1);color:var(--accent-purple);font-size:0.78rem;font-weight:600;">' + c + '</span>';
                        }).join('') + '</div>';
                }

                // Mentioned challenges
                if (sec.mentioned_challenges && sec.mentioned_challenges.length > 0) {
                    sectionHtml += '<div style="margin:8px 0;padding:10px;border-radius:8px;background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.15);">' +
                        '<strong style="color:var(--accent-orange);font-size:0.85rem;">\u26a0\ufe0f Challenges</strong><ul style="margin:4px 0 0 0;padding-left:20px;">' +
                        sec.mentioned_challenges.map(function (c) { return '<li style="margin:3px 0;font-size:0.88rem;">' + c + '</li>'; }).join('') +
                        '</ul></div>';
                }

                // Mentioned applications
                if (sec.mentioned_applications && sec.mentioned_applications.length > 0) {
                    sectionHtml += '<div style="margin:8px 0;padding:10px;border-radius:8px;background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.15);">' +
                        '<strong style="color:var(--accent-blue);font-size:0.85rem;">\ud83d\ude80 Applications</strong><ul style="margin:4px 0 0 0;padding-left:20px;">' +
                        sec.mentioned_applications.map(function (a) { return '<li style="margin:3px 0;font-size:0.88rem;">' + a + '</li>'; }).join('') +
                        '</ul></div>';
                }

                // Section summary
                if (sec.section_summary) {
                    sectionHtml += '<div style="margin:10px 0 0 0;padding:10px 14px;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);">' +
                        '<strong style="font-size:0.85rem;color:var(--text-muted);">\ud83d\udcdd Summary:</strong> ' +
                        '<span style="font-size:0.88rem;">' + sec.section_summary + '</span></div>';
                }

                sectionHtml += '</div>';
                return sectionHtml;
            }).join('');
        } else {
            html += '<div class="glass-card lesson-section">' +
                '<h3>\ud83d\udcd6 Course Content</h3>' +
                '<p style="color:var(--text-muted);">No sections generated yet. This course may need to be re-uploaded.</p>' +
                '</div>';
        }

        // Admin Notes (enrichment — separate from core)
        if (data.additional_notes && data.additional_notes.trim()) {
            html += '<div class="glass-card lesson-section" style="border-left:3px solid var(--accent-blue);">' +
                '<h3>\ud83d\udcdd Instructor Notes</h3>' +
                '<p style="color:var(--text-secondary);font-style:italic;">' + data.additional_notes.replace(/\n/g, '<br>') + '</p>' +
                '</div>';
        }

        // Reference Links (enrichment — separate from core)
        if (data.references && data.references.length > 0) {
            html += '<div class="glass-card lesson-section" style="border-left:3px solid var(--accent-blue);">' +
                '<h3>\ud83d\udd17 Reference Materials</h3>' +
                '<div style="display:flex;flex-direction:column;gap:8px;">' +
                data.references.map(function (ref) {
                    return '<a href="' + ref.url + '" target="_blank" style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:8px;background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.15);text-decoration:none;color:var(--accent-blue);font-size:0.88rem;">' +
                        '\ud83d\udcda ' + ref.title + ' <span style="font-size:0.75rem;color:var(--text-muted);margin-left:auto;">\u2197</span></a>';
                }).join('') +
                '</div></div>';
        }

        // Key Concepts with behavioral status badges
        if (data.concepts && data.concepts.length > 0) {
            var conceptPills = data.concepts.map(function (c) {
                var m = data.mastery[c] || 0;
                var color = m >= 70 ? 'var(--accent-green)' : m >= 40 ? 'var(--accent-orange)' : m > 0 ? 'var(--accent-red)' : 'var(--text-muted)';
                var statusBadge = '';
                if (learningStatus[c]) {
                    var ls = learningStatus[c];
                    statusBadge = ' <span title="' + ls.reason + '" style="font-size:0.7rem;">' + ls.icon + '</span>';
                }
                return '<span style="padding:6px 14px;border-radius:20px;background:rgba(255,255,255,0.05);border:1px solid ' + color + ';color:' + color + ';font-size:0.82rem;font-weight:600;">' + c + ': ' + m + '%' + statusBadge + '</span>';
            }).join('');
            html += '<div class="glass-card lesson-section"><h3>\ud83e\udde0 Key Concepts</h3>' +
                '<div style="display:flex;flex-wrap:wrap;gap:8px;">' + conceptPills + '</div></div>';
        }

        // Knowledge Graph (relationships)
        if (data.graph && data.graph.length > 0) {
            html += '<div class="glass-card lesson-section"><h3>\ud83d\udd17 Knowledge Graph</h3><ul>' +
                data.graph.map(function (g) {
                    var label = g.relation_type ? ' <span style="color:var(--text-muted);font-size:0.8rem;font-style:italic;">(' + g.relation_type + ')</span>' : '';
                    return '<li><strong>' + g.source + '</strong> \u2192 ' + g.target + label + '</li>';
                }).join('') +
                '</ul></div>';
        }

        // Cross-course prerequisites
        if (data.cross_course_prereqs && data.cross_course_prereqs.length > 0) {
            html += '<div class="glass-card lesson-section" style="border-left:3px solid var(--accent-orange);">' +
                '<h3>\ud83d\udcda Recommended Prerequisite Courses</h3>' +
                '<p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:12px;">These courses cover prerequisite concepts:</p>' +
                data.cross_course_prereqs.map(function (cp) {
                    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;margin:6px 0;border-radius:8px;background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.15);cursor:pointer;" onclick="openCourse(' + cp.course_id + ')">' +
                        '<div><strong style="font-size:0.9rem;">' + cp.course_title + '</strong>' +
                        '<span style="font-size:0.78rem;color:var(--text-muted);margin-left:8px;">covers: ' + cp.matching_concepts.join(', ') + '</span></div>' +
                        '<span style="font-size:0.82rem;color:var(--accent-orange);">Open \u2192</span></div>';
                }).join('') +
                '</div>';
        }

        // Unresolved prerequisites
        if (data.unresolved_prereqs && data.unresolved_prereqs.length > 0) {
            html += '<div class="glass-card lesson-section" style="border-left:3px solid var(--accent-purple);">' +
                '<h3>\ud83d\udcac Need Help With Prerequisites?</h3>' +
                '<p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:8px;">These aren\'t in any course yet \u2014 ask the AI Tutor:</p>' +
                '<div style="display:flex;flex-wrap:wrap;gap:6px;">' +
                data.unresolved_prereqs.map(function (concept) {
                    return '<span style="padding:5px 12px;border-radius:20px;background:rgba(124,58,237,0.1);color:var(--accent-purple);font-size:0.82rem;cursor:pointer;" onclick="askAboutConcept(\'' + concept + '\')">' + concept + ' \ud83d\udcac</span>';
                }).join('') +
                '</div></div>';
        }

        document.getElementById('lesson-content').innerHTML = html;
    } catch (e) {
        document.getElementById('lesson-content').innerHTML =
            '<div class="glass-card" style="border-left:4px solid var(--accent-red)">' +
            '<p style="color:var(--accent-red)">\u274c Failed to load course: ' + e.message + '</p>' +
            '<p style="color:var(--text-secondary);margin-top:8px;">Make sure the server is running.</p></div>';
    }
}

// Track section view for behavioral intelligence
var sectionViewTimers = {};
function trackSectionView(courseId, sectionIndex, element) {
    // Track that this section was viewed
    if (!sectionViewTimers[sectionIndex]) {
        sectionViewTimers[sectionIndex] = Date.now();
        // Send section_viewed event after 5 seconds (meaningful engagement)
        setTimeout(function () {
            var duration = Math.round((Date.now() - sectionViewTimers[sectionIndex]) / 1000);
            api('/student/track-event', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: currentUser.id,
                    course_id: courseId,
                    event_type: 'section_viewed',
                    section_index: sectionIndex,
                    duration_seconds: duration
                })
            }).catch(function () { });
        }, 5000);
    }
}


// ── Quiz System ──────────────────────────────────────
async function startQuiz() {
    if (!currentCourse) return;
    showView('quiz');
    quizAnswers = {};
    quizIndex = 0;

    // Read selected question count and hide the selector
    const quizCountSelect = document.getElementById('quiz-count');
    const numQuestions = parseInt(quizCountSelect.value) || 5;
    const optionsBar = document.getElementById('quiz-options-bar');
    optionsBar.style.display = 'none';

    document.getElementById('quiz-container').innerHTML = '<div class="loading"><div class="spinner"></div> Generating ' + numQuestions + ' quiz questions...</div>';

    try {
        const data = await api('/student/quiz', {
            method: 'POST',
            body: JSON.stringify({
                student_id: currentUser.id,
                course_id: currentCourse,
                num_questions: numQuestions,
            }),
        });
        quizQuestions = data.questions;
        renderQuizQuestion();
    } catch (e) {
        optionsBar.style.display = '';
        document.getElementById('quiz-container').innerHTML = `
            <div class="glass-card" style="border-left:4px solid var(--accent-red)">
                <p style="color:var(--accent-red)">❌ Failed to generate quiz: ${e.message}</p>
            </div>`;
    }
}

function renderQuizQuestion() {
    const total = quizQuestions.length;
    const q = quizQuestions[quizIndex];

    document.getElementById('quiz-progress-fill').style.width = `${((quizIndex + 1) / total) * 100}%`;
    document.getElementById('quiz-progress-text').textContent = `${quizIndex + 1}/${total}`;

    const options = typeof q.options === 'object' && !Array.isArray(q.options)
        ? q.options
        : { A: q.options[0], B: q.options[1], C: q.options[2], D: q.options[3] };

    document.getElementById('quiz-container').innerHTML = `
        <div class="glass-card question-card">
            <div class="question-text">Q${quizIndex + 1}. ${q.question}</div>
            ${q.concept_tag ? `<div style="font-size:0.78rem;color:var(--accent-purple);margin-bottom:12px;">Concept: ${q.concept_tag}</div>` : ''}
            <div class="options-list">
                ${Object.entries(options).map(([key, val]) => `
                    <button class="option-btn ${quizAnswers[quizIndex] === key ? 'selected' : ''}"
                            onclick="selectOption(${quizIndex}, '${key}')">
                        <span class="option-letter">${key}</span>
                        <span>${val}</span>
                    </button>
                `).join('')}
            </div>
        </div>
    `;

    document.getElementById('quiz-prev-btn').disabled = quizIndex === 0;
    const nextBtn = document.getElementById('quiz-next-btn');
    if (quizIndex === total - 1) {
        nextBtn.textContent = '✅ Submit Quiz';
        nextBtn.className = 'btn btn-success';
    } else {
        nextBtn.textContent = 'Next →';
        nextBtn.className = 'btn btn-primary';
    }
}

function selectOption(questionIdx, option) {
    quizAnswers[questionIdx] = option;
    renderQuizQuestion();
}

function quizPrev() {
    if (quizIndex > 0) { quizIndex--; renderQuizQuestion(); }
}

async function quizNext() {
    if (quizIndex < quizQuestions.length - 1) {
        quizIndex++;
        renderQuizQuestion();
    } else {
        await submitQuiz();
    }
}

async function submitQuiz() {
    if (Object.keys(quizAnswers).length < quizQuestions.length) {
        toast('Please answer all questions before submitting', 'error');
        return;
    }

    showView('results');
    document.getElementById('results-container').innerHTML = '<div class="loading"><div class="spinner"></div> Evaluating your answers...</div>';

    try {
        const formattedAnswers = {};
        for (const [k, v] of Object.entries(quizAnswers)) {
            formattedAnswers[String(k)] = v;
        }

        const data = await api('/student/submit-quiz', {
            method: 'POST',
            body: JSON.stringify({
                student_id: currentUser.id,
                course_id: currentCourse,
                questions: quizQuestions,
                answers: formattedAnswers,
            }),
        });

        renderResults(data);
    } catch (e) {
        document.getElementById('results-container').innerHTML = `
            <div class="glass-card" style="border-left:4px solid var(--accent-red)">
                <p style="color:var(--accent-red)">❌ Evaluation failed: ${e.message}</p>
            </div>`;
    }
}

function renderResults(data) {
    const ev = data.evaluation;
    const rec = data.recommendation;
    const scoreClass = ev.overall_score >= 70 ? 'high' : ev.overall_score >= 40 ? 'medium' : 'low';

    document.getElementById('results-container').innerHTML = `
        <div class="glass-card result-header">
            <div class="result-score ${scoreClass}">${ev.overall_score}%</div>
            <p style="font-size:1.1rem;color:var(--text-secondary);">${ev.correct_answers}/${ev.total_questions} correct</p>
            <p style="margin-top:12px;color:var(--text-primary);font-size:0.95rem;">${ev.feedback}</p>
        </div>

        ${rec ? `
            <div class="glass-card recommendation-card">
                <div class="action ${rec.action}">${rec.action === 'advance' ? '🚀' : rec.action === 'practice' ? '📝' : '⚠️'} ${rec.action}</div>
                <p style="color:var(--text-secondary);font-size:0.92rem;line-height:1.6;margin-bottom:16px;">${rec.reason}</p>
                ${rec.weak_concepts && rec.weak_concepts.length > 0 ? `
                    <div style="margin-top:8px;">
                        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:8px;">Weak Concepts:</p>
                        ${rec.weak_concepts.map(c => `
                            <span style="display:inline-block;padding:4px 12px;margin:4px;border-radius:20px;background:rgba(239,68,68,0.1);color:var(--accent-red);font-size:0.82rem;">${c}</span>
                        `).join('')}
                    </div>
                ` : ''}
                ${rec.weak_prerequisites && rec.weak_prerequisites.length > 0 ? `
                    <div style="margin-top:12px;padding:12px;background:rgba(245,158,11,0.05);border-radius:8px;border:1px solid rgba(245,158,11,0.15);">
                        <p style="font-size:0.85rem;color:var(--accent-orange);margin-bottom:8px;">⚠️ Weak Prerequisites (study these first):</p>
                        ${rec.weak_prerequisites.map(wp => `
                            <span style="display:inline-block;padding:4px 12px;margin:4px;border-radius:20px;background:rgba(245,158,11,0.1);color:var(--accent-orange);font-size:0.82rem;">
                                ${wp.concept}: ${wp.mastery}% (needed for ${wp.needed_for})
                            </span>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        ` : ''}

        <div class="glass-card" style="margin-top:24px;">
            <h3 class="card-title" style="margin-bottom:16px;">📋 Question Details</h3>
            ${ev.details.map((d, i) => `
                <div style="padding:16px;border-bottom:1px solid var(--border-glass);${d.is_correct ? '' : 'background:rgba(239,68,68,0.03);'}">
                    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                        <strong style="font-size:0.9rem;">Q${i + 1}. ${d.question}</strong>
                        <span style="font-size:0.85rem;${d.is_correct ? 'color:var(--accent-green)' : 'color:var(--accent-red)'}">
                            ${d.is_correct ? '✅ Correct' : '❌ Wrong'}
                        </span>
                    </div>
                    ${!d.is_correct ? `<p style="font-size:0.85rem;color:var(--text-secondary);">Your answer: ${d.your_answer} · Correct: ${d.correct_answer}</p>` : ''}
                    ${d.explanation ? `<p style="font-size:0.82rem;color:var(--text-muted);margin-top:4px;">💡 ${d.explanation}</p>` : ''}
                    ${d.concept_tag ? `<p style="font-size:0.75rem;color:var(--accent-purple);margin-top:4px;">Concept: ${d.concept_tag}</p>` : ''}
                </div>
            `).join('')}
        </div>

        <div style="display:flex;gap:12px;margin-top:24px;">
            <button class="btn btn-secondary" onclick="showView('dashboard')">← Back to Dashboard</button>
            <button class="btn btn-primary" onclick="openCourse(${currentCourse})">📚 Review Course</button>
            <button class="btn btn-success" onclick="startQuiz()">🔄 Retake Quiz</button>
        </div>
    `;
}


// ── Analytics ────────────────────────────────────────
async function loadAnalytics() {
    if (!currentUser || currentUser.role !== 'student') return;

    try {
        const data = await api(`/student/analytics/${currentUser.id}`);
        const d = data.dashboard;

        document.getElementById('analytics-stats').innerHTML = `
            <div class="glass-card stat-card blue">
                <div class="stat-value">${d.overall_mastery}%</div>
                <div class="stat-label">Overall Mastery</div>
            </div>
            <div class="glass-card stat-card green">
                <div class="stat-value">${d.courses_studied}</div>
                <div class="stat-label">Courses Studied</div>
            </div>
            <div class="glass-card stat-card orange">
                <div class="stat-value">${d.courses_total}</div>
                <div class="stat-label">Total Courses</div>
            </div>
        `;

        const studied = d.all_courses.filter(c => c.avg_mastery > 0);
        if (studied.length > 0) renderMasteryChart(studied);
        if (Object.keys(d.domain_breakdown).length > 0) renderDomainChart(d.domain_breakdown);
        renderHeatmap(d.all_courses);

    } catch (e) {
        toast('Failed to load analytics', 'error');
    }
}

function renderMasteryChart(courses) {
    const ctx = document.getElementById('mastery-chart');
    if (chartInstances.mastery) chartInstances.mastery.destroy();

    chartInstances.mastery = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: courses.map(c => c.title.length > 20 ? c.title.slice(0, 20) + '...' : c.title),
            datasets: [{
                label: 'Mastery %',
                data: courses.map(c => c.avg_mastery),
                backgroundColor: courses.map(c =>
                    c.avg_mastery >= 70 ? 'rgba(16,185,129,0.7)' :
                        c.avg_mastery >= 40 ? 'rgba(245,158,11,0.7)' :
                            'rgba(239,68,68,0.7)'
                ),
                borderRadius: 6,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { max: 100, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8', maxRotation: 45 } },
            },
        },
    });
}

function renderDomainChart(domains) {
    const ctx = document.getElementById('domain-chart');
    if (chartInstances.domain) chartInstances.domain.destroy();

    const labels = Object.keys(domains);
    const values = labels.map(d => domains[d].avg_mastery);
    const colors = ['#00d4ff', '#7c3aed', '#10b981', '#f59e0b', '#ec4899'];

    chartInstances.domain = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', padding: 12, font: { size: 11 } },
                },
            },
        },
    });
}

function renderHeatmap(courses) {
    const container = document.getElementById('mastery-heatmap');
    container.innerHTML = courses.map(c => {
        const score = c.avg_mastery || 0;
        let bg, color;
        if (score === 0) { bg = 'rgba(100,116,139,0.1)'; color = '#64748b'; }
        else if (score < 30) { bg = 'rgba(239,68,68,0.2)'; color = '#ef4444'; }
        else if (score < 50) { bg = 'rgba(245,158,11,0.2)'; color = '#f59e0b'; }
        else if (score < 70) { bg = 'rgba(0,212,255,0.2)'; color = '#00d4ff'; }
        else if (score < 90) { bg = 'rgba(16,185,129,0.2)'; color = '#10b981'; }
        else { bg = 'rgba(124,58,237,0.2)'; color = '#7c3aed'; }

        return `<div class="heatmap-cell" style="background:${bg};color:${color};" onclick="openCourse(${c.id})">
            ${c.title.length > 16 ? c.title.slice(0, 16) + '…' : c.title}<br><strong>${score}%</strong>
        </div>`;
    }).join('');
}


// ── Admin ────────────────────────────────────────────
async function loadAdmin() {
    try {
        const [statsData, coursesData, materialsData] = await Promise.all([
            api('/admin/stats'),
            api('/admin/courses'),
            api('/admin/materials'),
        ]);

        document.getElementById('admin-stats').innerHTML = `
            <div class="glass-card stat-card blue">
                <div class="stat-value">${statsData.total_courses}</div>
                <div class="stat-label">Courses Generated</div>
            </div>
            <div class="glass-card stat-card purple">
                <div class="stat-value">${statsData.total_concepts}</div>
                <div class="stat-label">Concepts Extracted</div>
            </div>
            <div class="glass-card stat-card green">
                <div class="stat-value">${statsData.total_sections || 0}</div>
                <div class="stat-label">Sections</div>
            </div>
            <div class="glass-card stat-card orange">
                <div class="stat-value">${statsData.total_students}</div>
                <div class="stat-label">Students</div>
            </div>
        `;

        const coursesContainer = document.getElementById('admin-courses-container');
        if (coursesData.courses.length === 0) {
            coursesContainer.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:24px;">No courses yet. Upload a PDF to generate your first course!</p>';
        } else {
            coursesContainer.innerHTML = coursesData.courses.map(c => `
                <div class="glass-card" style="margin-bottom:16px;padding:16px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <strong style="font-size:0.95rem;">${c.title}</strong>
                            <span style="margin-left:12px;font-size:0.78rem;padding:3px 10px;border-radius:20px;background:rgba(0,212,255,0.1);color:var(--accent-blue);">${c.domain}</span>
                            <span style="margin-left:8px;font-size:0.78rem;padding:3px 10px;border-radius:20px;background:rgba(124,58,237,0.1);color:var(--accent-purple);">${c.difficulty}</span>
                            <p style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px;">${c.summary || ''}</p>
                            <p style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">📄 ${c.source_filename || 'N/A'} · 📑 ${c.section_count || 0} sections · 🧠 ${c.concepts.length} concepts · ${new Date(c.created_at).toLocaleDateString()}</p>
                        </div>
                        <div style="display:flex;gap:8px;">
                            <button class="btn btn-sm" style="background:rgba(59,130,246,0.1);color:var(--accent-blue);border:1px solid rgba(59,130,246,0.2);" onclick="toggleCourseEnrich(${c.id})">⚙️ Enrich</button>
                            <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:var(--accent-red);border:1px solid rgba(239,68,68,0.2);" onclick="deleteCourse(${c.id})">🗑️</button>
                        </div>
                    </div>
                    <!-- Enrichment Panel (hidden by default) -->
                    <div id="enrich-panel-${c.id}" style="display:none;margin-top:16px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.06);">
                        <!-- View PDF -->
                        ${c.source_filename ? `<div style="margin-bottom:16px;"><a href="/uploads/${c.source_filename}" target="_blank" class="btn btn-sm" style="background:rgba(99,102,241,0.1);color:var(--accent-purple);border:1px solid rgba(99,102,241,0.2);text-decoration:none;">📄 View Original PDF</a></div>` : ''}

                        <!-- Reference Links -->
                        <div style="margin-bottom:16px;">
                            <h4 style="font-size:0.88rem;margin-bottom:10px;color:var(--text-primary);">🔗 Reference Links</h4>
                            <div id="refs-list-${c.id}" style="margin-bottom:10px;"></div>
                            <div style="display:flex;gap:8px;">
                                <input type="text" id="ref-title-${c.id}" class="input-field" placeholder="Link title" style="flex:1;font-size:0.85rem;padding:8px 12px;">
                                <input type="text" id="ref-url-${c.id}" class="input-field" placeholder="https://..." style="flex:2;font-size:0.85rem;padding:8px 12px;">
                                <button class="btn btn-sm btn-primary" onclick="addReference(${c.id})">+ Add</button>
                            </div>
                        </div>

                        <!-- Admin Notes -->
                        <div>
                            <h4 style="font-size:0.88rem;margin-bottom:10px;color:var(--text-primary);">📝 Instructor Notes</h4>
                            <textarea id="notes-${c.id}" class="input-field" placeholder="Add notes, corrections, simplified explanations, lab procedures..." style="width:100%;min-height:80px;font-size:0.85rem;padding:10px 12px;resize:vertical;"></textarea>
                            <button class="btn btn-sm btn-primary" style="margin-top:8px;" onclick="saveNotes(${c.id})">💾 Save Notes</button>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        const tbody = document.getElementById('materials-body');
        tbody.innerHTML = materialsData.materials.length > 0
            ? materialsData.materials.map(m => `
                <tr>
                    <td>📄 ${m.filename}</td>
                    <td>${m.course_title || 'N/A'}</td>
                    <td>${m.education_level}</td>
                    <td style="color:var(--text-muted);font-size:0.82rem;">${new Date(m.uploaded_at).toLocaleDateString()}</td>
                </tr>
            `).join('')
            : '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:32px;">No materials uploaded yet</td></tr>';

    } catch (e) {
        toast('Failed to load admin data', 'error');
    }
}

// Toggle course enrichment panel and load data
async function toggleCourseEnrich(courseId) {
    const panel = document.getElementById(`enrich-panel-${courseId}`);
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        // Load references
        await loadCourseReferences(courseId);
        // Load existing notes
        try {
            const data = await api(`/admin/courses/${courseId}/references`);
            // Notes are loaded separately via learn API, but let's try to get from course
        } catch (e) { }
    } else {
        panel.style.display = 'none';
    }
}

// Load reference links for a course
async function loadCourseReferences(courseId) {
    const container = document.getElementById(`refs-list-${courseId}`);
    try {
        const data = await api(`/admin/courses/${courseId}/references`);
        if (data.references.length === 0) {
            container.innerHTML = '<p style="font-size:0.8rem;color:var(--text-muted);padding:4px 0;">No references added yet</p>';
        } else {
            container.innerHTML = data.references.map(r => `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;margin-bottom:6px;border-radius:8px;background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.1);">
                    <a href="${r.url}" target="_blank" style="color:var(--accent-blue);font-size:0.85rem;text-decoration:none;">📚 ${r.title}</a>
                    <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:var(--accent-red);border:none;padding:4px 8px;font-size:0.75rem;" onclick="deleteReference(${r.id}, ${courseId})">✕</button>
                </div>
            `).join('');
        }
    } catch (e) {
        container.innerHTML = '<p style="font-size:0.8rem;color:var(--accent-red);">Failed to load references</p>';
    }
}

// Add a reference link
async function addReference(courseId) {
    const titleInput = document.getElementById(`ref-title-${courseId}`);
    const urlInput = document.getElementById(`ref-url-${courseId}`);
    const title = titleInput.value.trim();
    const url = urlInput.value.trim();

    if (!title || !url) {
        toast('Please enter both title and URL', 'error');
        return;
    }

    try {
        await api(`/admin/courses/${courseId}/references`, {
            method: 'POST',
            body: JSON.stringify({ title, url }),
        });
        titleInput.value = '';
        urlInput.value = '';
        toast('Reference added', 'success');
        await loadCourseReferences(courseId);
    } catch (e) {
        toast('Failed to add reference: ' + e.message, 'error');
    }
}

// Delete a reference link
async function deleteReference(refId, courseId) {
    try {
        await api(`/admin/references/${refId}`, { method: 'DELETE' });
        toast('Reference removed', 'success');
        await loadCourseReferences(courseId);
    } catch (e) {
        toast('Failed to delete: ' + e.message, 'error');
    }
}

// Save admin notes
async function saveNotes(courseId) {
    const textarea = document.getElementById(`notes-${courseId}`);
    const notes = textarea.value;

    try {
        await api(`/admin/courses/${courseId}/notes`, {
            method: 'PUT',
            body: JSON.stringify({ notes }),
        });
        toast('Notes saved', 'success');
    } catch (e) {
        toast('Failed to save notes: ' + e.message, 'error');
    }
}

async function deleteCourse(courseId) {
    if (!confirm('Delete this course? This will remove all associated concepts and graph data.')) return;
    try {
        await api(`/admin/courses/${courseId}`, { method: 'DELETE' });
        toast('Course deleted', 'success');
        loadAdmin();
    } catch (e) {
        toast('Failed to delete: ' + e.message, 'error');
    }
}

function updateUploadLabel(input) {
    const label = document.getElementById('upload-label');
    label.textContent = input.files[0] ? `📎 ${input.files[0].name}` : 'Click to select PDF or text file';
}

async function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file');
    if (!fileInput.files[0]) {
        toast('Please select a file first', 'error');
        return;
    }

    const btn = document.getElementById('upload-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Generating course with AI...';

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('education_level', document.getElementById('upload-level').value);
    formData.append('difficulty', document.getElementById('upload-difficulty').value);

    try {
        const res = await fetch(`${API}/admin/upload`, { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Upload failed');

        toast(`✅ Course "${data.course_title}" generated — ${data.concepts_extracted} concepts, ${data.graph_edges} prerequisite edges`, 'success');
        fileInput.value = '';
        document.getElementById('upload-label').textContent = 'Click to select PDF or text file';
        loadAdmin();
    } catch (e) {
        toast('Upload failed: ' + e.message, 'error');
    }

    btn.disabled = false;
    btn.textContent = '⬆️ Upload & Generate Course';
}


// ── AI Chatbot ───────────────────────────────────────
let chatOpen = true;

function toggleInlineChat() {
    const body = document.getElementById('inline-chat-body');
    const toggleText = document.getElementById('chat-toggle-text');
    chatOpen = !chatOpen;
    body.classList.toggle('collapsed', !chatOpen);
    toggleText.textContent = chatOpen ? '▼ Collapse' : '▲ Expand';
}

function addChatBubble(role, message) {
    const container = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    bubble.innerHTML = message.replace(/\n/g, '<br>');
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
    return bubble;
}

function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble assistant typing';
    bubble.id = 'typing-indicator';
    bubble.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message || !currentCourse || !currentUser) return;

    input.value = '';
    input.disabled = true;
    document.getElementById('chat-send-btn').disabled = true;

    addChatBubble('user', message);
    showTypingIndicator();

    try {
        const data = await api('/student/chat', {
            method: 'POST',
            body: JSON.stringify({
                student_id: currentUser.id,
                course_id: currentCourse,
                message: message,
            }),
        });

        removeTypingIndicator();
        const toneTag = data.tone ? `<span class="chat-mastery-tag ${data.tone}">${data.tone} mode · ${data.mastery_level}% mastery</span><br>` : '';
        addChatBubble('assistant', toneTag + data.response);
    } catch (e) {
        removeTypingIndicator();
        addChatBubble('assistant', `⚠️ Sorry, I couldn't process that: ${e.message}`);
    }

    input.disabled = false;
    document.getElementById('chat-send-btn').disabled = false;
    input.focus();
}

async function loadChatHistory() {
    if (!currentUser || !currentCourse) return;
    try {
        const data = await api(`/student/chat-history/${currentUser.id}/${currentCourse}`);
        const container = document.getElementById('chat-messages');
        container.innerHTML = `
            <div class="chat-bubble assistant">
                👋 Hi! I'm your AI tutor. Ask me anything about this course — I'll adapt my explanation to your mastery level!
            </div>
        `;
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                addChatBubble(msg.role === 'user' ? 'user' : 'assistant', msg.message);
            });
        }
    } catch (e) {
        console.log('Could not load chat history:', e);
    }
}
