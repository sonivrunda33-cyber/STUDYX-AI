"""Start StudyX on this laptop, or share it on your trusted Wi-Fi network.

Local laptop: python run.py
Mobile on same Wi-Fi: python run.py --lan
For internet hosting, use a production server such as gunicorn run:app.
"""
import argparse
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run StudyX AI")
    parser.add_argument(
        "--lan", action="store_true",
        help="Allow phones and laptops on the same trusted Wi-Fi to reach this computer",
    )
    args = parser.parse_args()
    host = "0.0.0.0" if args.lan else os.environ.get("STUDYX_HOST", "127.0.0.1")
    port = int(app.config.get("PORT", 5000))
    if args.lan:
        print("\nStudyX LAN MODE: keep this terminal open and use 'ipconfig' to find your")
        print(f"laptop's Wi-Fi IPv4 address. Open http://<YOUR-LAPTOP-IP>:{port}")
        print("on your phone (same Wi-Fi). Allow Python on Private networks in Windows Firewall.")
        print("LAN mode is for a trusted local network, NOT for public internet hosting.\n")
    app.run(host=host, debug=app.config["DEBUG"], port=port)
