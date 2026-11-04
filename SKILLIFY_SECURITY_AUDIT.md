# Skillify — Security Audit Report

**Audit Date:** November 04, 2026  
**Audited Target:** Skillify (Django 6.0.2 / Python 3.12 / MySQL)  
**Project Scope:** Complete Project Codebase Security Review prior to GitHub Publication  
**Environment Type:** Development / Academic Project  

---

## Executive Summary

A comprehensive security audit of the Skillify project codebase was performed across all apps (`users`, `profiles`, `skills`, `session`, `core`, `reviews`, `messaging`, `trust`, `notifications`, `disputes`, `skillify_admin`). 

The audit identified **4 Critical**, **7 High**, **6 Medium**, and **4 Low** severity security findings. 

> [!CAUTION]
> **DO NOT commit this repository to GitHub in its current state.**  
> The project currently contains **plaintext credentials** (Gmail App Password, Zoom OAuth API keys, MySQL root database password, and Django SECRET_KEY) and **lacks a `.gitignore` file**. Pushing now will expose your email account, Zoom account, and database credentials to public scrapers within seconds.

---

## Vulnerability Summary Matrix

| ID | Issue Name | Location | Category | Risk Level |
|---|---|---|---|---|
| **SEC-01** | Exposed Third-Party & Database Credentials | `skillify_project/settings.py` | Secrets Exposure | **Critical** |
| **SEC-02** | Hardcoded Django Secret Key & Insecure Settings | `skillify_project/settings.py` | Configuration | **Critical** |
| **SEC-03** | Missing `.gitignore` File & Threat of Data Leak | Project Root | GitHub / Secrets | **Critical** |
| **SEC-04** | Stored DOM Cross-Site Scripting (XSS) in Chat Messages | `messaging/templates/messaging/conversation.html` | XSS | **Critical** |
| **SEC-05** | Unrestricted File Upload in Certificates & Disputes | `profiles/views.py`, `disputes/views.py` | File Upload Security | **High** |
| **SEC-06** | State-Changing Actions Accessible via GET Requests (CSRF) | `session/views.py`, `session/urls.py` | CSRF / Authorization | **High** |
| **SEC-07** | Missing `@login_required` on Sensitive Session Views | `session/views.py` | Authorization | **High** |
| **SEC-08** | OTP Expiration Timedelta Logic Flaw | `users/views.py`, `core/views.py` | Authentication Bypass | **High** |
| **SEC-09** | Lack of Rate Limiting on Login and 6-Digit OTP Endpoints | `users/views.py`, `core/views.py` | Brute Force / Auth | **High** |
| **SEC-10** | Race Condition & Double-Spending in Session Booking | `session/views.py` | Business Logic / Data Integrity | **High** |
| **SEC-11** | Stored Cross-Site Scripting (XSS) in Admin Sessions Modal | `skillify_admin/templates/skillify_admin/sessions.html` | XSS | **High** |
| **SEC-12** | Denial of Service via Unauthenticated NLP Trust Score API | `trust/views.py` | Denial of Service (DoS) | **Medium** |
| **SEC-13** | Incomplete Validation in `api_book_session` Endpoint | `session/views.py` | Authorization / Logic | **Medium** |
| **SEC-14** | Disabled Password Complexity Validators | `skillify_project/settings.py` | Authentication | **Medium** |
| **SEC-15** | Internal Exception and Stack Leakage in JSON Responses | `users/views.py`, `core/views.py` | Information Disclosure | **Medium** |
| **SEC-16** | Script Injection Risk via `|safe` in Admin Analytics | `skillify_admin/templates/skillify_admin/analytics.html` | XSS | **Medium** |
| **SEC-17** | Potential Open Redirect in Notification Click Handler | `notifications/views.py` | Open Redirect | **Medium** |
| **SEC-18** | CSV Formula Injection in Financial & Admin Exports | `core/views.py`, `skillify_admin/views.py` | Injection | **Low** |
| **SEC-19** | Loose Domain Validation in Video URL Parser | `users/models.py` | Iframe Injection | **Low** |
| **SEC-20** | Duplicate Authentication Routes Across `users` and `core` | `users/views.py`, `core/views.py` | Architecture / Drift | **Low** |
| **SEC-21** | Media Directory Unconditionally Served in Production URLconf | `skillify_project/urls.py` | Information Disclosure | **Low** |

---

## Detailed Audit Findings

### 1. SEC-01: Exposed Third-Party & Database Credentials
- **File:** `skillify_project/settings.py` (Lines 85, 122–123, 129–131)
- **Risk Level:** **Critical**
- **Description:**  
  `settings.py` contains hardcoded production and personal credentials:
  - **MySQL Database Password:** `'Kr#nal419'`
  - **Gmail SMTP Credentials:** Email `rajputsiddhraj6353@gmail.com` and App Password `eozd dajw dbcn xzuh`
  - **Zoom API OAuth Credentials:**
    - `ZOOM_ACCOUNT_ID = 'q5gAm1NxRuiVkO2U9suRHA'`
    - `ZOOM_CLIENT_ID = '2IBKuFXOQ5SjRiTE24Z9Xw'`
    - `ZOOM_CLIENT_SECRET = 'TZ1PWofTkYZrl3WaEQ7nmx1IslaZdSf3'`
- **Impact:**  
  Anyone who views the GitHub repository can hijack the Gmail account for sending spam or password reset attacks, take over the Zoom account, and compromise the local database if network access is shared.
- **Recommended Solution:**  
  1. Revoke the existing Gmail App Password and generate a new one.
  2. Regenerate the Zoom Client Secret in the Zoom App Marketplace portal.
  3. Change the database password.
  4. Move all secrets into an environment file (`.env`) using `python-decouple` (already installed in your environment):
     ```python
     from decouple import config

     SECRET_KEY = config('SECRET_KEY')
     DB_PASSWORD = config('DB_PASSWORD')
     EMAIL_HOST_USER = config('EMAIL_HOST_USER')
     EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
     ZOOM_ACCOUNT_ID = config('ZOOM_ACCOUNT_ID')
     ZOOM_CLIENT_ID = config('ZOOM_CLIENT_ID')
     ZOOM_CLIENT_SECRET = config('ZOOM_CLIENT_SECRET')
     ```

---

### 2. SEC-02: Hardcoded Django Secret Key & Insecure Settings
- **File:** `skillify_project/settings.py` (Lines 6, 8, 10)
- **Risk Level:** **Critical**
- **Description:**  
  - `SECRET_KEY = 'django-insecure-sk1ll1fy-s3cr3t-k3y-ch4ng3-1n-pr0duct10n'` is hardcoded.
  - `DEBUG = True`
  - `ALLOWED_HOSTS = ['*']`
  - Missing secure cookie settings (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`).
- **Impact:**  
  If the Django `SECRET_KEY` is known to an attacker, they can forge session cookies, tamper with signed tokens, and forge cryptographic hashes. `DEBUG = True` leaks complete source code, environment variables, settings, and database schemas on any unhandled exception.
- **Recommended Solution:**  
  - Load `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` from `.env`.
  - Ensure `DEBUG = False` before production deployment.
  - Set `ALLOWED_HOSTS` to specific domain names or IP addresses.

---

### 3. SEC-03: Missing `.gitignore` File & Threat of Massive Repository Leak
- **File:** Project Root (`.gitignore` does not exist)
- **Risk Level:** **Critical**
- **Description:**  
  There is currently **no `.gitignore` file** at the root of `skillify_project`.
- **Impact:**  
  Running `git add .` will stage:
  - The virtual environments (`venv/` and `.venv/`) totaling hundreds of megabytes.
  - The SQLite database file (`db.sqlite3`) which may contain real test accounts and sessions.
  - The entire `media/` folder including uploaded profile pictures, tutor certificates, and dispute evidence.
  - Development notes and documents containing setup information.
- **Recommended Solution:**  
  Create a `.gitignore` immediately before running any git commands (see complete template in Section 3 of this report).

---

### 4. SEC-04: Stored DOM Cross-Site Scripting (XSS) in Chat Messages
- **File:** `messaging/templates/messaging/conversation.html` (Lines 378–392)
- **Risk Level:** **Critical**
- **Description:**  
  In the conversation messaging UI, incoming messages polled via `pollMessages()` are injected into the DOM using `row.innerHTML`:
  ```javascript
  if (msg.content) bubble += msg.content;
  ...
  row.innerHTML = `${avL}<div class="msg-col"><div class="msg-bubble">${bubble}</div>...</div>`;
  ```
  Neither `msg.content` nor `msg.file_name` are escaped before being concatenated into `bubble` and assigned to `innerHTML`.
- **Impact:**  
  Any user can send a message containing `<img src=x onerror="fetch('/some-endpoint')...">` or `<script>`. When the other participant's browser polls for new messages, the malicious payload immediately executes within their active session. The attacker can hijack the victim's session, read private chat history, or trigger actions on their behalf.
- **Recommended Solution:**  
  Sanitize and escape text content before inserting into the DOM, or use `textContent` / `createTextNode`:
  ```javascript
  function escapeHTML(str) {
      const p = document.createElement('p');
      p.textContent = str;
      return p.innerHTML;
  }
  // Use escaped content:
  if (msg.content) bubble += escapeHTML(msg.content);
  ```

---

### 5. SEC-05: Unrestricted File Upload in Certificates & Disputes
- **Files:** 
  - `profiles/views.py` (Lines 52–64)
  - `disputes/views.py` (Lines 41, 55, 123, 133)
  - `disputes/models.py` (Lines 31, 77)
  - `profiles/models.py` (Line 8)
- **Risk Level:** **High**
- **Description:**  
  When tutors upload certificates (`cert_file`) or dispute parties upload evidence (`evidence_file`), the files are saved directly to the filesystem with **no validation**:
  - No file extension validation (allows `.html`, `.svg`, `.exe`, `.js`, `.py`, `.sh`).
  - No file size limits (allows multi-gigabyte uploads leading to disk exhaustion).
  - No MIME type inspection.
- **Impact:**  
  - If a user uploads an `.svg` or `.html` file, it is saved under `/media/certificates/` or `/media/disputes/evidence/`. When an admin or user opens the file URL in the browser, the browser executes the embedded JavaScript, leading to Stored XSS.
  - Large file uploads can crash the server via disk space exhaustion (Denial of Service).
- **Recommended Solution:**  
  1. Restrict allowed extensions (e.g., `['.pdf', '.jpg', '.jpeg', '.png']`).
  2. Enforce a strict file size ceiling (e.g., 5MB max).
  3. Validate using Django's `FileExtensionValidator`:
     ```python
     from django.core.validators import FileExtensionValidator

     evidence_file = models.FileField(
         upload_to='disputes/evidence/',
         validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
         blank=True, null=True
     )
     ```
  4. In the views, check `file.size <= 5 * 1024 * 1024` before saving.

---

### 6. SEC-06: State-Changing Actions Accessible via GET Requests (CSRF)
- **Files:** 
  - `session/views.py` (Lines 648, 694, 1134, 840, 910)
  - `session/urls.py` (Lines 8, 9, 10, 12, 13)
- **Risk Level:** **High**
- **Description:**  
  The following state-altering and financial operations are accessible via `GET` requests without CSRF token verification:
  - `cancel_booking_view` (`/cancel-booking/<booking_id>/`) $\rightarrow$ Cancels booking and triggers credit refunds.
  - `start_session_view` (`/start-session/<booking_id>/`) $\rightarrow$ Initiates Zoom session.
  - `mark_complete_view` (`/mark-complete/<booking_id>/`) $\rightarrow$ Confirms session completion and triggers credit transfers.
  - `reschedule_accept_view` (`/reschedule-accept/<booking_id>/`) $\rightarrow$ Updates session date and schedule.
  - `reschedule_decline_view` (`/reschedule-decline/<booking_id>/`) $\rightarrow$ Cancels booking and refunds credits.
- **Impact:**  
  An attacker can craft an external webpage containing `<img src="http://127.0.0.1:8000/cancel-booking/15/">` or send a link to a logged-in learner or tutor. Simply visiting the link will automatically cancel their booking or transfer credits without their intent.
- **Recommended Solution:**  
  Convert all state-changing views to require `POST` and protect them with Django CSRF tokens:
  ```python
  from django.views.decorators.http import require_POST

  @login_required
  @require_POST
  def cancel_booking_view(request, booking_id):
      ...
  ```
  In templates, wrap the action buttons inside `<form method="POST">{% csrf_token %}...<button type="submit">...</form>`.

---

### 7. SEC-07: Missing `@login_required` on Sensitive Session Views
- **File:** `session/views.py` (Lines 744, 1044)
- **Risk Level:** **High**
- **Description:**  
  - `book_session_view(request, session_id)` lacks the `@login_required` decorator.
  - `reschedule_session_view(request, session_id)` lacks the `@login_required` decorator.
- **Impact:**  
  When an anonymous (unauthenticated) user posts to `book_session_view`, calling `request.user.wallet` triggers an unhandled `AttributeError`, exposing 500 debug error pages if `DEBUG=True`.
- **Recommended Solution:**  
  Add `@login_required` to both view definitions:
  ```python
  @login_required
  def book_session_view(request, session_id):
      ...

  @login_required
  def reschedule_session_view(request, session_id):
      ...
  ```

---

### 8. SEC-08: OTP Expiration Timedelta Logic Flaw
- **Files:** 
  - `users/views.py` (Lines 89, 228)
  - `core/views.py` (Lines 89, 243)
- **Risk Level:** **High**
- **Description:**  
  The OTP expiration check in both `verify_otp_view` and `reset_password_view` uses:
  ```python
  if (timezone.now() - profile.otp_created_at).seconds <= 300:
  ```
  In Python, `timedelta.seconds` returns only the seconds portion within a 24-hour cycle modulo 86400 (it completely ignores `timedelta.days`).
- **Impact:**  
  If an OTP was generated 1 day and 1 minute ago (`1 day, 60 seconds`), `(now - created_at).days == 1`, but `(now - created_at).seconds == 60`! Because `60 <= 300`, an expired OTP that is days old is accepted as valid!
- **Recommended Solution:**  
  Use `total_seconds()`:
  ```python
  if (timezone.now() - profile.otp_created_at).total_seconds() <= 300:
  ```

---

### 9. SEC-09: Lack of Rate Limiting on Login and 6-Digit OTP Endpoints
- **Files:** `users/views.py`, `core/views.py`
- **Risk Level:** **High**
- **Description:**  
  The system uses a 6-digit numeric OTP (`000000` to `999999` $\rightarrow$ 1,000,000 combinations) for email verification and password resets. However:
  - There is no attempt counter on failed OTP entries.
  - There is no IP or account rate-limiting on `verify_otp_view`, `reset_password_view`, or `login_view`.
- **Impact:**  
  An attacker can initiate a password reset for any target email and launch an automated brute-force script against `reset_password_view`. Without attempt limits or account lockouts, a 6-digit space can be brute-forced rapidly, leading to complete account takeover.
- **Recommended Solution:**  
  1. Track `failed_attempts` on `UserProfile`. Invalidate the OTP after 5 consecutive failed attempts.
  2. Implement rate limiting using `django-ratelimit` or `django-axes` on login and OTP verification endpoints.

---

### 10. SEC-10: Race Condition & Double-Spending in Session Booking
- **File:** `session/views.py` (Lines 1079–1124, 1182–1226)
- **Risk Level:** **High**
- **Description:**  
  In both `book_session_view` and `api_book_session`, credit balance verification and credit deduction are performed without database locks or transaction isolation:
  ```python
  if wallet.balance < session.credits_required:
      return ...
  wallet.freeze_credits(session.credits_required)
  ```
- **Impact:**  
  If a user dispatches multiple simultaneous booking requests (e.g., using a script or rapid double-clicking), all requests will read the initial balance before any deduction is committed. This allows a user to spend more credits than they possess (double spending / negative balance).
- **Recommended Solution:**  
  Wrap credit operations in a database transaction with `select_for_update()`:
  ```python
  from django.db import transaction

  with transaction.atomic():
      wallet = Wallet.objects.select_for_update().get(user=request.user)
      if wallet.balance < session.credits_required:
          messages.error(request, 'Insufficient credits.')
          return redirect(...)
      wallet.freeze_credits(session.credits_required)
      ...
  ```

---

### 11. SEC-11: Stored Cross-Site Scripting (XSS) in Admin Sessions Modal
- **File:** `skillify_admin/templates/skillify_admin/sessions.html` (Lines 236–253)
- **Risk Level:** **High**
- **Description:**  
  In the custom admin dashboard, session booking details are dynamically formatted into an HTML string and injected with `.innerHTML`:
  ```javascript
  html += `...<span>${b.learner}</span>...`;
  ...
  document.getElementById('bookingModalContent').innerHTML = html;
  ```
- **Impact:**  
  If a malicious learner registers with an account name containing payload characters (e.g. `<img src=x onerror=...`), this payload will execute inside the browser of any staff member or superuser who inspects that session in the admin panel. This could lead to administrative session hijacking or unauthorized admin actions.
- **Recommended Solution:**  
  Escape `b.learner`, `b.avatar`, and `b.zoom_url` before inserting into the DOM string, or build table rows using `document.createElement()` and `textContent`.

---

### 12. SEC-12: Denial of Service via Unauthenticated NLP Trust Score API
- **File:** `trust/views.py` (Lines 13–32)
- **Risk Level:** **Medium**
- **Description:**  
  The endpoint `GET /trust/score/<pk>/` is unauthenticated (`require_GET`). If the tutor does not have a cached `TrustScore`, or if triggered repeatedly, it executes `recalculate_trust_score(user)`.
  This function executes:
  - `vaderSentiment` analyzer on all reviews.
  - `spaCy` NLP pipeline (`en_core_web_sm`) tokenization, lemma analysis, and entity processing.
  - `scikit-learn` TF-IDF vectorization and cosine similarity calculations.
  - Multiple relational database aggregations.
- **Impact:**  
  An unauthenticated attacker can script thousands of concurrent requests to `/trust/score/<pk>/`, exhausting CPU and RAM on the host server.
- **Recommended Solution:**  
  1. Do not trigger recalculations synchronously on `GET` requests. Return 404 or a default state if recalculation is not yet computed.
  2. Implement strict rate limiting (e.g., 60 requests per minute).

---

### 13. SEC-13: Incomplete Validation in `api_book_session` Endpoint
- **File:** `session/views.py` (Lines 1182–1226)
- **Risk Level:** **Medium**
- **Description:**  
  `api_book_session` performs booking via JSON API but is missing critical validations present in `book_session_view`:
  - It does NOT check whether `session.date` or `session.start_time` has already passed.
  - It does NOT verify whether `booked_count >= session.max_participants`.
- **Impact:**  
  Users can invoke the API endpoint directly to book expired sessions from past dates or overbook group sessions beyond the tutor's maximum participant capacity.
- **Recommended Solution:**  
  Synchronize validation logic between `book_session_view` and `api_book_session` or consolidate them into a single reusable service function.

---

### 14. SEC-14: Disabled Password Complexity Validators
- **File:** `skillify_project/settings.py` (Line 91)
- **Risk Level:** **Medium**
- **Description:**  
  `AUTH_PASSWORD_VALIDATORS = []` is completely empty. The views only check `len(password) < 6`.
- **Impact:**  
  Users can create trivial passwords such as `123456` or `aaaaaa`, making user and tutor accounts vulnerable to dictionary attacks and credential stuffing.
- **Recommended Solution:**  
  Re-enable Django's standard password validators:
  ```python
  AUTH_PASSWORD_VALIDATORS = [
      {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
      {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
      {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
      {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
  ]
  ```

---

### 15. SEC-15: Internal Exception and Stack Leakage in JSON Responses
- **Files:** `users/views.py` (Line 375), `core/views.py` (Line 475)
- **Risk Level:** **Medium**
- **Description:**  
  In `api_register`:
  ```python
  except Exception as e:
      return JsonResponse({'success': False, 'error': str(e)}, status=500)
  ```
- **Impact:**  
  Uncaught exceptions will output raw database error strings, table names, column constraints, or Python trace context to the client.
- **Recommended Solution:**  
  Log the exception on the server using `logger.exception(e)` and return a generic error message:
  ```python
  return JsonResponse({'success': False, 'error': 'An internal error occurred. Please try again later.'}, status=500)
  ```

---

### 16. SEC-16: Script Injection Risk via `|safe` in Admin Analytics
- **File:** `skillify_admin/templates/skillify_admin/analytics.html` (Lines 131–141)
- **Risk Level:** **Medium**
- **Description:**  
  Dynamic Django context variables (such as `skill_pop_labels` derived from skill names) are passed to JavaScript using the `|safe` filter inside a `<script>` tag:
  ```html
  "skillLabels": {{ skill_pop_labels|safe }},
  ```
- **Impact:**  
  If any skill name contains closing script tags (e.g., `</script><script>...`), it prematurely closes the script block and executes arbitrary JavaScript.
- **Recommended Solution:**  
  Use Django's built-in `json_script` tag:
  ```html
  {{ skill_pop_labels|json_script:"skillLabelsData" }}
  ```
  Then in JavaScript:
  ```javascript
  const skillLabels = JSON.parse(document.getElementById('skillLabelsData').textContent);
  ```

---

### 17. SEC-17: Potential Open Redirect in Notification Click Handler
- **File:** `notifications/views.py` (Lines 57–58)
- **Risk Level:** **Medium**
- **Description:**  
  `mark_read` executes:
  ```python
  if notification.link:
      return redirect(notification.link)
  ```
- **Impact:**  
  If a notification link begins with `https://` or `//`, or if an attacker can influence notification links (e.g. through future announcement forms or profile fields), users can be redirected to external phishing domains upon clicking a notification.
- **Recommended Solution:**  
  Validate that `notification.link` is a relative URL using Django's `url_has_allowed_host_and_scheme`:
  ```python
  from django.utils.http import url_has_allowed_host_and_scheme

  if notification.link and url_has_allowed_host_and_scheme(notification.link, allowed_hosts={request.get_host()}):
      return redirect(notification.link)
  return redirect('notifications_page')
  ```

---

### 18. SEC-18: CSV Formula Injection in Financial & Admin Exports
- **Files:** `core/views.py` (Line 540), `skillify_admin/views.py` (User/Tutor/Review CSV exports)
- **Risk Level:** **Low**
- **Description:**  
  When exporting wallet transaction histories or user lists to CSV, string fields (such as `txn.description` or user names) are written directly to the CSV file without escaping special prefix characters.
- **Impact:**  
  If a transaction description or user name begins with `=`, `+`, `-`, or `@`, spreadsheet applications (Microsoft Excel, LibreOffice Calc) may interpret the cell as an executable formula upon opening.
- **Recommended Solution:**  
  Prepend a single quote `'` to any cell value that starts with `=`, `+`, `-`, or `@`.

---

### 19. SEC-19: Loose Domain Validation in Video URL Parser
- **File:** `users/models.py` (Lines 50–58)
- **Risk Level:** **Low**
- **Description:**  
  In `get_embed_video_url`:
  ```python
  elif 'youtube.com/embed/' in url:
      return url
  ```
  Because it checks for substring containment (`'youtube.com/embed/' in url`), an input such as `https://attacker.com/fake?youtube.com/embed/` satisfies the condition and is returned as the iframe source.
- **Impact:**  
  A tutor could embed an external site or phishing iframe into their public tutor profile.
- **Recommended Solution:**  
  Parse the domain using `urllib.parse.urlparse` and verify that the hostname ends with `youtube.com`.

---

### 20. SEC-20: Duplicate Authentication Routes Across `users` and `core`
- **Files:** `users/urls.py`, `core/urls.py`, `skillify_project/urls.py`
- **Risk Level:** **Low**
- **Description:**  
  Both `users.urls` and `core.urls` define identical routes for `register/`, `login/`, `logout/`, `verify-otp/`, and `forgot-password/`. Both are included in the root `urls.py`.
- **Impact:**  
  Code duplication creates security drift where a patch or security fix applied to `users/views.py` is not reflected in `core/views.py`.
- **Recommended Solution:**  
  Remove the duplicate auth routes from `core/urls.py` and delete duplicate auth views from `core/views.py`.

---

### 21. SEC-21: Media Directory Unconditionally Served in Production URLconf
- **File:** `skillify_project/urls.py` (Line 22)
- **Risk Level:** **Low**
- **Description:**  
  `urlpatterns` unconditionally appends:
  ```python
  urlpatterns = [...] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
  ```
  And then conditionally checks `if settings.DEBUG: urlpatterns += static(...)` again at line 24.
- **Impact:**  
  Django is not designed to serve media files in production. In production environments, user media should be served via Nginx/Apache or cloud object storage (AWS S3) to avoid blocking Python worker threads.
- **Recommended Solution:**  
  Only serve `MEDIA_URL` through Django when `settings.DEBUG` is True.

---

## 3. GitHub Pre-Publishing Checklist & Configuration

Before running `git init` and uploading your code to GitHub, execute the following steps:

### Step 1: Create a `.gitignore` File
Create a `.gitignore` file in your root project directory (`C:\Users\HP\Desktop\skillify_project\.gitignore`) with the following content:

```gitignore
# Python artifacts
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual Environments (DO NOT COMMIT)
venv/
.venv/
env/
ENV/

# Database files (DO NOT COMMIT)
db.sqlite3
db.sqlite3-journal
*.db
*.sqlite3

# Environment & Secret files (DO NOT COMMIT)
.env
.env.*
!.env.example

# User Media uploads (DO NOT COMMIT)
media/profile_pics/
media/certificates/
media/disputes/
media/messaging/
media/*
!media/.gitkeep

# IDE and Editor configurations
.vscode/
.idea/
*.sublime-project
*.sublime-workspace

# OS-specific files
Thumbs.db
Desktop.ini
.DS_Store

# Temporary & Working Files
*.log
scratch/
Skillify_Presentation*.pptx
Skillify_*Report*.docx
Skillify_*Report*.pdf
*.jpeg
*.jpg
*.png
website_details.txt
admin panel.txt
trust score.txt
new_chat.txt
abc.txt
i.txt
skillify_project_setup.txt
```

### Step 2: Create `.env` and `.env.example`
1. Create a `.env` file (which will remain on your local machine and **never** be committed):
   ```env
   SECRET_KEY=generate-a-new-random-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=skillify_db
   DB_USER=root
   DB_PASSWORD=your_actual_db_password
   DB_HOST=localhost
   DB_PORT=3306

   EMAIL_HOST_USER=your_email@gmail.com
   EMAIL_HOST_PASSWORD=your_new_app_password

   ZOOM_ACCOUNT_ID=your_zoom_account_id
   ZOOM_CLIENT_ID=your_zoom_client_id
   ZOOM_CLIENT_SECRET=your_new_zoom_client_secret
   ```

2. Create a `.env.example` file (which **will** be committed to GitHub so others know what variables are required):
   ```env
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=skillify_db
   DB_USER=root
   DB_PASSWORD=your_db_password
   DB_HOST=localhost
   DB_PORT=3306

   EMAIL_HOST_USER=example@gmail.com
   EMAIL_HOST_PASSWORD=your_gmail_app_password

   ZOOM_ACCOUNT_ID=your_zoom_account_id
   ZOOM_CLIENT_ID=your_zoom_client_id
   ZOOM_CLIENT_SECRET=your_zoom_client_secret
   ```

### Step 3: Security Scan Tools (Dependency Audit)
*Note on Automated Tools:* Standard CLI tools such as `pip-audit`, `bandit`, and `safety` were not installed in the environment (as per instructions to not install packages without explicit permission).  
Before submitting to GitHub, you may optionally run:
```powershell
.\venv\Scripts\python.exe -m pip install pip-audit bandit
.\venv\Scripts\pip-audit.exe
.\venv\Scripts\bandit.exe -r . -x ./venv,./.venv
```

---

## Overall Security Assessment & Next Steps

| Assessment Metric | Status |
|---|---|
| **SQL Injection** | **PASS** — Safe use of Django ORM without raw SQL string concatenation. |
| **Authentication Flow** | **PARTIAL** — Multi-role auth and OTP work, but OTP expiration logic flaw and absence of rate limiting require immediate patching. |
| **Access Control (Authorization)** | **PARTIAL** — Most views are scoped properly, but multiple state-changing operations are exposed to CSRF via `GET` requests and missing decorators. |
| **Cross-Site Scripting (XSS)** | **ACTION REQUIRED** — Client-side `.innerHTML` usage in messaging chat polling and admin sessions must be sanitized. |
| **Secrets & GitHub Readiness** | **CRITICAL ACTION REQUIRED** — All hardcoded credentials must be migrated to `.env` and revoked, and `.gitignore` must be added before committing. |

### Minimum Fixes Required Prior to GitHub Upload:
1. **Remove hardcoded secrets from `settings.py`** and migrate them to `.env`.
2. **Revoke and regenerate** the exposed Gmail App Password and Zoom Client Secret.
3. **Create the `.gitignore` file** to ensure `venv/`, `media/`, `db.sqlite3`, and sensitive documents are excluded from Git tracking.
4. **Fix the timedelta expiration bug** (`.total_seconds() <= 300`) in OTP views.
5. **Escape HTML** before assigning to `.innerHTML` in `conversation.html`.

