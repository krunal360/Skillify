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

    // ===== Profile Picture Preview =====
    const fileInput = document.getElementById('profilePictureInput');
    const preview = document.getElementById('profilePreview');
    const removeFlag = document.getElementById('removePictureFlag');

    if (fileInput) {
        fileInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                if (file.size > 5 * 1024 * 1024) {
                    alert('File too large! Maximum size is 5MB.');
                    this.value = '';
                    return;
                }
                if (!file.type.match(/^image\/(jpeg|png|gif|webp)$/)) {
                    alert('Invalid file type. Please upload JPG, PNG, GIF, or WebP.');
                    this.value = '';
                    return;
                }
                const reader = new FileReader();
                reader.onload = function (ev) { preview.src = ev.target.result; };
                reader.readAsDataURL(file);
                removeFlag.value = '0';

                let removeBtn = document.getElementById('removePicBtn');
                if (!removeBtn) {
                    removeBtn = document.createElement('button');
                    removeBtn.type = 'button';
                    removeBtn.className = 'remove-pic-btn';
                    removeBtn.id = 'removePicBtn';
                    removeBtn.title = 'Remove photo';
                    removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';
                    preview.parentElement.appendChild(removeBtn);
                    attachRemoveHandler(removeBtn);
                }
            }
        });
    }

    function attachRemoveHandler(btn) {
        btn.addEventListener('click', function () {
            removeFlag.value = '1';
            fileInput.value = '';
            preview.src = "https://ui-avatars.com/api/?name=User&background=4ECDC4&color=fff&size=150";
            this.remove();
        });
    }

    const removePicBtn = document.getElementById('removePicBtn');
    if (removePicBtn) attachRemoveHandler(removePicBtn);

    // ===== Demo Video Preview =====
    const videoInput = document.getElementById('demo_video');
    const previewContainer = document.getElementById('videoPreviewContainer');
    const previewFrame = document.getElementById('videoPreviewFrame');
    const clearVideoBtn = document.getElementById('clearVideoBtn');

    function getEmbedUrl(url) {
        if (!url) return '';
        let match = url.match(/youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)/);
        if (match) return 'https://www.youtube.com/embed/' + match[1];
        match = url.match(/youtu\.be\/([a-zA-Z0-9_-]+)/);
        if (match) return 'https://www.youtube.com/embed/' + match[1];
        if (url.includes('youtube.com/embed/')) return url;
        match = url.match(/vimeo\.com\/(\d+)/);
        if (match) return 'https://player.vimeo.com/video/' + match[1];
        return '';
    }

    if (videoInput) {
        let debounceTimer;
        videoInput.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                const embedUrl = getEmbedUrl(videoInput.value.trim());
                if (embedUrl) {
                    previewFrame.src = embedUrl;
                    previewContainer.style.display = 'block';
                } else {
                    previewFrame.src = '';
                    previewContainer.style.display = 'none';
                }
            }, 600);
        });
    }

    if (clearVideoBtn) {
        clearVideoBtn.addEventListener('click', function () {
            videoInput.value = '';
            previewFrame.src = '';
            previewContainer.style.display = 'none';
            this.parentElement.style.display = 'none';
        });
    }

    // ===== Auto Dismiss Alerts =====
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

});