import logging
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Use the narrowest scope you need
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("sort.log")],
)

def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)  # opens browser for consent
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

service = get_service()

# List the 10 most recent messages
sender="noreply@steampowered.com"
labels = service.users().labels().list(userId="me").execute().get("labels", [])


def get_or_create_label(service, name):
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].lower() == name.lower():
            return label["id"]
    created = service.users().labels().create(
        userId="me",
        body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return created["id"]


label_name = "Steam"
label_id = get_or_create_label(service, label_name)
results = service.users().messages().list(
    userId="me", q=f'from:{sender} -label:"{label_name}"', maxResults=500
).execute()

message_ids = [m["id"] for m in results.get("messages", [])]
changed = skipped = failed = 0

for msg_id in message_ids:
    try:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "(no subject)")

        if label_id in msg.get("labelIds", []):
            skipped += 1
            logging.debug("Already labeled: %s", subject)
            continue

        updated = service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]},
        ).execute()

        changed += 1
        logging.info("Added label '%s' -> %s (id=%s)", label_name, subject, msg_id)
        # updated["labelIds"] holds the message's labels after the change
    except Exception:
        failed += 1
        logging.exception("Failed to label message %s", msg_id)

logging.info("Done: %d labeled, %d already had it, %d failed", changed, skipped, failed)