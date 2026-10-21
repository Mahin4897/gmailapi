# Gmail Auto-Labeler and AI Email Prioritizer

Two small Python tools that organize your Gmail with labels, using the Gmail API:

1. **Sender labeler** (`main.py`): finds emails from a specific sender and adds a label to them (for example, every email from `noreply@steampowered.com` gets the label `Steam`).
2. **AI priority sorter** (`ai_email_sorter.py`): reads your recent inbox emails, asks the Gemini API to rate each one as **High**, **Medium** or **Low** priority, and adds the matching label (`Priority/High`, `Priority/Medium`, `Priority/Low`). It starts in a test mode that only prints the AI's answers and changes nothing in Gmail.

Both use OAuth to access your mailbox, create labels automatically, and write logs of what they do.

## Features

**Sender labeler**

- Searches Gmail with the same syntax as the Gmail search box (`from:`, `-label:`, and so on)
- Creates the label automatically if it doesn't exist
- Skips emails that already have the label, so it is safe to run repeatedly
- Keeps going if a single email fails, and prints a summary at the end

**AI priority sorter**

- Reads the subject, sender and the beginning of the body of recent inbox emails
- Classifies emails in batches with Gemini and gets a structured JSON answer
- Test mode (`PRINT_ONLY`) prints the raw AI response and a one-line result per email without touching Gmail
- Skips emails that already have a priority label, so each email is only sent to the AI once
- If an AI request fails, those emails stay unlabeled and are retried on the next run

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management (plain `pip` works too)
- A Google account (Gmail)
- A Google Cloud project with the Gmail API enabled (setup below)
- For the AI sorter: a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Project structure

```
gmailapi/
├── main.py              # sender labeler
├── ai_email_sorter.py   # AI priority sorter
├── gmail_service.py     # shared Gmail login and label helpers (used by the AI sorter)
├── .env                 # your Gemini API key (you create this)
├── client_secret.json   # OAuth client credentials from Google (you download this)
├── token.json           # created automatically after your first login
├── sort.log             # log written by main.py
├── priority.log         # log written by ai_email_sorter.py
├── pyproject.toml
└── README.md
```

`client_secret.json`, `token.json` and `.env` are secrets. **Never commit them to git** (see [Security](#security)).

`gmail_service.py` exists on purpose. Importing a Python file runs all of its top-level code, so importing `get_service` from `main.py` would also run the whole Steam labeling script. Keeping the shared helpers in their own file avoids that.

---

## Part 1: Set up the Gmail API

You only need to do this once. The menu names in Google Cloud Console change from time to time, so if something is labeled slightly differently, look for the closest match.

### Step 1: Create a Google Cloud project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in with the Google account whose mail you want to manage.
2. Click the project selector at the top of the page (next to the Google Cloud logo).
3. Click **New Project**.
4. Enter a name, for example `gmail-labeler`, and click **Create**.
5. Make sure the new project is selected in the project selector before continuing.

### Step 2: Enable the Gmail API

1. Open the navigation menu and go to **APIs & Services → Library**.
2. Search for **Gmail API** and open it.
3. Click **Enable**.

Direct link: <https://console.cloud.google.com/apis/library/gmail.googleapis.com> (select your project first).

### Step 3: Configure the OAuth consent screen

Google requires a consent screen before you can create credentials. It is what you see in the browser when you approve the script.

1. Go to **APIs & Services → OAuth consent screen**. In newer versions of the console this is called **Google Auth Platform**. If you see a **Get started** button, click it.
2. **App information:** enter an app name (for example `Gmail Labeler`) and choose your email as the user support email.
3. **Audience:** choose **External**. (Internal is only available for Google Workspace organizations.)
4. **Contact information:** enter your email address.
5. Agree to the policy and click **Create**.

Then add yourself as a test user. While the app is in "Testing" mode, only listed test users can log in:

1. Open the **Audience** page (or the **Test users** section on the consent screen page).
2. Under **Test users**, click **Add users**.
3. Enter the Gmail address you will log in with and click **Save**.

Optionally, open **Data Access** and add the scope `https://www.googleapis.com/auth/gmail.modify`. The scripts request this scope themselves at login, so this step is not required, but it makes the consent screen list it clearly.

### Step 4: Create the OAuth client and download `client_secret.json`

1. Go to **APIs & Services → Credentials**. In the newer console this is **Google Auth Platform → Clients**.
2. Click **Create Credentials → OAuth client ID** (or **Create client**).
3. For **Application type**, choose **Desktop app**. This is important. Other types fail with a `redirect_uri_mismatch` error.
4. Enter a name, for example `gmail-labeler-desktop`, and click **Create**.
5. A dialog shows your client ID and client secret. Click **Download JSON**.
6. Move the downloaded file into the project folder and **rename it to `client_secret.json`**. Google gives it a long name like `client_secret_123456-abc.apps.googleusercontent.com.json`, but the scripts look for exactly `client_secret.json`.

If you close the dialog without downloading, you can download the JSON again from the client's page.

### Step 5: Log in for the first time

1. Run one of the scripts (see the usage sections below).
2. Your browser opens a Google login page. Choose the account you added as a test user.
3. Google shows **"Google hasn't verified this app"**. This is expected for your own personal project. Click **Advanced**, then **Go to Gmail Labeler (unsafe)**.
4. Review the permission and click **Continue** or **Allow**.
5. The browser shows a message that the login completed, and a `token.json` file appears in the project folder.

Later runs reuse `token.json` and do not open the browser. The scripts refresh the token automatically when it expires.

If the machine has no browser (for example a remote server), do the first login on a computer with a browser, then copy `token.json` to the other machine.

### Make the login last longer (recommended)

While the consent screen is in **Testing** mode, Google expires the login after **7 days**, and the scripts will fail with `invalid_grant`. For a personal tool you can fix this:

1. Go to **OAuth consent screen / Audience**.
2. Click **Publish app** to move it to **In production**.
3. Delete `token.json` and log in again.

You will still see the "unverified app" warning, and you click through it just as before. Verification is only needed if other people will use your app.

---

## Part 2: Install

With uv:

```bash
uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib google-genai python-dotenv
```

Or, if you cloned a project that already has a `pyproject.toml`:

```bash
uv sync
```

With plain pip:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib google-genai python-dotenv
```

If you only use the sender labeler, `google-genai` and `python-dotenv` are not needed.

---

## Part 3: Sender labeler (`main.py`)

### Configure

Open `main.py` and edit these two values:

```python
sender = "noreply@steampowered.com"   # the sender whose emails you want to label
label_name = "Steam"                  # the label to add
```

Nested labels use a slash, for example `"Games/Steam"`.

### Run

```bash
uv run main.py
```

Example output:

```
2026-10-21 08:00:03,412 INFO Added label 'Steam' -> Your Steam receipt (id=18c2f4a9b1d3e5f7)
2026-10-21 08:00:03,901 INFO Added label 'Steam' -> New game in your wishlist (id=18c2f4a9b1d3e5f8)
2026-10-21 08:00:04,310 INFO Done: 2 labeled, 0 already had it, 0 failed
```

### How it works

1. **Authentication.** `get_service()` loads `token.json` if it exists and refreshes it when expired. If there is no valid token, it starts the browser login using `client_secret.json` and saves the result to `token.json`.
2. **Label lookup.** `get_or_create_label()` lists your existing labels and returns the ID of the one that matches `label_name`. If none matches, it creates it. The Gmail API works with label **IDs** (like `Label_8392011`), not names.
3. **Search.** The script searches with `from:<sender> -label:"<label>"`, so emails that already have the label are excluded from the results.
4. **Labeling.** For each message, it reads the subject and current labels, then calls `messages().modify()` with `addLabelIds`. It does not remove the email from the inbox.
5. **Logging.** Each change is logged with the subject and message ID. Errors on a single email are logged with a traceback and do not stop the run. A summary is printed at the end.

### Limitations

- A single run handles up to 500 matching emails (`maxResults=500`). Because already-labeled emails are excluded from the search, running the script again picks up the rest.
- Labels are only added. The emails stay in the inbox. To move them out of the inbox, add `"removeLabelIds": ["INBOX"]` to the `modify()` body.
- It makes two API calls per email, which is fine for hundreds of emails but slow for thousands. For large batches, collect the IDs and use `messages().batchModify()` (up to 1,000 IDs per call).

---

## Part 4: AI priority sorter (`ai_email_sorter.py`)

### Get a Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and sign in.
2. Click **Create API key** and copy it.
3. Create a file named `.env` in the project folder:

```
GEMINI_KEY=your-api-key-here
```

The script loads this file automatically. Do not put quotes around the key, and do not commit the file.

### Run in test mode first

`PRINT_ONLY` is `True` by default, so your first runs only print results:

```bash
uv run ai_email_sorter.py
```

Example output:

```
--- raw AI response ---
[{"id": "18c2f4a9b1d3e5f7", "priority": "High"}, {"id": "18c2f4a9b1d3e5f8", "priority": "Low"}]
2026-10-22 08:00:05,120 INFO High   | Bank <alerts@bank.example> | Payment failed
2026-10-22 08:00:05,121 INFO Low    | Steam <noreply@steampowered.com> | New game in your wishlist
2026-10-22 08:00:05,122 INFO PRINT_ONLY is on, no labels were changed
```

In test mode the script does not create or read any labels, and it processes the same most recent emails on every run. That lets you adjust the prompt or settings and compare results.

### Turn on labeling

When the results look right, open `ai_email_sorter.py` and set:

```python
PRINT_ONLY = False
```

Now the script creates `Priority/High`, `Priority/Medium` and `Priority/Low` (shown as `High`, `Medium` and `Low` under a `Priority` parent label in Gmail) and adds the matching one to each email. It does not remove emails from the inbox.

### Settings

All settings are at the top of `ai_email_sorter.py`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `MODEL` | `gemini-3.5-flash-lite` | The Gemini model used for classification. |
| `DAYS` | `3` | Only look at inbox emails from the last N days. |
| `MAX_EMAILS` | `40` | The most emails processed in one run. |
| `BATCH_SIZE` | `20` | How many emails are sent to the AI per request. |
| `BODY_CHARS` | `800` | How many characters of each email body the AI sees. |
| `PRIORITIES` | High, Medium, Low | The priority levels. |
| `LABEL_PREFIX` | `Priority/` | Prefix for the Gmail labels. |
| `PRINT_ONLY` | `True` | Test mode. `True` prints results only, `False` applies labels. |

To change how the AI decides, edit `SYSTEM_PROMPT`. Specific rules work better than vague ones, for example "Emails from my bank are always High" or "Steam sale emails are Low".

### How it works

1. **Find new emails.** It lists inbox emails from the last `DAYS` days. In labeling mode, it also lists which of them already have a priority label and skips those.
2. **Download them.** For each email it fetches the full message and extracts the subject, sender, date and body. Emails are made of nested parts with base64-encoded text, so the script prefers the `text/plain` part and falls back to stripping the tags from the `text/html` part.
3. **Classify in batches.** For each batch it sends the AI a JSON list containing only `id`, `from`, `subject` and the first `BODY_CHARS` characters of the body. The system prompt defines the three levels and requires a JSON-only reply. The request uses `response_mime_type="application/json"` so the reply parses reliably.
4. **Validate the answer.** The script ignores any answer whose ID was not in the batch or whose priority is not exactly High, Medium or Low. If the AI skipped an email or a request failed, that email is left unlabeled and retried on the next run.
5. **Apply labels.** In labeling mode, it groups the IDs by priority and adds each label with one `batchModify` call per group (up to 1,000 IDs per call).

### Privacy and safety

- For each email, the sender, subject and the first `BODY_CHARS` characters of the body are sent to the Gemini API. Reduce `BODY_CHARS`, or remove the body from the request, if that is too much. Check the Gemini API terms for how data is handled on your plan.
- Email content is untrusted. The system prompt tells the model not to follow instructions found inside emails, and the script only accepts a fixed set of priorities for IDs it sent. This reduces the risk of a malicious email manipulating its own priority, but it can't remove it completely.

### Limitations

- The AI can be wrong. Use test mode to check results, and tune `SYSTEM_PROMPT`.
- Only inbox emails from the last `DAYS` days are considered, and at most `MAX_EMAILS` per run.
- Labels are only added, never removed. If you re-run after changing the prompt, emails that already have a priority label are skipped. To re-sort them, remove their priority labels in Gmail first.
- The model name `gemini-3.5-flash-lite` may need changing depending on what your API key has access to (see Troubleshooting).

---

## Permissions (scope)

Both scripts request the `gmail.modify` scope. It lets them read mail and change labels. It is broader than read-only access, so treat `token.json` like a password. If you only want to read mail, use `gmail.readonly` instead, but then labeling will not work.

If you change `SCOPES` in `gmail_service.py` (or `main.py`), **delete `token.json`** and log in again. A token keeps the permissions it was created with. `gmail_service.py` also checks this and starts a new login if the saved token has different scopes.

## Troubleshooting

| Problem | Cause and fix |
| --- | --- |
| `403 Request had insufficient authentication scopes` | `token.json` was created with an older scope. Delete `token.json` and run again. |
| `Error 403: access_denied` in the browser | Your account isn't listed as a test user. Add it under **Audience → Test users**. |
| `invalid_grant` or `Token has been expired or revoked` | The token expired (7 days in Testing mode) or access was revoked. Delete `token.json` and log in again. Publish the app to avoid weekly expiry. |
| `redirect_uri_mismatch` | The OAuth client is not the **Desktop app** type. Create a new Desktop app client and download its JSON. |
| `FileNotFoundError: client_secret.json` | The file is missing or has the wrong name. Rename the downloaded JSON to `client_secret.json` and place it in the project folder. |
| `400 Invalid label` | A label name was passed where an ID is required. Use `get_or_create_label()` to get the ID. |
| `KeyError: 'messages'` | The search returned no results. Use `results.get("messages", [])`. |
| `Gmail API has not been used in project ... or it is disabled` | The API isn't enabled for the project that owns your credentials. Enable it in **APIs & Services → Library**. |
| `uv add` fails with `Network is unreachable` | A network or DNS problem, not a project problem. Check your connection (`curl -I https://files.pythonhosted.org`) and try again. |
| `ModuleNotFoundError: No module named 'gmail_service'` | `gmail_service.py` is missing or not in the same folder as `ai_email_sorter.py`. |
| Running the AI sorter also labels Steam emails | The AI sorter is importing from `main.py`. Import from `gmail_service.py` instead. |
| `GEMINI_KEY is not set` | The `.env` file is missing, is not in the folder you run from, or uses a different variable name. It must contain `GEMINI_KEY=...`. |
| Gemini `404` or "model not found" | The `MODEL` name isn't available to your key. List valid names with `[m.name for m in client.models.list()]` and update `MODEL`. |
| Gemini `429` or quota errors | You hit a rate or usage limit. The affected emails stay unlabeled and are retried on the next run. Lower `MAX_EMAILS`, or run less often. |
| `json.JSONDecodeError` in the AI sorter | The model returned something that isn't valid JSON. The raw reply is printed in test mode. The batch is skipped and retried next run. |
| `can only concatenate str (not "list") to str` | Email dictionaries were added to a string. Send `json.dumps(payload)` as the request contents, as `classify()` does. |

## Run it automatically every day (Linux, systemd)

These files work for either script. This example runs the AI sorter. For the sender labeler, change `ai_email_sorter.py` to `main.py` and rename the files.

Create `~/.config/systemd/user/gmailsort.service`:

```ini
[Unit]
Description=Prioritize Gmail emails with AI

[Service]
Type=oneshot
WorkingDirectory=/home/YOU/path/to/gmailapi
ExecStart=/home/YOU/.local/bin/uv run ai_email_sorter.py
```

Create `~/.config/systemd/user/gmailsort.timer`:

```ini
[Unit]
Description=Run Gmail AI sorting daily

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now gmailsort.timer
systemctl --user list-timers
```

Notes:

- `Persistent=true` runs a missed job as soon as the computer is back on.
- Use absolute paths, because the scheduler does not run from your project folder. `WorkingDirectory` makes `.env`, `token.json` and `client_secret.json` resolve correctly.
- Run the script by hand once first, so `token.json` already exists. A scheduled job cannot complete the browser login.
- Set `PRINT_ONLY = False` before scheduling, otherwise the job only prints and never labels.
- Check results with `journalctl --user -u gmailsort.service -n 30` and `priority.log`.

## Security

Add this to `.gitignore` before your first commit:

```gitignore
client_secret.json
token.json
.env
sort.log
priority.log
.venv/
__pycache__/
```

- `client_secret.json` identifies your app, `token.json` grants access to your mailbox, and `.env` holds your Gemini API key. Do not share them, post them in screenshots, or push them to GitHub.
- If you leak the Google files by accident, go to your Google account's [third-party access page](https://myaccount.google.com/permissions) and revoke the app's access. In Google Cloud Console, delete the OAuth client and create a new one.
- If you leak the Gemini key, delete it in Google AI Studio and create a new one.

## Resources

- [Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Gmail API reference](https://developers.google.com/workspace/gmail/api/reference/rest)
- [Gmail search operators](https://support.google.com/mail/answer/7190)
- [Gemini API documentation](https://ai.google.dev/gemini-api/docs)