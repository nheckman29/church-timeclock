# Woolsey Baptist Church Time Clock

Employees clock in and out with a PIN on a tablet. The office gets a finished biweekly
timesheet instead of transcribing punch cards by hand.

Built to be boring and long-lived: a React + Tailwind frontend talking to a small Flask
JSON API over SQLite. No ORM, no auth library, no state management library. The Python
side has two dependencies, `Flask` and `waitress`.

**One process in production.** Flask serves the API under `/api` and the built React app
(`frontend/dist/`) for every other URL. The built files are committed, so the church
computer only needs Python. Node is only needed when you change the UI.

## Setup

```bash
cd church-timeclock
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python run.py
```

## Changing the UI

```bash
# Terminal 1: the API
./.venv/bin/python run.py

# Terminal 2: the UI with hot reload, at http://localhost:5173
cd frontend
npm install        # first time only
npm run dev
```

The dev server forwards `/api` calls to Flask on port 8080. When you are done, run
`npm run build` and commit `frontend/dist/` along with your source changes. Flask serves
whatever is in `dist/`, so a change you forget to build will not show up on the tablet.

The first run creates `timeclock.db` and prints a randomly generated office PIN:

```
====================================================
  First run. Your office (admin) PIN is: 418203
  Write it down, then change it under Settings.
====================================================

Time clock running. On this machine:  http://localhost:8080
From the tablet or another computer:  http://192.168.1.42:8080
```

Open the second URL on the tablet, log in to the office area, change the admin PIN under
Settings, set the pay period start date to the first day of any known pay period, and add
your employees.

Override the port with `PORT=9000 ./.venv/bin/python run.py`.

## Daily use

**Employees** tap their PIN and press Enter. There is no "in" or "out" button: the app
decides based on their last punch, which removes the most common source of bad data. The
screen confirms in a green box ("Jane Smith clocked in at 8:34AM") or a red one ("Jane
Smith clocked out at 12:32PM"), then returns to the keypad after 10 seconds or when they
tap **Return**. The **Time Card Access** button opens a PIN-protected view of that
employee's hours for the current Sunday–Saturday week, including daily totals and elapsed
time for an active shift. The previous and next arrows let employees review other weeks.

The same screen works from a personal phone or laptop on the church network: open
`http://<machine-ip>:8080/`. Laptops can type the PIN on the keyboard and press Enter.

**The office** opens `/admin`. The dashboard shows every employee's total hours for the
selected pay period, with arrows to move between periods.

## Running payroll

1. Open the office area and select the pay period.
2. Clear any missed punches flagged in the red banner.
3. Click **Download Hours Summary**. One line per employee with total hours: the file you
   key into payroll.
4. Click **Download Timesheet Report** and **Download Backup**, then save both somewhere
   other than this machine.

The timesheet report opens in Excel and lists all 14 days of the period for every
employee, Sunday through Saturday, with each clock in and clock out to the minute, the
hours for each shift in both H:MM and decimal, and a period total per employee. Days
with no punches still appear, so gaps are visible.

## Missed punches

A forgotten clock-out is the most likely failure in any PIN kiosk, and it fails quietly:
the shift never closes, so those hours vanish from the export. Everything below keys off a
single setting, **longest possible shift** (default 16 hours), configurable under Settings.
An unfinished punch older than that is treated as a missed punch.

- **At the kiosk.** If Jane forgets to clock out Tuesday and taps her PIN Wednesday
  morning, the app does *not* close a 23-hour shift. It starts a fresh shift, leaves
  Tuesday's punch open, and tells her to see the office.
- **On every office page.** A red banner lists each missed punch with a link straight to
  the screen that fixes it.
- **At export.** Exporting a period that still contains missed punches is blocked. You can
  override it, but you have to click through a page that names every affected shift.
- **On the timesheet.** Unfinished shifts show as **OPEN** in red at zero hours.

To fix one, open the employee, use **Add Missed Punch** for the time they actually left,
or correct an existing punch under **Correct Punches**.

Someone who is clocked in right now is also an open shift, but it is not a missed punch and
it does not block exports.

## How hours are calculated

Exact minutes, no rounding. Each clock-in pairs with the next clock-out, so lunch breaks
and split shifts work with no extra setup. Unpaired punches are kept and shown rather than
dropped, so bad data stays visible instead of silently changing someone's total.

There is no overtime split. The export reports total hours and payroll applies its own
overtime rules.

Pay periods are 14 days counted from the start date in Settings, so they never drift.

## Backups

Everything lives in one file, `timeclock.db`. **Download Backup** under the office menu
writes a consistent copy you can save anywhere. Do this after every payroll run and keep it
off this machine. To restore, stop the app, drop the backup file in next to `app.py` named
`timeclock.db`, and start it again.

## Security, honestly

PINs are stored as keyed hashes, so they are not readable at a glance in the database file.
That is the real extent of the protection. A 4-digit PIN cannot be made cryptographically
strong, and the deterministic hash is what lets the database enforce unique PINs, which
matters more day to day: two employees sharing a PIN would make punches ambiguous.

The security boundary is physical and network access to the church machine. A PIN kiosk
cannot prove who pressed the keys, exactly like the punch-card machine it replaces.

The app serves plain HTTP with PIN-only admin access, which is fine on a trusted church
network. **Do not forward this port to the internet** without adding TLS and stronger admin
authentication.

## Known limitation: daylight saving

Times are stored as local wall-clock time. A shift crossing the 2:00 AM DST change twice a
year would compute incorrectly. Church shifts are daytime, so this is a deliberate trade
for much simpler code. If overnight shifts ever become routine, the fix is to store UTC and
convert for display.

## Before you trust it with a paycheck

Run the punch-card machine alongside this app for one or two pay periods and reconcile the
two. It is the cheapest possible check that the hours are right.

## Files

All business rules live in Python. The frontend only displays what the API returns,
including preformatted times and hours, so it never does date math.

| File | Purpose |
| --- | --- |
| `app.py` | All `/api` routes (kiosk, office, exports) and serving the React app |
| `db.py` | SQLite helpers and settings |
| `timecalc.py` | Pairing punches, totalling hours, pay periods, display formatting. Pure functions |
| `reports.py` | Builds the CSV downloads. Pure functions |
| `alerts.py` | Missed-punch detection |
| `schema.sql` | Three tables: employees, punches, settings |
| `run.py` | Starts the server for everyday use |
| `frontend/src/main.jsx` | Every URL and the page it shows |
| `frontend/src/api.js` | The one function that calls the API, plus a `useApi` loading hook |
| `frontend/src/pages/` | One component per screen: `Kiosk`, `Login`, `Dashboard`, `EmployeeDetail`, `Employees`, `Settings`, `ExportCheck` |
| `frontend/src/components/` | `AdminLayout` (office nav and missed-punch banner) and `Notice` |
| `frontend/src/index.css` | Brand colors and the shared button, input and card styles |
| `frontend/public/` | Church logos |
| `frontend/dist/` | Built output that Flask serves. Regenerate with `npm run build` |

To rebrand, replace the logos in `frontend/public/`, change the colors at the top of
`frontend/src/index.css`, then `npm run build`.

## Tests

```bash
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest tests -q
```

The tests cover the API, the time math, and the reports. The frontend has no separate
test suite; its screens are thin enough that the API tests carry the risk.

## Autostart

**macOS.** Save as `~/Library/LaunchAgents/org.church.timeclock.plist`, then
`launchctl load ~/Library/LaunchAgents/org.church.timeclock.plist`. Replace the paths.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>org.church.timeclock</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/CHURCH/church-timeclock/.venv/bin/python</string>
    <string>/Users/CHURCH/church-timeclock/run.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/CHURCH/church-timeclock</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

**Windows.** Create a `start-timeclock.bat`:

```bat
cd /d C:\church-timeclock
.venv\Scripts\python.exe run.py
```

Then add it in Task Scheduler with the trigger "At startup" and "Run whether user is logged
on or not".

**The tablet.** Open the office URL in Chrome and use Add to Home Screen, or any kiosk
browser app, pointed at `http://<machine-ip>:8080/`. Turn off the screen timeout.
