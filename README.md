# Shop Billing Machine (Browser App)

A local browser-based billing and inventory app for a small shop.

## Features
- Products, selling prices, GST and stock quantity
- Billing cart and totals
- Save bill permanently in SQLite; stock automatically reduces on saved bill
- Excel export with Stock, Bills and Bill Items sheets
- WhatsApp click-to-chat with bill text prefilled; user reviews and taps Send
- Data survives closing/reopening the app as long as `billing_data.db` is retained

## Windows setup
1. Install Python 3.10+ from https://www.python.org/downloads/ (enable "Add Python to PATH").
2. Extract this ZIP to a folder.
3. Open Command Prompt in that folder.
4. Run:
   ```bat
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. Browser opens at `http://localhost:8501`.

## Backup
Copy `billing_data.db` somewhere safe regularly. The Excel button exports current records but the database is the app's persistent working data.

## Access from multiple devices
This starter runs on one computer. To access it from other devices on the same network, run:
```bat
streamlit run app.py --server.address 0.0.0.0
```
Then browse to `http://<host-computer-LAN-IP>:8501`. Keep the host computer on and protect the network. For internet access / multi-user concurrent use, deploy to a server and use managed persistent storage rather than a local SQLite file.

## WhatsApp
The button opens WhatsApp with a prefilled message. It does not auto-send. Fully automated sending requires the official WhatsApp Business Platform and credentials/approval; do not put credentials in this app's source.
