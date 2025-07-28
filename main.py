import sys
import os
import csv
import json
from PyQt5.QtWidgets import QApplication
from gui import MainWindow
from stream_monitor import StreamMonitor

CHANNELS_FILE = os.path.join(os.getcwd(), "channels.json")

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        # create default channels.json file if it doesn't exist
        default_channels = [
            {
                "name": "Test Channel",
                "url": "YOUR_TEST_STREAM_URL_HERE",
                "db_name": "incidents_test.db"
            }
        ]
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_channels, f, indent=4)
    
    with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_channels(channels):
    with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(channels, f, indent=4)

def export_incidents_to_csv(db_name):
    db_path = os.path.join(os.getcwd(), "data", db_name)
    csv_path = os.path.join(os.getcwd(), "data", db_name.replace(".db", ".csv"))
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as fin, open(csv_path, "w", encoding="utf-8", newline='') as fout:
            writer = csv.writer(fout)
            writer.writerow(["Date", "Time", "Type", "Message"])
            for line in fin:
                if line.strip():
                    parts = [p.strip() for p in line.strip().split("|", 2)]
                    if len(parts) == 3:
                        dateheure, typ, msg = parts
                        if " " in dateheure:
                            date, heure = dateheure.split(" ", 1)
                        else:
                            date, heure = dateheure, ""
                        writer.writerow([date, heure, typ, msg])
                    else:
                        writer.writerow(["", "", "", line.strip()])

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        
        channels = load_channels()
        if not channels:
            print("The channels.json file is empty or doesn't exist. Please add a channel.")
            sys.exit(1)

        # we no longer create a monitor here, we just pass the channel list
        window = MainWindow(channels)
        window.show()
        exit_code = app.exec_()
        
        # shutdown handling is now done in the main window
        sys.exit(exit_code)
    except Exception as e:
        import traceback
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print("A critical error occurred. See crash.log for details.")
        sys.exit(1)
 
        