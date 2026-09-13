# 🎓 RAS-Computer-Educations

[![Django](https://img.shields.io/badge/Django-6.0%2B-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![ReportLab](https://img.shields.io/badge/PDF_Generation-ReportLab-FF6B6B?style=for-the-badge)](https://www.reportlab.com/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)
[![Theme](https://img.shields.io/badge/Theme-Dark%20%2F%20Light%20Mode-6366F1?style=for-the-badge)](#-uiux--styling-features)

A modern, full-featured web portal and administrative management system built with **Django** for **RAS-Computer-Educations**. The platform provides an intuitive public interface for prospective students, an instant anti-tamper certificate verification engine, dynamic course promotion tickers, an inquiry CRM with WhatsApp integration, and a dedicated staff administration dashboard.

---

## 📑 Table of Contents

- [✨ Key Features](#-key-features)
  - [🌐 Public Web Portal](#-public-web-portal)
  - [🛡️ Anti-Tamper Certificate Verification & PDF Engine](#️-anti-tamper-certificate-verification--pdf-engine)
  - [📬 Inquiry CRM & Lead Management](#-inquiry-crm--lead-management)
  - [🎛️ Administrative Dashboard](#️-administrative-dashboard)
  - [🌓 Modern UI/UX & Responsive Design](#-modern-uiux--responsive-design)
- [🏗️ System Architecture & Apps](#️-system-architecture--apps)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚀 Quick Start & Installation](#-quick-start--installation)
- [🗺️ Routing & URL Reference](#️-routing--url-reference)
- [🔒 Security & Verification Specifications](#-security--verification-specifications)
- [🔄 Automated Git Hooks](#-automated-git-hooks)
- [⚙️ Configuration & Environment Settings](#️-configuration--environment-settings)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Key Features

### 🌐 Public Web Portal
- **Interactive Homepage:** Modern landing page with hero banner, fast certificate lookup, featured programs, and dynamic counter badges.
- **Categorized Course Catalog:** Structured catalog categorized into:
  - 💻 **Basic Fundamentals** (Computer basics, Office productivity, Data Entry)
  - 📊 **Accounting & Finance** (Tally Prime, GST, Inventory Management)
  - ⚙️ **Programming & Development** (C, C++, Java, Python, Web Scripting)
  - 🎓 **Diploma Programs** (6-Month Career Diplomas)
  - 🏆 **Advance Diploma Programs** (12-Month Master Diplomas)
  - 🚀 **Frontend & Full Stack Engineering** (React, Django, NodeJS, Full Stack tracks)
  - 🧩 **Modular Courses** (Specialized individual tools and skill boosters)
- **Course Detail Pages:** Deep-dive syllabus overview, duration, fees, eligibility criteria, and instant inquiry action buttons.
- **Promotional Offers Ticker:** Seamless horizontal announcement ticker at the top of the site displaying active discounts, limited-time offers, and course badges.
- **Dynamic About Us & Contact Pages:** Live contact information, working hours, direct WhatsApp chat links, and embedded Google Maps.

---

### 🛡️ Anti-Tamper Certificate Verification & PDF Engine
- **Instant Online Verification:** Verify certificates globally by Certificate ID via the persistent navbar search bar or dedicated `/verify-certificate/` portal.
- **Cryptographic Tamper-Proofing:** 
  - Generates a **SHA-256 verification hash** and a **16-character alphanumeric verification token** computed from the student's name, certificate ID, course ID, issue date, and grade.
  - Strict exact-match lookup preventing wildcard or fuzzy identifier leaks.
- **Standardized Certificate ID Format:** Automated algorithmic generation adhering to:
  ```
  CERT-YYYY-FL-RANDOM-SEQ
  Example: CERT-2026-JD-8492-01
  ```
  *(Where `YYYY` = year, `FL` = initials of student, `RANDOM` = 4-digit entropy, `SEQ` = 2-digit sequential order)*.
- **Dynamic PDF Rendering (ReportLab):** Generates print-ready high-resolution certificates with double-line borders, official seals, and custom typography matching RAS-Computer-Educations standards.
- **Batch Export as ZIP:** Export all issued certificates into a single organized ZIP archive with smart duplicate filename deduplication.
- **Direct Web Printing:** One-click browser print view with dedicated print media queries (`@media print`).

---

### 📬 Inquiry CRM & Lead Management
- **Inquiry Capture Form:** Prospective students can send course inquiries directly with pre-selected courses.
- **Lead Tracking Lifecycle:** Track inquiries across lifecycle stages:
  - `Pending` ➔ `Contacted` ➔ `Interested` ➔ `Callback Later` ➔ `Not Interested` ➔ `Converted`
- **Follow-up Timeline:** Add chronological staff remarks and schedule future callback timestamps.
- **1-Click WhatsApp Direct Integration:** Open a direct WhatsApp conversation (`https://wa.me/<number>`) with prospective students directly from the dashboard.
- **Unread Notification Badges:** Live unread notification counter in the dashboard navigation bar.

---

### 🎛️ Administrative Dashboard
- **Protected Staff Authentication:** Restrict access exclusively to staff/admin accounts with session inactivity timeouts (`SESSION_COOKIE_AGE`).
- **Real-Time Overview Metrics:** Quick metric cards for Total Courses, Total Certificates, Registered Students, and Pending Inquiries.
- **Course Management:** Full CRUD operations (Add, Edit, Delete) with image upload and one-click "Featured on Homepage" toggling.
- **Certificate Management:** Issue new certificates with auto-generated or manual IDs, preview PDFs, edit records, revoke invalid certificates, or download in bulk.
- **Offers Manager:** Create, activate/deactivate, set start & end dates, prioritize order, and publish promotional ticker banners.
- **Student Profile Management:** View enrolled student accounts, active/inactive statuses, and associated course details.
- **In-Place Site CMS:** Edit the "About Us" and "Contact Details" content directly through the admin panel without modifying code or restarting the server.

---

### 🌓 Modern UI/UX & Responsive Design
- **Zero Heavy Framework Bloat:** Built with semantic HTML5 and clean Vanilla CSS using CSS variables (custom properties).
- **Persistent Theme Switcher:** Dark and Light mode toggling with memory saved to `localStorage` and system color preference (`prefers-color-scheme`) auto-detection.
- **Fully Responsive:** Smooth layout transitions across mobile screens, tablets, laptops, and ultra-wide displays.
- **Micro-Interactions:** Subtle hover states, animated ticker tracks, modal dialogues, and flash notification dismissals.

---

## 🏗️ System Architecture & Apps

The project follows a modular Django application structure:

```
RAS-COMPUTER-EDUCATION/
├── accounts/                  # Student profile management and auth extension
│   ├── models.py              # StudentProfile (linked to Django User)
│   ├── forms.py               # Registration and profile forms
│   └── tests.py               # Account unit tests
├── certificates/              # Certificate issuance, verification, and PDF generation
│   ├── models.py              # Certificate model with SHA-256 hash logic
│   ├── utils.py               # ID generator, ReportLab PDF engine, ZIP packager
│   ├── forms.py               # Verification forms
│   ├── views.py               # Public certificate verification endpoints
│   └── urls.py                # Route definitions (/verify-certificate/)
├── core/                      # Core public pages and dynamic site content
│   ├── models.py              # Inquiry, InquiryFollowUp, AboutContent, ContactContent
│   ├── context_processors.py  # Global site content injector
│   ├── forms.py               # Public contact & inquiry forms
│   ├── views.py               # Home, About, and Contact views
│   └── urls.py                # Public page routes
├── courses/                   # Course catalog and promotional offers
│   ├── models.py              # Course and CourseOffer models
│   ├── context_processors.py  # Active course offers ticker injector
│   ├── views.py               # Course listing and detail views
│   └── urls.py                # Course catalog routes (/courses/)
├── dashboard/                 # Staff administration portal
│   ├── decorators.py          # @staff_required access control decorator
│   ├── forms.py               # Admin forms for CRUD operations & CMS editing
│   ├── context_processors.py  # Inquiry notification counter injector
│   ├── views.py               # Admin dashboard views, stats, CRUD controllers
│   └── urls.py                # Admin portal routes (/cdac-admin/)
├── computer_class_site/       # Django project configuration
│   ├── settings.py            # Global project settings & context processors
│   ├── urls.py                # Root URL dispatcher
│   └── wsgi.py                # WSGI application entry point
├── static/                    # Static assets
│   ├── css/
│   │   ├── style.css          # Main stylesheet with CSS design tokens & dark mode
│   │   └── auth.css           # Authentication & dashboard styling
│   ├── js/
│   │   └── main.js            # Theme toggle, mobile nav, and UI interaction scripts
│   └── images/                # Logos, badges, and default banners
├── templates/                 # Django HTML templates
│   ├── base.html              # Base layout with navbar, ticker & theme switcher
│   ├── core/                  # home.html, about.html, contact.html
│   ├── courses/               # course_list.html, course_detail.html
│   ├── certificates/          # verify.html, result.html
│   └── dashboard/             # Admin portal templates, management tables, forms
├── .githooks/                 # Git hooks for automated migration management
│   ├── post-checkout          # Runs 'python manage.py migrate' after branch checkout
│   └── post-merge             # Runs 'python manage.py migrate' after pull/merge
├── manage.py                  # Django CLI utility
├── setup.bat                  # One-click Windows setup batch script
└── .gitignore                 # Git ignore rules for Python/Django
```

---

## 🛠️ Tech Stack

| Component | Technology / Library | Description |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+ & Django 6.x | Robust, secure web framework and ORM |
| **Database** | SQLite (Default) | Zero-configuration database (swappable with PostgreSQL / MySQL) |
| **PDF Generation** | ReportLab | Programmatic rendering of vector-sharp certificate documents |
| **Image Processing** | Pillow (PIL) | Course thumbnail and image handling |
| **Frontend** | HTML5, Vanilla CSS3, JavaScript | Lightweight, high-performance UI without heavy npm bundles |
| **Typography** | Google Fonts | Outfit, Plus Jakarta Sans, Mukta |
| **Security** | SHA-256 Hashing | Cryptographic certificate validation tokens |

---

## 🚀 Quick Start & Installation

### Prerequisites
- Python 3.10 or higher installed ([Download Python](https://www.python.org/downloads/))
- Git installed ([Download Git](https://git-scm.com/))

### 1. Clone the Repository
```bash
git clone https://github.com/Shivam-Patel22/RAS-COMPUTER-EDUCATION.git
cd RAS-COMPUTER-EDUCATION
```

### 2. Create and Activate a Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install django reportlab pillow
```

### 4. Configure Git Hooks & Initial Database
You can run the included Windows setup script:
```cmd
setup.bat
```
Or execute the steps manually:
```bash
# Set Git to use the repository's automated hooks
git config core.hooksPath .githooks

# Run initial database migrations
python manage.py migrate
```

### 5. Create an Administrator (Staff) Account
To access the staff management portal, create a superuser:
```bash
python manage.py createsuperuser
```
Follow the interactive prompts to set your username, email, and password.

### 6. Start the Development Server
```bash
python manage.py runserver
```

Open your browser and visit:
- **Public Portal:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Staff Admin Dashboard:** [http://127.0.0.1:8000/cdac-admin/](http://127.0.0.1:8000/cdac-admin/)
- **Django Native Admin:** [http://127.0.0.1:8000/django-admin/](http://127.0.0.1:8000/django-admin/)

---

## 🗺️ Routing & URL Reference

### 🌐 Public Endpoints
| URL Route | View / Action | Description |
| :--- | :--- | :--- |
| `/` | `core:home` | Homepage with hero section, quick search & highlights |
| `/about/` | `core:about` | About the institute, mission, and key pillars |
| `/contact/` | `core:contact` | Contact information, interactive inquiry form & map |
| `/courses/` | `courses:course_list` | Categorized course catalog |
| `/courses/<id>/` | `courses:course_detail` | Detailed syllabus, pricing, and duration |
| `/verify-certificate/` | `certificates:verify` | Certificate lookup & cryptographic verification |
| `/verify/` | `certificates:verify_alt` | Alternate alias for certificate verification |

### 🎛️ Staff Admin Dashboard
| URL Route | View / Action | Description |
| :--- | :--- | :--- |
| `/cdac-admin/` | `dashboard:login` | Staff authentication portal |
| `/cdac-admin/dashboard/` | `dashboard:index` | Main statistics & activity analytics overview |
| `/cdac-admin/courses/` | `dashboard:manage_courses` | Course catalog CRUD management |
| `/cdac-admin/courses/add/` | `dashboard:add_course` | Create a new course entry |
| `/cdac-admin/certificates/` | `dashboard:manage_certificates` | Certificate records management |
| `/cdac-admin/certificates/add/` | `dashboard:add_certificate` | Issue single or batch certificates |
| `/cdac-admin/certificates/<id>/print/` | `dashboard:print_certificate` | Instant on-screen PDF print view |
| `/cdac-admin/certificates/download-zip/` | `dashboard:download_certificates_zip` | Download all certificates in a ZIP bundle |
| `/cdac-admin/inquiries/` | `dashboard:manage_inquiries` | Lead inquiry CRM table |
| `/cdac-admin/inquiries/<id>/followup/` | `dashboard:add_inquiry_followup` | Add staff remark & callback scheduling |
| `/cdac-admin/offers/` | `dashboard:manage_offers` | Promotional banner & ticker manager |
| `/cdac-admin/students/` | `dashboard:active_students` | Registered student directory |
| `/cdac-admin/about/edit/` | `dashboard:edit_about` | In-place About page CMS editor |
| `/cdac-admin/contact/edit/` | `dashboard:edit_contact` | In-place Contact page CMS editor |
| `/cdac-admin/logout/` | `dashboard:logout` | End staff session |

---

## 🔒 Security & Verification Specifications

1. **Exact-Match Querying:** Certificate verification uses exact case-insensitive matching (`iexact`) to prevent enumeration attacks or partial identifier snooping.
2. **Cryptographic Hashes:** When a certificate is issued or saved, a SHA-256 hash is generated using:
   ```python
   hashlib.sha256(f"{certificate_id}|{student_name}|{course_id}|{issue_date}|{grade}".encode('utf-8')).hexdigest()
   ```
3. **Session Inactivity Guard:** Administrative sessions expire automatically after inactivity (`SESSION_COOKIE_AGE = 3600` seconds) and upon browser closure.
4. **Role Segregation:** Only users with `is_staff = True` are granted access to the staff dashboard suite; student or anonymous requests are cleanly blocked and redirected.

---

## 🔄 Automated Git Hooks

This repository includes pre-configured Git hooks in the `.githooks/` directory to simplify team collaboration:
- **`post-checkout`**: Automatically executes `python manage.py migrate` when switching branches so local schemas stay up to date.
- **`post-merge`**: Automatically applies new database migrations after pulling changes from remote branches.

To enable them:
```bash
git config core.hooksPath .githooks
```

---

## ⚙️ Configuration & Environment Settings

Key settings can be modified in [`computer_class_site/settings.py`](file:///computer_class_site/settings.py):

| Setting | Default Value | Purpose |
| :--- | :--- | :--- |
| `DEBUG` | `True` | Set to `False` in production deployments |
| `ALLOWED_HOSTS` | `[]` | Add your production domain(s) and IPs |
| `SECRET_KEY` | `django-insecure-...` | Set via environment variable in production |
| `SESSION_COOKIE_AGE` | `3600` (1 hour) | Duration of staff login session |
| `EMAIL_BACKEND` | `console.EmailBackend` | Set to SMTP backend for live email notifications |
| `MEDIA_ROOT` | `BASE_DIR / 'media'` | Directory for uploaded course images |

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome!

1. Fork the Project repository.
2. Create your Feature Branch:
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. Commit your Changes:
   ```bash
   git commit -m "Add AmazingFeature"
   ```
4. Push to the Branch:
   ```bash
   git push origin feature/AmazingFeature
   ```
5. Open a Pull Request.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">
  <sub>Developed for <strong>RAS-Computer-Educations</strong>. Built with ❤️ using Python & Django.</sub>
</div>
