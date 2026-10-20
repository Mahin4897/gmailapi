# Gmail Auto-Labeler

A small Python script that finds emails from a specific sender in your Gmail account and adds a label to them (for example, every email from `noreply@steampowered.com` gets the label `Steam`). It uses the Gmail API with OAuth, creates the label if it doesn't exist, skips emails that already have it, and writes a log of everything it does.

## Features

- Searches Gmail with the same syntax as the Gmail search box (`from:`, `-label:`, and so on)
- Creates the label automatically if it doesn't exist
- Skips emails that already have the label, so it is safe to run repeatedly
- Logs every change to the terminal and to `sort.log`
- Keeps going if a single email fails, and prints a summary at the end

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) for dependency management (plain `pip` works too)
- A Google account (Gmail)
- A Google Cloud project with the Gmail API enabled (setup below)

## Project structure

```
gmailapi/
├── main.py             # the script
├── client_secret.json  # OAuth client credentials from Google (you download this)
├── token.json          # created automatically after your first login
├── sort.log            # created automatically, log of all runs
├── pyproject.toml
└── README.md
```

`client_secret.json` and `token.json` give access to your mailbox. **Never commit them to git** (see [Security](#security)).

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

Optionally, open **Data Access** and add the scope `https://www.googleapis.com/auth/gmail.modify`. The script requests this scope itself at login, so this step is not required, but it makes the consent screen list it clearly.

### Step 4: Create the OAuth client and download `client_secret.json`

1. Go to **APIs & Services → Credentials**. In the newer console this is **Google Auth Platform → Clients**.
2. Click **Create Credentials → OAuth client ID** (or **Create client**).
3. For **Application type**, choose **Desktop app**. This is important. Other types fail with a `redirect_uri_mismatch` error.
4. Enter a name, for example `gmail-labeler-desktop`, and click **Create**.
5. A dialog shows your client ID and client secret. Click **Download JSON**.
6. Move the downloaded file into the project folder and **rename it to `client_secret.json`**. Google gives it a long name like `client_secret_123456-abc.apps.googleusercontent.com.json`, but the script looks for exactly `client_secret.json`.

If you close the dialog without downloading, you can download the JSON again from the client's page.

### Step 5: Log in for the first time

1. Run the script (see [Usage](#usage)).
2. Your browser opens a Google login page. Choose the account you added as a test user.
3. Google shows **"Google hasn't verified this app"**. This is expected for your own personal project. Click **Advanced**, then **Go to Gmail Labeler (unsafe)**.
4. Review the permission and click **Continue** or **Allow**.
5. The browser shows a message that the login completed, and a `token.json` file appears in the project folder.

Later runs reuse `token.json` and do not open the browser. The script refreshes the token automatically when it expires.

If the machine has no browser (for example a remote server), do the first login on a computer with a browser, then copy `token.json` to the other machine.

### Make the login last longer (recommended)

While the consent screen is in **Testing** mode, Google expires the login after **7 days**, and the script will fail with `invalid_grant`. For a personal tool you can fix this:

1. Go to **OAuth consent screen / Audience**.
2. Click **Publish app** to move it to **In production**.
3. Delete `token.json` and log in again.

You will still see the "unverified app" warning, and you click through it just as before. Verification is only needed if other people will use your app.

---

## Part 2: Install and run

### Install dependencies

With uv:

```bash
uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

Or, if you cloned a project that already has a `pyproject.toml`:

```bash
uv sync
```

With plain pip:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Configure the script

Open `main.py` and edit these two values:

```python
sender = "noreply@steampowered.com"   # the sender whose emails you want to label
label_name = "Steam"                  # the label to add
```

Nested labels use a slash, for example `"Games/Steam"`.

### Usage

```bash
uv run main.py
```

Example output:

```
2026-10-21 08:00:03,412 INFO Added label 'Steam' -> Your Steam receipt (id=18c2f4a9b1d3e5f7)
2026-10-21 08:00:03,901 INFO Added label 'Steam' -> New game in your wishlist (id=18c2f4a9b1d3e5f8)
2026-10-21 08:00:04,310 INFO Done: 2 labeled, 0 already had it, 0 failed
```

---

## How it works

1. **Authentication.** `get_service()` loads `token.json` if it exists and refreshes it when expired. If there is no valid token, it starts the browser login using `client_secret.json` and saves the result to `token.json`.
2. **Label lookup.** `get_or_create_label()` lists your existing labels and returns the ID of the one that matches `label_name`. If none matches, it creates it. The Gmail API works with label **IDs** (like `Label_8392011`), not names.
3. **Search.** The script searches with `from:<sender> -label:"<label>"`, so emails that already have the label are excluded from the results.
4. **Labeling.** For each message, it reads the subject and current labels, then calls `messages().modify()` with `addLabelIds`. It does not remove the email from the inbox.
5. **Logging.** Each change is logged with the subject and message ID. Errors on a single email are logged with a traceback and do not stop the run. A summary is printed at the end.

## Permissions (scope)

The script requests the `gmail.modify` scope. It lets the script read mail and change labels. It is broader than read-only access, so treat `token.json` like a password. If you only want to read mail, use `gmail.readonly` instead, but then labeling will not work.

If you change `SCOPES` in the code, **delete `token.json`** and log in again. A token keeps the permissions it was created with.

## Limitations

- A single run handles up to 500 matching emails (`maxResults=500`). Because already-labeled emails are excluded from the search, running the script again picks up the rest.
- Labels are only added. The emails stay in the inbox. To move them out of the inbox, add `"removeLabelIds": ["INBOX"]` to the `modify()` body.
- It makes two API calls per email, which is fine for hundreds of emails but slow for thousands. For large batches, collect the IDs and use `messages().batchModify()` (up to 1,000 IDs per call).

## Troubleshooting

| Problem | Cause and fix |
| --- | --- |
| `403 Request had insufficient authentication scopes` | `token.json` was created with an older scope. Delete `token.json` and run again. |
| `Error 403: access_denied` in the browser | Your account isn't listed as a test user. Add it under **Audience → Test users**. |
| `invalid_grant` or `Token has been expired or revoked` | The token expired (7 days in Testing mode) or access was revoked. Delete `token.json` and log in again. Publish the app to avoid weekly expiry. |
| `redirect_uri_mismatch` | The OAuth client is not the **Desktop app** type. Create a new Desktop app client and download its JSON. |
| `FileNotFoundError: client_secret.json` | The file is missing or has the wrong name. Rename the downloaded JSON to `client_secret.json` and place it next to `main.py`. |
| `400 Invalid label` | A label name was passed where an ID is required. Use `get_or_create_label()` to get the ID. |
| `KeyError: 'messages'` | The search returned no results. Use `results.get("messages", [])`. |
| `Gmail API has not been used in project ... or it is disabled` | The API isn't enabled for the project that owns your credentials. Enable it in **APIs & Services → Library**. |
| `uv add` fails with `Network is unreachable` | A network or DNS problem, not a project problem. Check your connection (`curl -I https://files.pythonhosted.org`) and try again. |

## Run it automatically every day (Linux, systemd)

Create `~/.config/systemd/user/gmaillabel.service`:

```ini
[Unit]
Description=Label Gmail emails

[Service]
Type=oneshot
WorkingDirectory=/home/YOU/path/to/gmailapi
ExecStart=/home/YOU/.local/bin/uv run main.py
```

Create `~/.config/systemd/user/gmaillabel.timer`:

```ini
[Unit]
Description=Run Gmail labeling daily

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now gmaillabel.timer
systemctl --user list-timers
```

`Persistent=true` runs a missed job as soon as the computer is back on. Use absolute paths, because the scheduler does not run from your project folder. Run the script by hand once first, so `token.json` already exists. A scheduled job cannot complete the browser login.

## Security

Add this to `.gitignore` before your first commit:

```gitignore
client_secret.json
token.json
sort.log
.venv/
__pycache__/
```

- `client_secret.json` identifies your app, and `token.json` grants access to your mailbox. Do not share them, post them in screenshots, or push them to GitHub.
- If you leak either file by accident, go to your Google account's [third-party access page](https://myaccount.google.com/permissions) and revoke the app's access. In Google Cloud Console, delete the OAuth client and create a new one.

## Resources

- [Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Gmail API reference](https://developers.google.com/workspace/gmail/api/reference/rest)
- [Gmail search operators](https://support.google.com/mail/answer/7190)