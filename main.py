import logging
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv
from gmail_service import get_service, get_or_create_label
# Use the narrowest scope you need
load_dotenv()  # Load environment variables from .env file
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("sort.log")],
)



service = get_service()


# List the 10 most recent messages
email_address = input("Enter your email address: ")
sender=email_address
labels = service.users().labels().list(userId="me").execute().get("labels", [])

label_name = input("Enter the label name to apply: ")
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