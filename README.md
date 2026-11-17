# Django SMS Sender

**IT 120 – Integrative Programming and Technologies · Group Assignment**

A Django web application that lets a user send SMS messages through the **Twilio** SMS gateway.
The user enters a recipient's phone number and a message; the app validates the input, submits
the message to Twilio's API, and shows clear success or failure feedback. Every attempt is saved
so the user can review the history and check whether a message was actually delivered.

**Intended users:** anyone who needs to send a quick text from a browser, for example a teacher
sending announcements to verified class officers or a small office sending reminders.

---

## Group members and responsibilities

| Member | Role | Main files |
|---|---|---|
| **Paul Albaciete** | Django project setup, models, views, URLs, application logic, Twilio SMS integration, secure configuration | `sms_project/settings.py`, `sms_project/urls.py`, `sms_app/models.py`, `sms_app/views.py`, `sms_app/urls.py`, `sms_app/services.py`, `.env.example` |
| **Jude Amancio** | User interface, forms, input validation, user feedback, testing, documentation, demo video | `sms_app/forms.py`, `sms_app/templates/`, `sms_app/static/`, `sms_app/tests.py`, `README.md` |

> Both members understand and can explain the whole application.

---

## Main features

### Core
- **SMS form** with recipient phone number, message box and **Send SMS** button.
- **Input validation** (server side, in `forms.py`):
  - empty phone number / empty or whitespace-only message are rejected;
  - phone numbers are checked and converted to the international E.164 format Twilio needs
    (`0917 123 4567` → `+639171234567`);
  - letters, misplaced `+` signs, numbers that are too short or too long are rejected;
  - messages over 1,600 characters (Twilio's limit) are rejected.
- **Twilio integration** in one module (`services.py`) using the official `twilio` Python library.
- **Error handling** with readable messages for: missing credentials, wrong credentials,
  unverified trial recipients, invalid numbers, blocked countries, unsubscribed recipients,
  carrier spam filtering, network failures and timeouts, and any other provider error.
  Error messages never include credentials or raw provider responses.
- **Honest status reporting:** after sending, the app says the message was *submitted* to the
  provider and that delivery is **not yet confirmed**. Only Twilio's `delivered` status is shown
  as delivered.

### Additional features
1. **Message history dashboard** (`/history/`) with counts of all, pending, delivered and failed
   attempts, plus filters.
2. **Message status tracking:** a *Check status* button asks Twilio for the latest status
   (queued → sent → delivered / undelivered / failed).
3. **Contact management** (`/contacts/`): save, pick and delete recipients.
4. **Character and segment counter** that shows how many SMS parts the message will use
   (GSM 160/153 chars, Unicode 70/67 chars).
5. **Live message preview** in a phone-style bubble.
6. **Double-submit protection:** the button is disabled while sending, and the page redirects
   after a successful send (Post/Redirect/Get) so refreshing does not send the SMS again.

---

## SMS workflow

```
User opens app ──► enters phone number ──► composes message ──► clicks "Send SMS"
                                                                     │
                                         Django form validation (forms.py)
                                     invalid │                    │ valid
                       show error under the field          services.send_sms()
                       (nothing is sent)                          │
                                                   Twilio REST API (messages.create)
                                             error │                         │ accepted
                        save attempt as "Not sent" +            save attempt with Twilio SID +
                        show friendly error message             status "Queued"; show "submitted,
                                                                delivery not confirmed yet"
                                                                             │
                                                     History page ─► "Check status" ─► Twilio
                                                     (sent / delivered / undelivered / failed)
```

---

## Technologies and dependencies

| Technology | Purpose |
|---|---|
| Python 3.12 | Programming language |
| Django 6.1 | Web framework (views, forms, templates, ORM, CSRF protection, messages) |
| twilio 9.x | Official Twilio Python library for the SMS API |
| python-dotenv | Loads secrets from a local `.env` file into environment variables |
| SQLite | Stores message history and contacts |
| Bootstrap 5.3 + Bootstrap Icons (CDN) | Layout and styling |
| Vanilla JavaScript | Character counter, preview, contact picker |

Exact versions are in `requirements.txt`.

### Project structure

```
sms_project/
├── manage.py
├── requirements.txt
├── .env.example            # placeholder settings - copy to .env
├── .gitignore              # keeps .env, venv and db.sqlite3 out of Git
├── sms_project/
│   ├── settings.py         # reads all secrets from environment variables
│   └── urls.py
└── sms_app/
    ├── models.py           # Contact, SMSMessage
    ├── forms.py            # SMSForm, ContactForm, phone validation
    ├── services.py         # all Twilio code + error translation
    ├── views.py            # compose, history, refresh_status, contacts
    ├── urls.py
    ├── admin.py
    ├── context_processors.py
    ├── tests.py            # 39 automated tests (Twilio is mocked)
    ├── templates/sms_app/  # base, compose, history, contacts
    └── static/sms_app/     # css/style.css, js/compose.js
```

---

## Installation and setup

**Requirements:** Python 3.12+ and Git.

```bash
git clone https://github.com/<your-group>/<your-repo>.git
cd <your-repo>

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

# Create your local settings file
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux

python manage.py migrate
```

Optional, for the Django admin at `/admin/`:

```bash
python manage.py createsuperuser
```

---

## Configuring the SMS provider (Twilio)

1. Sign up at <https://www.twilio.com/try-twilio> (a free trial is enough).
2. In the **Twilio Console** home page, under *Account Info*, find your **Account SID** and
   **Auth Token**.
3. Get a sender: **Phone Numbers → Manage → Buy a number** (trial accounts get one free number
   with SMS capability). Alternatively, create a **Messaging Service** and use its SID.
4. **Trial accounts can only text verified numbers.** Add each test recipient under
   **Phone Numbers → Manage → Verified Caller IDs**.
5. If texting Philippine numbers, make sure the Philippines is allowed under
   **Messaging → Settings → Geo permissions**.
6. Open your `.env` file and fill in:

   ```
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_FROM_NUMBER=+1...          # or set TWILIO_MESSAGING_SERVICE_SID instead
   DJANGO_SECRET_KEY=...             # any long random string
   ```

7. Restart the server. The badge in the top-right corner changes to **Twilio configured**.

### Security practices
- Credentials live only in environment variables / the local `.env` file; `settings.py` reads them
  with `os.environ`. Nothing secret is hard-coded.
- `.env` and `db.sqlite3` are in `.gitignore`; only `.env.example` (placeholders) is committed.
- All forms use Django's CSRF protection (`{% csrf_token %}`); state-changing actions
  (send, check status, delete) accept POST only.
- Error messages shown to users never include the auth token or raw API responses.
- Message preview uses `textContent`, and templates use Django auto-escaping, to prevent XSS.
- Do not show the `.env` file or the Twilio Console's Auth Token in the demo video.

---

## Running the application

```bash
venv\Scripts\activate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

| Page | URL |
|---|---|
| Compose / send SMS | `/` |
| History dashboard | `/history/` |
| Contacts | `/contacts/` |
| Django admin | `/admin/` |

---

## Testing

### Automated tests

```bash
python manage.py test sms_app
```

The 39 tests replace Twilio with a mock, so they never send real SMS or need credentials. They
cover validation, phone number conversion, segment counting, every error type in `services.py`,
all views, CSRF enforcement, history statistics and filters, status refresh and contacts.

**Result:** `Ran 39 tests ... OK`

### Manual test cases (from the assignment)

| # | Test case | Input | Expected result | Actual result | Pass? |
|---|---|---|---|---|---|
| 1 | Valid phone number and message | `+639XXXXXXXXX` (verified), "Hello from Django" | Sends request, shows provider response | Green alert: "submitted to the SMS provider (status: Queued). Delivery is not confirmed yet"; SMS received on phone | ☐ |
| 2 | Empty phone number | phone blank, "Hello" | Rejected, validation message | "Please enter the recipient's phone number." under the field; nothing sent | ☐ |
| 3 | Empty message | valid phone, message blank | Rejected, validation message | "The message cannot be empty." under the field; nothing sent | ☐ |
| 4 | Invalid phone number | `12ab` / `+63123` | Validation error | "may only contain digits..." / "Invalid phone number..." | ☐ |
| 5 | Unverified number on trial | real but unverified number | Provider rejection handled | Red alert: "trial account can only send to verified numbers..." | ☐ |
| 6 | Missing credentials | empty `TWILIO_AUTH_TOKEN` in `.env` | Error without exposing secrets | Red alert: "The SMS provider is not configured. Missing setting(s): TWILIO_AUTH_TOKEN..." | ☐ |
| 7 | Incorrect credentials | wrong `TWILIO_AUTH_TOKEN` | Error without exposing secrets | Red alert: "The SMS provider rejected our credentials..." | ☐ |
| 8 | Network error | disconnect Wi-Fi, then send | Understandable failure message | Red alert: "Could not connect to the SMS provider..." | ☐ |
| 9 | Successful response | after test 1 | Confirms submission, does not claim delivery | Status "Queued"; after **Check status**, changes to "Delivered" | ☐ |

> Tick each box after your group runs the test, and update "Actual result" if anything differs.

---

## Known limitations

- **Twilio trial restrictions:** only verified recipient numbers, and messages start with
  "Sent from your Twilio trial account".
- **Status is refreshed manually** with the *Check status* button. Automatic updates would need a
  Twilio status-callback webhook, which requires a public HTTPS URL (e.g. after deployment or
  with ngrok).
- **No user login:** anyone who can open the site can send messages and see history. Fine for a
  local class demo; a real deployment should add authentication and rate limiting.
- Segment count shown before sending is an estimate; Twilio's actual count is saved after sending.
- Phone-number checks verify the format only. Whether the number exists is decided by Twilio.
