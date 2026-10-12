/* ============================================================
   LAKSHYA - JavaScript for the Flask site
   Every block checks that its elements exist, so one file works
   on all pages (home, assistant, dashboard, login, register).
   ============================================================ */
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const URLS = window.LAKSHYA_URLS || {};

function toast(text) {
    const t = $('#toast');
    if (!t) return;
    t.textContent = text;
    t.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove('show'), 2600);
}

/* 1. MENU + SMOOTH SCROLL ----------------------------------- */
if ($('#burger') && $('#links')) {
    $('#burger').onclick = () => $('#links').classList.toggle('open');
}

// Links that point to a section on the page we are already on scroll smoothly.
$$('a[href*="#"]').forEach(link => {
    link.addEventListener('click', e => {
        if (link.pathname !== location.pathname) return;   // other page: let browser navigate
        const id = link.hash.slice(1);
        if (!id) return;
        const target = document.getElementById(id);
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
        history.replaceState(null, '', link.hash);
        const links = $('#links');
        if (links) links.classList.remove('open');
    });
});

// Highlight the nav link of the section you are reading (home page)
if ($('#features')) {
    const spy = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (!en.isIntersecting) return;
            $$('.links a[data-sec]').forEach(a =>
                a.classList.toggle('active', a.dataset.sec === en.target.id));
        });
    }, { rootMargin: '-45% 0px -50% 0px' });

    ['home', 'features', 'how', 'about']
        .map(id => document.getElementById(id))
        .filter(Boolean)
        .forEach(el => spy.observe(el));
}

/* 2. FEATURES POP-UP (home) --------------------------------- */
if ($('#fgrid')) {
    const features = [
        ['🤖', 'AI Study Assistant', 'Get instant help with programming, DSA, concepts, and interview preparation.',
            ['Answers in seconds, any time', 'Explains errors step by step', 'Builds practice questions'], URLS.assistant],
        ['🎯', 'Daily Quests', 'Turn your study tasks into exciting daily missions.',
            ['Clear daily goals', 'XP reward on every quest', 'Less procrastination'], URLS.dashboard],
        ['⚡', 'XP & Levels', 'Earn XP every time you complete a task and level up.',
            ['Instant feedback on effort', 'Visible progress', 'Keeps you motivated'], URLS.dashboard],
        ['🔥', 'Study Streak', 'Maintain your daily learning streak.',
            ['Builds a daily habit', 'Rewards consistency', 'Easy to see at a glance'], URLS.dashboard],
        ['📊', 'Progress Tracking', 'See your level, XP and completed tasks at a glance.',
            ['Know exactly where you stand', 'Spot what is left to do', 'Plan smarter sessions'], URLS.dashboard],
        ['🏆', 'Achievements', 'Unlock badges and achievements for reaching milestones.',
            ['Celebrate small wins', 'Unlock new badges', 'Share your progress'], URLS.dashboard]
    ];
    $('#fgrid').innerHTML = features.map((f, i) => `
    <button class="glass fcard" data-i="${i}"><div class="ico">${f[0]}</div><h3>${f[1]}</h3><p>${f[2]}</p></button>`).join('');

    const modal = $('#modal');
    const closeModal = () => modal.classList.remove('active');

    $('#fgrid').addEventListener('click', e => {
        const card = e.target.closest('.fcard');
        if (!card) return;
        const f = features[card.dataset.i];
        $('#mc').innerHTML = `
      <div class="ico">${f[0]}</div><h2 style="font-size:24px">${f[1]}</h2>
      <p style="color:var(--m);margin-top:6px">${f[2]}</p>
      <ul>${f[3].map(b => `<li>${b}</li>`).join('')}</ul>
      <a class="btn p" href="${f[4]}">Try Feature</a>`;
        modal.classList.add('active');
    });

    $('#mx').onclick = closeModal;
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
    window.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

/* 3. AI CHAT (assistant page) ------------------------------- */
if ($('#msgs')) {
    const chat = $('#msgs');
    const history = [];                                   // [{ role, content }]
    let speakOn = false;
    let busy = false;

    const demoAnswers = {
        'hashmap': 'A HashMap stores key-value pairs. It hashes the key to find a bucket, so get() and put() are O(1) on average.',
        'plan': '4-week plan:\nWeek 1: arrays, strings, hashing\nWeek 2: linked lists, stacks, queues\nWeek 3: trees, recursion, binary search\nWeek 4: graphs, DP basics, revision',
        'error': 'Paste the error message and the code around it. I will explain what it means and how to fix it.',
        'interview': 'Start with a 60-second intro, prepare two project stories, and practise 10 core questions.'
    };
    const demoReply = prompt => {
        const key = Object.keys(demoAnswers).find(k => prompt.toLowerCase().includes(k));
        return key ? demoAnswers[key] : 'Good question. Tell me your subject and level, and I will explain it step by step.';
    };

    // Request  (JSON): { "message": "...", "history": [ {role, content}, ... ] }
    // Response (JSON): { "reply": "..." }  or  { "error": "..." }
    async function getAIResponse(prompt) {
        if (!URLS.chat) {
            toast('Chat endpoint not configured.');
            return demoReply(prompt);
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 30000);
        try {
            const res = await fetch(URLS.chat, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: prompt, history }),
                signal: controller.signal
            });
            if (res.status === 401) return 'Please log in again to use the assistant.';

            let data = {};
            try { data = await res.json(); } catch (_) { /* non-JSON error page */ }

            if (!res.ok || !data.reply) throw new Error(data.error || ('Server error ' + res.status));
            return data.reply;
        } catch (err) {
            console.warn('AI request failed:', err.message);
            toast('AI is unavailable right now. Showing a demo answer.');
            return demoReply(prompt);
        } finally {
            clearTimeout(timer);
        }
    }

    function addMessage(text, who) {                      // who: 'u' = you, 'a' = AI
        const div = document.createElement('div');
        div.className = 'm ' + who;
        div.textContent = text;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
        return div;
    }

    async function send(text) {
        text = (text || '').trim();
        if (!text || busy) return;
        busy = true;

        $('#in').value = '';
        const sug = $('#sug');
        if (sug) sug.style.display = 'none';

        addMessage(text, 'u');
        const loading = addMessage('', 'a');
        loading.innerHTML = '<div class="dots"><i></i><i></i><i></i></div>';

        try {
            const reply = await getAIResponse(text);
            history.push(
                { role: 'user', content: text },
                { role: 'assistant', content: reply }
            );
            loading.remove();
            addMessage(reply, 'a');
            if (speakOn && 'speechSynthesis' in window) {
                speechSynthesis.speak(new SpeechSynthesisUtterance(reply));
            }
        } finally {
            busy = false;
        }
    }

    function newChat() {
        history.length = 0;
        chat.innerHTML = '';
        addMessage('Hi, I am your LAKSHYA assistant. Choose a suggestion or type a question.', 'a');
        const sug = $('#sug');
        if (sug) sug.style.display = '';   // reset to CSS default, not forced value
    }

    $('#send').onclick = () => send($('#in').value);

    $('#in').addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            send(e.target.value);
        }
    });

    $('#sug').addEventListener('click', e => {
        const b = e.target.closest('button');
        if (b) send(b.textContent);
    });

    $('#caps').addEventListener('click', e => {
        const c = e.target.closest('.fcard');
        if (c) send(c.dataset.p);
    });

    $$('.hi').forEach(b => b.onclick = () => send(b.dataset.p));
    $('#nc').onclick = newChat;
    newChat();

    /* voice */
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let listener = null;

    $('#mic').onclick = () => {
        if (!Recognition) return toast('Voice input is not supported in this browser');
        if (listener) return listener.stop();

        listener = new Recognition();
        listener.lang = 'en-US';
        $('#mic').classList.add('on');

        listener.onresult = e => {
            const t = e.results && e.results[0] && e.results[0][0] && e.results[0][0].transcript;
            if (t) send(t);
        };
        listener.onerror = () => toast('Could not hear you. Check mic permission.');
        listener.onend = () => {
            listener = null;
            $('#mic').classList.remove('on');
        };

        listener.start();
    };

    $('#spk').onclick = function () {
        speakOn = !speakOn;
        this.textContent = speakOn ? '🔊' : '🔈';
        if (!speakOn && 'speechSynthesis' in window) speechSynthesis.cancel();
        toast(speakOn ? 'Replies will be read aloud' : 'Read aloud off');
    };
}

/* 4. EXTRAS ------------------------------------------------- */
const floaters = [...$$('.fc')];                        // floating hero cards
if (floaters.length) {
    (function float(t) {
        floaters.forEach((c, i) => {
            const a = +c.dataset.f;
            c.style.transform =
                `translate(${Math.sin(t / 1800 + i) * a * .6}px, ${Math.sin(t / 1200 + i * 1.7) * a}px)`;
        });
        requestAnimationFrame(float);
    })(0);
}

const topBtn = $('#top');
const navEl = $('nav');
if (navEl && topBtn) {
    window.addEventListener('scroll', () => {
        navEl.classList.toggle('scrolled', scrollY > 20);
        topBtn.classList.toggle('show', scrollY > 600);
    }, { passive: true });

    topBtn.onclick = () => scrollTo({ top: 0, behavior: 'smooth' });
}