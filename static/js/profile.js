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

    // ===== Auto Dismiss Alerts =====
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ===== Animate Rating Bars =====
    setTimeout(function () {
        document.querySelectorAll('.rating-fill').forEach(function (bar) {
            bar.style.transition = 'width 0.8s ease';
        });
    }, 300);

});