# StudyX AI — Mobile Responsive Fix (22 Nov 2026)

This package makes the public landing page a real single-column phone layout and
adds proper mobile navigation and readable cards to the study dashboard.

## Installation

1. Back up your old project and **do not delete** `instance/studyx_blue.sqlite3`.
2. Stop the Flask server (`Ctrl+C`). In DB Browser, commit any intended edits,
   then disconnect any open write transactions.
3. Replace the project's matching files with those in this ZIP.
   If you download the small PATCH, extract its `STUDYX-AI-Blue` folder into
   the same parent folder as your existing `STUDYX-AI-Blue` project and merge.
4. Keep your `.env` configuration and database file from your old project.
5. From the folder containing `run.py` run `python run.py --lan` to test on
   the same Wi-Fi, or `python run.py` for laptop-only use.
6. On your mobile browser reload the page. If an old PWA installation still
   shows the previous CSS, close/reopen the tab or remove/reinstall the old PWA.

The HTML viewport meta tag was already correct. The original site was missing
landing-page-specific CSS breakpoints, leaving desktop columns compressed into
mobile widths. Changes: new `studyx-mobile.css` included *after* original
styles in `base.html`, new PWA service-worker cache version, tablet and mobile
layouts, readable tap targets, cards, dashboard sidebar/bottom nav and forms.

## Verification

The public landing, sign-up and dashboard templates were rendered with the
bundled CSS using headless Chromium at 320, 375, 390, 680, 768, 1024 and
1280px. On phone widths (320-680px), they had no document horizontal overflow.
Flask/database operations were not exercised by these visual tests.
