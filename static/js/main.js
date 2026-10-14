// Theme Toggle Functions
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggleIcons();
}

function updateThemeToggleIcons() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const toggleBtns = document.querySelectorAll('.theme-toggle-btn');
    toggleBtns.forEach(btn => {
        const iconEl = btn.querySelector('.theme-toggle-icon');
        const textEl = btn.querySelector('.theme-toggle-text');
        if (isDark) {
            if (iconEl) iconEl.textContent = '☀️';
            if (textEl) textEl.textContent = 'Light Mode';
            btn.setAttribute('title', 'Switch to Light Mode');
            btn.classList.add('is-dark');
        } else {
            if (iconEl) iconEl.textContent = '🌙';
            if (textEl) textEl.textContent = 'Dark Mode';
            btn.setAttribute('title', 'Switch to Dark Mode');
            btn.classList.remove('is-dark');
        }
    });
}

// Dynamic Header Height Measurement for Hero Section
function updateHeaderHeight() {
    const navbar = document.querySelector('.navbar-header');
    const ticker = document.querySelector('.offers-ticker-container');
    let totalHeight = 0;
    if (navbar) {
        totalHeight += navbar.getBoundingClientRect().height;
    }
    if (ticker && ticker.offsetParent !== null) {
        totalHeight += ticker.getBoundingClientRect().height;
    }
    if (totalHeight > 0) {
        document.documentElement.style.setProperty('--header-height', `${Math.round(totalHeight)}px`);
    }
}

// Measure immediately and register responsive listeners
updateHeaderHeight();
window.addEventListener('resize', updateHeaderHeight);
window.addEventListener('orientationchange', updateHeaderHeight);

if (window.ResizeObserver) {
    const headerObserver = new ResizeObserver(() => {
        updateHeaderHeight();
    });
    const navbarEl = document.querySelector('.navbar-header');
    const tickerEl = document.querySelector('.offers-ticker-container');
    if (navbarEl) headerObserver.observe(navbarEl);
    if (tickerEl) headerObserver.observe(tickerEl);
}

document.addEventListener('DOMContentLoaded', () => {
    updateThemeToggleIcons();
    updateHeaderHeight();

    // 1. Mobile Menu Toggle
    const mobileToggle = document.getElementById('mobile-toggle');
    const navMenu = document.getElementById('nav-menu');

    if (mobileToggle && navMenu) {
        mobileToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            navMenu.classList.toggle('active');
            mobileToggle.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
            if (!navMenu.contains(e.target) && !mobileToggle.contains(e.target)) {
                navMenu.classList.remove('active');
                mobileToggle.classList.remove('active');
            }
        });

        const navLinks = navMenu.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                navMenu.classList.remove('active');
                mobileToggle.classList.remove('active');
            });
        });
    }

    // 2. Client-side Course Filtering (Progressive Enhancement)
    const courseSearchInput = document.getElementById('course-search-input');
    const courseCards = document.querySelectorAll('.course-card');

    if (courseSearchInput && courseCards.length > 0) {
        courseSearchInput.addEventListener('keyup', (e) => {
            const query = e.target.value.toLowerCase().trim();
            courseCards.forEach(card => {
                const title = card.getAttribute('data-course-name') || card.querySelector('.course-title')?.textContent || '';
                const description = card.querySelector('.course-description')?.textContent || '';
                if (title.toLowerCase().includes(query) || description.toLowerCase().includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }

    // 3. Date Input Year Constraint (Ensure max 4 digits for YEAR: 1000–9999)
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.hasAttribute('min')) input.setAttribute('min', '1000-01-01');
        if (!input.hasAttribute('max')) input.setAttribute('max', '9999-12-31');

        input.addEventListener('input', () => {
            if (input.value) {
                const parts = input.value.split('-');
                if (parts[0] && parts[0].length > 4) {
                    parts[0] = parts[0].slice(0, 4);
                    input.value = parts.join('-');
                }
            }
        });
    });

    // 4. Client-side Form Validation Helper
    const forms = document.querySelectorAll('form[data-validate="true"]');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            let valid = true;
            const requiredInputs = form.querySelectorAll('[required]');
            
            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    valid = false;
                    input.classList.add('is-invalid');
                } else {
                    input.classList.remove('is-invalid');
                }
            });

            // Ensure date inputs have valid 4-digit years
            const formDateInputs = form.querySelectorAll('input[type="date"]');
            formDateInputs.forEach(input => {
                if (input.value) {
                    const yearStr = input.value.split('-')[0];
                    const year = parseInt(yearStr, 10);
                    if (isNaN(year) || yearStr.length !== 4 || year < 1000 || year > 9999) {
                        valid = false;
                        input.classList.add('is-invalid');
                    }
                }
            });

            const password = form.querySelector('input[name="password"]');
            const confirmPassword = form.querySelector('input[name="confirm_password"]');
            if (password && confirmPassword && password.value !== confirmPassword.value) {
                valid = false;
                confirmPassword.classList.add('is-invalid');
                let errDiv = confirmPassword.parentElement.querySelector('.form-error');
                if (!errDiv) {
                    errDiv = document.createElement('div');
                    errDiv.className = 'form-error';
                    errDiv.style.color = 'var(--danger, #ef4444)';
                    errDiv.style.fontSize = '0.85rem';
                    errDiv.style.marginTop = '0.4rem';
                    confirmPassword.parentElement.appendChild(errDiv);
                }
                errDiv.textContent = 'Passwords do not match.';
            }

            if (!valid) {
                e.preventDefault();
            }
        });
    });
});
