"""AI-model updates: the ONLY part of KiraPick allowed to use the network.

Runs only when the user starts it (⚙ Tuỳ chọn → Cập nhật mô hình AI…) or has switched on the
daily check (off by default). Downloads a signed catalogue from KiraPick's GitHub release, never
sends photos, scores or any personal data, and activates a model only after its SHA-256 matches
the signed catalogue. Analysis itself never touches the network.
"""
