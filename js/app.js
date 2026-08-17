/* Ive's Library — app.js
   Renders the library from window.LIBRARY (data/books.js): hero wall, stats,
   collection cards, shelves, search/filter, scroll reveals and the book dialog. */
(function () {
  'use strict';
  const L = window.LIBRARY;
  if (!L) return;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fold = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const fmt = (n) => new Intl.NumberFormat('en-US').format(n);
  const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV'];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const books = L.books;
  const collections = L.collections.filter((c) => c.count > 0);
  const byId = new Map(books.map((b) => [b.id, b]));
  const colByKey = new Map(collections.map((c) => [c.key, c]));
  collections.forEach((c, i) => { c.numeral = ROMAN[i]; c.books = books.filter((b) => b.tags.includes(c.key)); });

  const langLabel = (l) => (l === 'Spanish' ? 'Español' : l === 'English' ? 'English' : l || '');
  const coverSrc = (b, big) => (big && b.coverBig) ? b.coverBig : b.cover;
  const searchIndex = new Map(books.map((b) => [b.id, fold([b.title, b.subtitle, b.author, b.publisher, b.isbn, ...b.tags.map((k) => colByKey.get(k)?.name || ''), b.summary || ''].join(' | '))]));

  /* ------------------------------------------------------------------ hero */
  function renderHero() {
    const wall = $('#heroWall');
    const withBig = books.filter((b) => b.coverBig);
    const others = books.filter((b) => !b.coverBig);
    const small = window.innerWidth < 720;
    const ROWS = small ? 4 : 5, PER_ROW = small ? 14 : 18;
    const need = ROWS * PER_ROW;
    // deterministic spread across the whole library (so every collection shows up on the wall)
    const pool = [];
    const src = withBig.length >= need ? withBig : [...withBig, ...others];
    const stride = Math.max(1, Math.floor(src.length / need));
    for (let i = 0, k = 0; pool.length < need && k < src.length; k++, i = (i + stride) % src.length) {
      const b = src[(i + Math.floor(k / src.length)) % src.length];
      if (!pool.includes(b)) pool.push(b);
    }
    for (let i = 0; pool.length < need && i < src.length; i++) if (!pool.includes(src[i])) pool.push(src[i]);
    const rows = Array.from({ length: ROWS }, () => []);
    pool.forEach((b, i) => rows[i % ROWS].push(b));
    const durs = [170, 210, 150, 230, 180];
    wall.innerHTML = rows.map((r, i) => {
      const imgs = r.map((b) => `<img src="${esc(coverSrc(b, true))}" alt="" loading="eager" decoding="async" />`).join('');
      return `<div class="wall-row ${i % 2 ? 'reverse' : ''}" style="--dur:${durs[i]}s">${imgs}${imgs}</div>`;
    }).join('');

    const m = L.meta;
    const langs = Object.keys(m.languages).filter((k) => k === 'English' || k === 'Spanish');
    $('#heroSub').innerHTML = `A home for <b>${fmt(m.totalEntries)} books</b> across <b>${collections.length} collections</b> — saints and popes, Our Lady, prayer, catechism, Catholic authors and stories for the little ones, in ${langs.length > 1 ? 'English and Spanish' : langs[0]}.`;
    $('#footerSub').textContent = `${fmt(m.totalEntries)} books · ${collections.length} collections · catalogued with BookBuddy, ${m.catalogued}`;
  }

  /* ----------------------------------------------------------------- stats */
  function renderStats() {
    const m = L.meta;
    const items = [
      { n: m.totalEntries, label: 'Books' },
      { n: collections.length, label: 'Collections' },
      { n: Math.round(m.pages / 1000), suffix: 'k', label: 'Pages to read' },
      { n: Object.keys(m.languages).filter((k) => m.languages[k] > 1).length, label: 'Languages' },
    ];
    $('#statGrid').innerHTML = items.map((s, i) => `<li class="stat" style="--d:${i * 90}ms"><b data-count="${s.n}" data-suffix="${s.suffix || ''}">0${s.suffix ? `<small>${s.suffix}</small>` : ''}</b><span>${s.label}</span></li>`).join('');
    const top = m.topAuthors[0];
    const spanish = m.languages.Spanish || 0, english = m.languages.English || 0;
    const oldest = books.filter((b) => b.year === m.oldestYear)[0];
    $('#statsNote').innerHTML = `The most-collected author is <b>${esc(top.name)}</b> with ${top.count} titles · <b>${english}</b> in English, <b>${spanish}</b> in Spanish` +
      (oldest ? ` · the oldest edition on the shelves is from <b>${m.oldestYear}</b>` : '') + `.`;
  }

  /* ----------------------------------------------------- collections + nav */
  function renderCollections() {
    $('#collectionGrid').innerHTML = collections.map((c, i) => {
      const fan = c.books.filter((b) => b.coverBig).concat(c.books.filter((b) => !b.coverBig)).slice(0, 3);
      return `<a class="ccard" href="#c-${c.key}" data-key="${c.key}" style="--d:${(i % 4) * 80}ms">
        <div class="num">${c.numeral}</div>
        <h3>${esc(c.name)}</h3>
        <div class="count">${c.count} ${c.count === 1 ? 'book' : 'books'}</div>
        <p class="blurb">${esc(c.blurb)}</p>
        <span class="arrow">Open shelf →</span>
        <div class="fan" aria-hidden="true">${fan.map((b) => `<img src="${esc(coverSrc(b, false))}" alt="" loading="lazy" decoding="async" />`).join('')}</div>
      </a>`;
    }).join('');
    const links = collections.map((c) => `<a href="#c-${c.key}" data-key="${c.key}">${esc(c.name)}<small>${c.count}</small></a>`).join('');
    $('#navCollections').innerHTML = links;
    $('#navSheet').innerHTML = links;
  }

  /* --------------------------------------------------------------- shelves */
  function bookCard(b, i) {
    return `<button class="book" type="button" data-id="${b.id}" style="--d:${(i % 8) * 45}ms" aria-label="${esc(b.title)}${b.author ? ' by ' + esc(b.author) : ''}">
      <span class="cover-wrap"><span class="book-3d">
        <img src="${esc(coverSrc(b, false))}" alt="" loading="lazy" decoding="async" width="${b.coverW}" height="${b.coverH}" />
        ${b.copies > 1 ? `<span class="badge copies">×${b.copies}</span>` : ''}
        ${b.video ? `<span class="badge video"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>Video</span>` : ''}
      </span></span>
      <span class="cap"><span class="t">${esc(b.title)}</span><span class="a">${esc(b.author || b.publisher || '')}</span></span>
    </button>`;
  }

  function renderShelves() {
    $('#shelves').innerHTML = collections.map((c) => {
      const spanish = c.books.filter((b) => b.language === 'Spanish').length;
      const vids = c.books.filter((b) => b.video).length;
      return `<section class="shelf-section" id="c-${c.key}" data-key="${c.key}" aria-labelledby="h-${c.key}">
        <div class="container">
          <header class="shelf-head reveal">
            <div>
              <div class="num">${c.numeral}</div>
              <h2 id="h-${c.key}">${esc(c.name)} <small class="shelf-count" data-total="${c.count}">${c.count} books</small></h2>
              <p class="blurb">${esc(c.blurb)}</p>
            </div>
            <p class="shelf-meta">${spanish ? `<b>${spanish}</b> en español` : ''}${spanish && vids ? ' · ' : ''}${vids ? `<b>${vids}</b> with video` : ''}</p>
          </header>
          <div class="shelf">${c.books.map(bookCard).join('')}</div>
        </div>
      </section>`;
    }).join('');
  }

  /* --------------------------------------------------------- reveal / obs */
  let revealObs;
  function setupReveal() {
    if (reduceMotion) { $$('.reveal, .book, .stat, .ccard').forEach((el) => el.classList.add('in')); countUpAll(); return; }
    revealObs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        e.target.classList.add('in');
        if (e.target.classList.contains('stat')) countUp(e.target.querySelector('b'));
        revealObs.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    $$('.reveal, .book, .stat, .ccard').forEach((el) => revealObs.observe(el));
  }
  function countUp(el) {
    if (!el || el.dataset.done) return;
    el.dataset.done = '1';
    const target = +el.dataset.count, suffix = el.dataset.suffix || '';
    const t0 = performance.now(), dur = 1500;
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.innerHTML = fmt(Math.round(target * e)) + (suffix ? `<small>${suffix}</small>` : '');
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  function countUpAll() { $$('.stat b').forEach((b) => { b.innerHTML = fmt(+b.dataset.count) + (b.dataset.suffix ? `<small>${b.dataset.suffix}</small>` : ''); }); }

  /* -------------------------------------------------------------- filters */
  const state = { q: '', lang: 'all', video: false };
  const searchInput = $('#searchInput');
  const searchClear = $('#searchClear');
  let filterTimer;

  function matches(b) {
    if (state.lang !== 'all' && b.language !== state.lang) return false;
    if (state.video && !b.video) return false;
    if (state.q) {
      const hay = searchIndex.get(b.id);
      return state.q.split(/\s+/).every((w) => hay.includes(w));
    }
    return true;
  }
  function applyFilters() {
    const active = state.q || state.lang !== 'all' || state.video;
    let total = 0;
    collections.forEach((c) => {
      const sec = $(`#c-${c.key}`);
      let n = 0;
      c.books.forEach((b) => {
        const ok = matches(b);
        const el = sec.querySelector(`.book[data-id="${b.id}"]`);
        el.hidden = !ok;
        if (ok) { n++; if (active) el.classList.add('in'); }
      });
      total += n;
      sec.hidden = n === 0;
      const cnt = sec.querySelector('.shelf-count');
      cnt.textContent = active ? `${n} of ${c.count}` : `${c.count} books`;
    });
    $('#emptyState').hidden = total !== 0;
    $('#resultCount').innerHTML = active ? `<b>${total}</b> ${total === 1 ? 'book' : 'books'} match` : '';
    searchClear.hidden = !state.q;
    if (active) { const fb = $('#filterbar'); const y = fb.getBoundingClientRect().top; if (y < 0 || y > window.innerHeight * .6) { /* keep the shelves in view when narrowing */ } }
  }
  searchInput.addEventListener('input', () => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => { state.q = fold(searchInput.value.trim()); applyFilters(); if (state.q) scrollToShelvesIfAbove(); }, 140);
  });
  searchInput.addEventListener('keydown', (e) => { if (e.key === 'Escape') { searchInput.value = ''; state.q = ''; applyFilters(); searchInput.blur(); } });
  searchClear.addEventListener('click', () => { searchInput.value = ''; state.q = ''; applyFilters(); searchInput.focus(); });
  $('#emptyReset').addEventListener('click', () => { searchInput.value = ''; state.q = ''; state.lang = 'all'; state.video = false; syncChips(); applyFilters(); });
  $$('.chip[data-lang]').forEach((ch) => ch.addEventListener('click', () => { state.lang = ch.dataset.lang; syncChips(); applyFilters(); }));
  $('.chip-video').addEventListener('click', () => { state.video = !state.video; syncChips(); applyFilters(); });
  function syncChips() {
    $$('.chip[data-lang]').forEach((ch) => ch.classList.toggle('is-active', ch.dataset.lang === state.lang));
    $('.chip-video').setAttribute('aria-pressed', String(state.video));
  }
  function scrollToShelvesIfAbove() {
    const fb = $('#filterbar');
    if (fb.getBoundingClientRect().top > window.innerHeight * 0.5) {
      const top = fb.getBoundingClientRect().top + window.scrollY - parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) ;
      window.scrollTo({ top, behavior: reduceMotion ? 'auto' : 'smooth' });
    }
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== searchInput && !$('#bookDialog').open) { e.preventDefault(); searchInput.focus(); }
  });

  /* ------------------------------------------------------- nav behaviours */
  const nav = $('#nav'), toTop = $('#toTop'), progressBar = $('#progressBar'), heroWall = $('#heroWall');
  const menuBtn = $('#menuBtn'), navSheet = $('#navSheet');
  let ticking = false;
  function onScroll() {
    if (ticking) return; ticking = true;
    requestAnimationFrame(() => {
      const y = window.scrollY;
      nav.classList.toggle('is-solid', y > 40);
      toTop.classList.toggle('show', y > 900);
      const h = document.documentElement.scrollHeight - window.innerHeight;
      progressBar.style.width = (h > 0 ? (y / h) * 100 : 0) + '%';
      if (!reduceMotion && y < window.innerHeight * 1.2) heroWall.style.transform = `rotate(-4deg) translateY(${y * 0.28}px)`;
      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' }));
  menuBtn.addEventListener('click', () => { const open = navSheet.hidden; navSheet.hidden = !open; menuBtn.setAttribute('aria-expanded', String(open)); });
  navSheet.addEventListener('click', (e) => { if (e.target.closest('a')) { navSheet.hidden = true; menuBtn.setAttribute('aria-expanded', 'false'); } });
  document.addEventListener('click', (e) => { if (!navSheet.hidden && !e.target.closest('.nav')) { navSheet.hidden = true; menuBtn.setAttribute('aria-expanded', 'false'); } });

  // highlight current collection in nav
  const secObs = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const key = e.target.dataset.key;
      $$('#navCollections a').forEach((a) => a.classList.toggle('is-current', a.dataset.key === key));
      const cur = $(`#navCollections a[data-key="${key}"]`);
      if (cur) cur.scrollIntoView({ block: 'nearest', inline: 'center', behavior: reduceMotion ? 'auto' : 'smooth' });
    });
  }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

  /* --------------------------------------------------------------- dialog */
  const dlg = $('#bookDialog');
  const dlgVideo = $('#dlgVideo');
  let current = null;
  function visibleBooks() { return $$('.book:not([hidden])').map((el) => +el.dataset.id); }

  function openBook(id, { push = true } = {}) {
    const b = byId.get(id); if (!b) return;
    current = id;
    const big = coverSrc(b, true);
    const img = $('#dlgCover'); img.src = big; img.alt = `Cover of ${b.title}`;
    $('#dlgAmbient').style.backgroundImage = `url("${big}")`;
    $('#dlgTags').innerHTML = b.tags.map((k) => { const c = colByKey.get(k); return c ? `<a href="#c-${c.key}" data-close>${esc(c.name)}</a>` : ''; }).join('');
    $('#dlgTitle').textContent = b.title;
    $('#dlgSubtitle').textContent = b.subtitle || '';
    $('#dlgAuthor').innerHTML = b.author ? `<span>by</span> ${esc(b.author)}` : `<span>Author not listed</span>`;
    const meta = [];
    if (b.language) meta.push(['Language', langLabel(b.language) + (b.languageInferred ? '' : '')]);
    if (b.publisher || b.year) meta.push(['Published', [b.publisher, b.year].filter(Boolean).join(', ')]);
    if (b.pages) meta.push(['Pages', fmt(b.pages)]);
    if (b.genre) meta.push(['Genre', b.genre]);
    if (b.isbn) meta.push(['ISBN', b.isbn]);
    if (b.copies > 1) meta.push(['Copies', `${b.copies} on the shelf`]);
    $('#dlgMeta').innerHTML = meta.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('');

    const sum = $('#dlgSummary');
    const old = $('.dlg-more', sum.parentElement); if (old) old.remove();
    if (b.summary) {
      const paras = b.summary.split(/\n{2,}|\n/).map((p) => p.trim()).filter(Boolean);
      sum.innerHTML = paras.map((p) => `<p>${esc(p)}</p>`).join('');
      sum.setAttribute('lang', b.summaryLang || 'en');
      sum.classList.remove('is-clamped');
      if (b.summary.length > 900) {
        sum.classList.add('is-clamped');
        const more = document.createElement('button'); more.className = 'dlg-more'; more.type = 'button'; more.textContent = 'Read more';
        more.addEventListener('click', () => { sum.classList.remove('is-clamped'); more.remove(); });
        sum.after(more);
      }
      $('#dlgSource').textContent = b.summarySource === 'publisher' ? 'Publisher’s description' : 'Shelf note written for Ive’s Library';
    } else {
      sum.innerHTML = `<p class="none">No summary yet for this one — but the cover speaks for itself.</p>`;
      sum.classList.remove('is-clamped');
      $('#dlgSource').textContent = '';
    }

    // video
    dlgVideo.innerHTML = '';
    if (b.video) {
      $('#dlgVideoSec').hidden = false;
      const ifr = document.createElement('iframe');
      ifr.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(b.video.id)}?rel=0&modestbranding=1&color=white`;
      ifr.title = b.video.title || 'Video'; ifr.loading = 'lazy'; ifr.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'; ifr.allowFullscreen = true; ifr.referrerPolicy = 'strict-origin-when-cross-origin';
      dlgVideo.appendChild(ifr);
      $('#dlgVideoCap').innerHTML = `<b>${esc(b.video.title)}</b>${b.video.channel ? ` · ${esc(b.video.channel)}` : ''}`;
    } else {
      $('#dlgVideoSec').hidden = true;
    }

    // links
    const q = encodeURIComponent(`${b.title} ${b.author || ''}`.trim());
    const links = [
      [`https://www.youtube.com/results?search_query=${q}`, 'YouTube', '<path d="M8 5v14l11-7z"/>'],
      [b.googleId ? `https://books.google.com/books?id=${encodeURIComponent(b.googleId)}` : `https://www.google.com/search?tbm=bks&q=${q}`, 'Google Books', '<path d="M4 4h16v16H4z M8 8h8v2H8z M8 12h8v2H8z"/>'],
      [`https://www.amazon.com/s?k=${b.isbn ? b.isbn : q}`, 'Find a copy', '<path d="M12 2 4 6v6c0 5 3.4 9.4 8 10 4.6-.6 8-5 8-10V6l-8-4z"/>'],
    ];
    $('#dlgLinks').innerHTML = links.map(([href, label, icon]) => `<a href="${href}" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true">${icon}</svg>${label}</a>`).join('');

    // prev/next
    const list = visibleBooks(); const idx = list.indexOf(id);
    $('#dlgPrev').disabled = idx <= 0; $('#dlgNext').disabled = idx === -1 || idx >= list.length - 1;
    $('#dlgPrev').dataset.target = idx > 0 ? list[idx - 1] : ''; $('#dlgNext').dataset.target = idx < list.length - 1 ? list[idx + 1] : '';

    if (!dlg.open) { dlg.showModal(); document.body.classList.add('dialog-open'); }
    $('.dlg-scroll', dlg).scrollTop = 0;
    if (push) history.replaceState(null, '', `#book-${id}`);
    $('#dlgClose').focus({ preventScroll: true });
  }
  function closeBook() {
    if (!dlg.open) return;
    dlg.close();
  }
  dlg.addEventListener('close', () => {
    document.body.classList.remove('dialog-open');
    dlgVideo.innerHTML = '';
    if (location.hash.startsWith('#book-')) history.replaceState(null, '', location.pathname + location.search);
    if (current) { const el = $(`.book[data-id="${current}"]`); if (el) { el.focus({ preventScroll: true }); } }
  });
  dlg.addEventListener('click', (e) => {
    if (e.target === dlg) { closeBook(); return; }
    const t = e.target.closest('[data-close]'); if (t) { closeBook(); }
  });
  $('#dlgClose').addEventListener('click', closeBook);
  $('#dlgPrev').addEventListener('click', (e) => { const t = +e.currentTarget.dataset.target; if (t) openBook(t); });
  $('#dlgNext').addEventListener('click', (e) => { const t = +e.currentTarget.dataset.target; if (t) openBook(t); });
  dlg.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft' && !$('#dlgPrev').disabled) { e.preventDefault(); openBook(+$('#dlgPrev').dataset.target); }
    if (e.key === 'ArrowRight' && !$('#dlgNext').disabled) { e.preventDefault(); openBook(+$('#dlgNext').dataset.target); }
  });
  $('#shelves').addEventListener('click', (e) => { const btn = e.target.closest('.book'); if (btn) openBook(+btn.dataset.id); });

  /* ------------------------------------------------------------ deep link */
  function handleHash() {
    const m = location.hash.match(/^#book-(\d+)$/);
    if (m) {
      const id = +m[1]; const el = $(`.book[data-id="${id}"]`);
      if (el) { el.classList.add('in'); el.scrollIntoView({ block: 'center' }); el.classList.add('is-flash'); }
      openBook(id, { push: false });
    }
  }

  /* ----------------------------------------------------------------- init */
  renderHero();
  renderStats();
  renderCollections();
  renderShelves();
  setupReveal();
  $$('.shelf-section').forEach((s) => secObs.observe(s));
  applyFilters();
  requestAnimationFrame(handleHash);
  window.addEventListener('hashchange', () => { if (/^#book-/.test(location.hash)) handleHash(); });
})();
