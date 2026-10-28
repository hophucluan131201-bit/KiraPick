"""App updates: the ONLY part of KiraPick allowed to use the network.

Runs only when the user starts it (⚙ Tuỳ chọn → Cập nhật KiraPick) or has switched on the daily
check (off by default). Reads KiraPick's public GitHub release list, downloads the newest installer
of this edition and checks it against GitHub's SHA-256 digest before running it. Never sends photos,
scores or any personal data. Analysis itself never touches the network.
"""
