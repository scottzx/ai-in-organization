const script = document.querySelector('script[data-site]');
const base = new URL('../', script.src);
const dialog = document.querySelector('#search-dialog');
const input = document.querySelector('#search-input');
const results = document.querySelector('#search-results');
let searchData;
let queryVersion = 0;

document.querySelectorAll('[data-search]').forEach(button => button.addEventListener('click', () => {
  dialog.showModal();
  input.focus();
}));
document.querySelector('#search-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
    event.preventDefault();
    if (!dialog.open) dialog.showModal();
    input.focus();
  }
});
input.addEventListener('input', async () => {
  const version = ++queryVersion;
  const query = input.value.trim().toLowerCase();
  if (!query) { results.textContent = '输入关键词，搜索报告、案例与资料索引。'; return; }
  try {
    if (!searchData) {
      const response = await fetch(new URL('search-index.json', base));
      if (!response.ok) throw new Error('Search unavailable');
      searchData = await response.json();
    }
    if (version !== queryVersion) return;
    const words = query.split(/\s+/);
    const matches = searchData.filter(item => words.every(word => (item.title + item.text).toLowerCase().includes(word)))
      .sort((a, b) => Number(b.title.toLowerCase().includes(query)) - Number(a.title.toLowerCase().includes(query)));
    results.replaceChildren();
    const count = document.createElement('p');
    count.className = 'search-count';
    count.textContent = `找到 ${matches.length} 篇内容${matches.length > 40 ? '，显示前 40 篇' : ''}`;
    results.append(count);
    for (const item of matches.slice(0, 40)) {
      const link = document.createElement('a');
      link.className = 'search-result';
      link.href = new URL(item.url, base);
      const title = document.createElement('strong');
      title.textContent = item.title;
      const excerpt = document.createElement('span');
      const position = Math.max(0, item.text.toLowerCase().indexOf(words[0]) - 38);
      excerpt.textContent = (position ? '…' : '') + item.text.slice(position, position + 150) + '…';
      link.append(title, excerpt);
      results.append(link);
    }
  } catch {
    if (version === queryVersion) results.textContent = '搜索暂时无法加载，请稍后重试。也可以通过目录阅读。';
  }
});

const menu = document.querySelector('#menu-toggle');
const sidebar = document.querySelector('#sidebar');
const sidebarScroll = document.querySelector('.sidebar-scroll');
const currentPage = sidebarScroll.querySelector('[aria-current="page"]');
const revealCurrentPage = () => {
  if (!currentPage) return;
  const item = currentPage.getBoundingClientRect();
  const viewport = sidebarScroll.getBoundingClientRect();
  if (item.top < viewport.top || item.bottom > viewport.bottom) {
    sidebarScroll.scrollTop += item.top - viewport.top - viewport.height / 3;
  }
};
revealCurrentPage();
menu.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  sidebar.classList.toggle('is-open', open);
  if (open) revealCurrentPage();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
    menu.setAttribute('aria-expanded', 'false');
    sidebar.classList.remove('is-open');
    menu.focus();
  }
});
document.querySelector('#copy-link').addEventListener('click', async event => {
  const button = event.currentTarget;
  try {
    await navigator.clipboard.writeText(location.href);
    button.textContent = '链接已复制';
  } catch { button.textContent = '请复制浏览器地址分享'; }
  setTimeout(() => { button.textContent = '分享本页 ↗'; }, 2500);
});
document.querySelectorAll('.prose table').forEach(table => {
  const wrapper = document.createElement('div');
  wrapper.className = 'table-scroll';
  wrapper.tabIndex = 0;
  wrapper.setAttribute('role', 'region');
  wrapper.setAttribute('aria-label', '表格，可左右滚动');
  table.before(wrapper);
  wrapper.append(table);
});
const headings = document.querySelectorAll('.prose h2[id], .prose h3[id]');
const tocLinks = [...document.querySelectorAll('.toc a')];
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      tocLinks.forEach(link => link.classList.toggle('active', decodeURIComponent(link.hash.slice(1)) === entry.target.id));
    }
  }, { rootMargin: '-10% 0px -75% 0px' });
  headings.forEach(heading => observer.observe(heading));
}
