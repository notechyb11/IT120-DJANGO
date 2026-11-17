# Team guide (internal checklist - you can delete this file before submitting)

## 1. GitHub: getting real commit history from every member

The rubric gives 10 points for "commit history shows meaningful contributions" and
"task distribution". So each member should push their own part from their own GitHub account.

1. **Member 1** creates the GitHub repo, adds Members 2 and 3 as collaborators
   (Settings → Collaborators), then commits the project skeleton:
   `manage.py`, `sms_project/`, `sms_app/__init__.py`, `apps.py`, `models.py`, `migrations/`,
   `urls.py`, `views.py`, `admin.py`, `context_processors.py`, `.gitignore`, `requirements.txt`.
2. **Member 2** clones, then commits `forms.py`, `templates/`, `static/`.
3. **Member 3** commits `services.py`, `tests.py`, `.env.example`, `README.md`.
4. Make a few more small commits each (fix README names, tick the test table, tweak styling)
   so the history is not just three giant commits.

Before the first push, check that `.env` is **not** listed by `git status`.

```bash
git init
git add .
git status              # .env and db.sqlite3 must NOT appear
git commit -m "Set up Django project and sms_app"
git branch -M main
git remote add origin https://github.com/<group>/<repo>.git
git push -u origin main
```

## 2. Demo video script (aim for 5-7 minutes)

| Time | Who | What to show |
|---|---|---|
| 0:00 | Paul | Introduce the group, project purpose and intended users |
| 0:45 | Paul | Quick tour: Compose, History, Contacts pages; the "Twilio configured" badge |
| 1:30 | Jude | Type a verified number + message; point out counter, segments, preview |
| 2:15 | Jude | Press **Send SMS**; read the green "submitted, delivery not confirmed" message; show the phone receiving it |
| 3:00 | Jude | Validation: blank number, blank message, `12ab` |
| 3:45 | Paul | Error handling: send to an unverified number (trial error), and/or turn off Wi-Fi (network error) |
| 4:30 | Paul | History: **Check status** changes Queued → Delivered; stats and filters; Contacts page |
| 5:15 | Jude | Run `python manage.py test sms_app` and show `OK` |
| 5:45 | All | Technologies used, how credentials are kept secret (`.env` + `.gitignore`), each member's contribution |

**Do not show** the `.env` file contents, the Auth Token in the Twilio Console, or full personal phone numbers
(you can blur them while editing).

## 3. Submission email

To: prala-an@carsu.edu.ph
Subject: `Assignment_IT 120-1stSemSY26-27`

```
Dear Instructor,

We are submitting our group assignment, Build a Django Application for Sending SMS.

Group Members:
1. Paul Albaciete
2. Jude Amancio

GitHub Repository: https://github.com/notechyb11/IT120-DJANGO
Demonstration Video: [link - make sure "anyone with the link can view"]

Thank you.

Respectfully,
[Group Representative]
```

Check that the repository is **public** (or the instructor is added) and the video link opens in a private/incognito window.
