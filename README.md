# GarageBook

GarageBook is a web app for tracking vehicle maintenance and expenses.

Built by Evgeny and Sanya using Python and Django.

## Current status

The Django project is set up. Vehicle and maintenance features are coming next.

## Run locally

Requires Python 3.13 and Git.

1. Clone this repository and open its folder in a terminal.
2. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

3. Install dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Set up the local database:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate
   ```

5. Start the development server:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver
   ```

6. Open http://127.0.0.1:8000/ in a browser.

Press Ctrl+C in the terminal to stop the server.
