document.addEventListener('DOMContentLoaded', function () {

    // ===== Theme Toggle =====
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const savedTheme = localStorage.getItem('skillify_theme') || 'light';
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            themeToggle.innerHTML = '<i class="bi bi-sun-fill"></i>';
        }
        themeToggle.addEventListener('click', function () {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            if (isDark) {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('skillify_theme', 'light');
                this.innerHTML = '<i class="bi bi-moon-stars-fill"></i>';
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('skillify_theme', 'dark');
                this.innerHTML = '<i class="bi bi-sun-fill"></i>';
            }
        });
    }

    // ===== Filter Toggle =====
    const filterToggleBtn = document.getElementById('filterToggleBtn');
    const filterPanel = document.getElementById('filterPanel');
    const filterChevron = document.getElementById('filterChevron');
    const filterCountBadge = document.getElementById('filterCountBadge');

    // Count active filters from URL
    const urlParams = new URLSearchParams(window.location.search);
    const filterKeys = ['skill', 'max_credits', 'min_rating', 'session_type', 'availability', 'sort_by'];
    const activeFilters = filterKeys.filter(key => urlParams.get(key) && urlParams.get(key) !== '');
    const activeCount = activeFilters.length;

    // Show badge with count if filters active
    if (filterCountBadge) {
        if (activeCount > 0) {
            filterCountBadge.textContent = activeCount;
            filterCountBadge.style.display = 'inline-block';
        } else {
            filterCountBadge.style.display = 'none';
        }
    }

    // Auto open panel if filters are active
    if (activeCount > 0 && filterPanel) {
        filterPanel.style.display = 'block';
        if (filterToggleBtn) filterToggleBtn.classList.add('active');
        if (filterChevron) filterChevron.classList.add('rotated');
    }

    // Toggle on button click
    if (filterToggleBtn && filterPanel) {
        filterToggleBtn.addEventListener('click', function () {
            const isOpen = filterPanel.style.display === 'block';
            if (isOpen) {
                filterPanel.style.display = 'none';
                filterToggleBtn.classList.remove('active');
                if (filterChevron) filterChevron.classList.remove('rotated');
            } else {
                filterPanel.style.display = 'block';
                filterToggleBtn.classList.add('active');
                if (filterChevron) filterChevron.classList.add('rotated');
            }
        });
    }

    // ===== Auto Dismiss Alerts =====
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ===== Navbar Unread Count =====
    function updateUnreadCount() {
        fetch('/messages/unread-count/')
            .then(r => r.json())
            .then(data => {
                const badge = document.getElementById('navUnreadCount');
                if (badge) {
                    if (data.count > 0) {
                        badge.textContent = data.count;
                        badge.style.display = 'inline';
                    } else {
                        badge.style.display = 'none';
                    }
                }
            }).catch(() => {});
    }
    updateUnreadCount();
    setInterval(updateUnreadCount, 10000);

});