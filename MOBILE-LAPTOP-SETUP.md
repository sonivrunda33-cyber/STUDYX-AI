# Use StudyX AI on both laptop and mobile

The app already has mobile responsive navigation and a web app manifest.
The Flask backend and SQLite database remain on the laptop for LAN use.

## Option A: Same Wi-Fi network (no deployment required)

1. Back up `instance/studyx_blue.sqlite3`. **Never overwrite or delete it** when replacing the application code.
2. Close DB Browser write transactions; keep your laptop awake.
3. Open PyCharm PowerShell in the folder with `run.py` and run:

   ```powershell
   python run.py --lan
   ```

4. In a second PowerShell terminal, run `ipconfig`. Under **Wireless LAN adapter Wi-Fi**, find **IPv4 Address**, such as `192.168.1.7` (this is an example, not your actual address).
5. Connect laptop and phone to the *same* Wi-Fi. In the phone browser open `http://192.168.1.7:5000`, replacing the example IP with yours. Use the same URL on the laptop if desired.
6. If it doesn't load: check Windows Firewall > Allow an app through firewall > allow Python on **Private networks**, confirm phone is not on mobile data or a guest Wi-Fi network, and check for Wi-Fi client isolation. Do not open router port forwarding or enable Public network firewall access.
7. Sign in to the same account on both devices. Both use the **same laptop-based SQLite database** and shared study data. Updates should appear after refreshing the other device.

This method stops when laptop or Flask process is off. `127.0.0.1` on the *phone* points at the phone, not the laptop.

## Option B: Public internet link (phone and laptop anywhere)

Use a Python-compatible HTTPS web host (for example, Render) and a **persistent PostgreSQL** database.
The application supports `DATABASE_URL` on hosting and defaults to the existing local SQLite database on the laptop.

For a Render Python web service with its root directory set to the folder containing `run.py`:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT run:app`
- Set `DATABASE_URL` to the **internal connection URL** for your persistent PostgreSQL database.
- Set `STUDYX_SECRET_KEY` to a long random secret and `STUDYX_COOKIE_SECURE=1`.
- Never enable Flask debug mode in production and don't upload `.env` or `instance/studyx_blue.sqlite3` publicly.

On an ordinary host with temporary file storage, the local SQLite file may disappear after restarts/redeployments; never use that setup for real student accounts. Render's filesystem is ephemeral by default. A PostgreSQL database has its own plans and pricing; review the provider's current terms.

**Important**: A new hosted PostgreSQL database starts empty. The two existing local users and their progress **will not automatically move** to the new hosted database. You need a deliberate, backed-up data migration if those same accounts/data must appear online. Do not copy SQLite files into a PostgreSQL DB.

The service worker caches public static assets for speed, but **does not make the database-backed application fully offline-capable**. Add-to-Home-Screen support over HTTPS is browser-dependent.
