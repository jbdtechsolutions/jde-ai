# jde-ai (YouTube analytics helper)

Minimal project to fetch YouTube channel analytics using Google APIs.

Setup

- Create a Python virtual environment and install requirements:

  Windows (PowerShell):
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  ```

- Place your OAuth client JSON as `client_secrets.json` next to the script.

Run

  python connect-yt.py

Notes

- If you see an ImportError for google libraries, ensure you installed them into the same Python interpreter used to run the script.
