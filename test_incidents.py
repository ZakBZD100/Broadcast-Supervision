import sys
import os
import csv
import gui 
import stream_monitor 

import cv2
import numpy as np
import threading
import time
import logging
from datetime import datetime
import os
import csv

class StreamMonitor:
    def __init__(self):
        self.stream_url = "https://cdn.live.easybroadcast.io/abr_corp/83_medi1tv-maghreb_jnbspmg/corp/83_medi1tv-maghreb_jnbspmg_1080p/chunks_dvr.m3u8"
        self.status = "INIT"
        self.incidents = []
        self.running = False
        self.logger = logging.getLogger("StreamMonitor")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler("stream_events.log", encoding="utf-8")
        self.logger.addHandler(handler)
        self.frame_callback = None  # to send frames to GUI
        self.status_callback = None # to send status to GUI
        self.log_callback = None    # to send logs to GUI
        self.last_frame = None
        self.last_status = None
        self.frozen_count = 0
        self.black_count = 0
        self.error_count = 0

    # black screen test
    def test_incidents(self):
        self.start()
        time.sleep(10)
        self.stop()
        self.export_report()
        bstest = cv2.imread("data/frame.jpg")
        mean_pixel = np.mean(bstest)
        if mean_pixel < 10:
            self.black_count += 1
        if self.black_count > 10:
            self._set_status("BLACK SCREEN TEST")
            self._log_event("Black screen test detected.")
        else:
            self.black_count = 0
                        
    def set_callbacks(self, frame_cb, status_cb, log_cb):
        self.frame_callback = frame_cb
        self.status_callback = status_cb
        self.log_callback = log_cb

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()

    def monitor_loop(self):
        cap = None
        try:
            while self.running:
                try:
                    if cap is None or not cap.isOpened():
                        try:
                            cap = cv2.VideoCapture(self.stream_url)
                            if not cap.isOpened():
                                self._set_status("ERROR")
                                self._log_event("Stream inaccessible")
                                self.error_count += 1
                                time.sleep(5)
                                continue
                        except Exception as e:
                            self._set_status("ERROR")
                            self._log_event(f"Stream opening error: {e}")
                            self.error_count += 1
                            time.sleep(5)
                            continue
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        self._set_status("ERROR")
                        self._log_event("Connection loss or empty frame")
                        self.error_count += 1
                        time.sleep(2)
                        continue
                    # Détection écran noir
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    mean_pixel = np.mean(gray)
                    if mean_pixel < 10:
                        self.black_count += 1
                        if self.black_count > 10:
                            self._set_status("BLACK SCREEN")
                            self._log_event("Black screen detected")
                    else:
                        self.black_count = 0
                    # Détection image figée
                    if self.last_frame is not None:
                        diff = cv2.absdiff(frame, self.last_frame)
                        nonzero = np.count_nonzero(diff)
                        if nonzero < 1000:
                            self.frozen_count += 1
                            if self.frozen_count > 10:
                                self._set_status("LAG")
                                self._log_event("Frozen frame detected")
                        else:
                            self.frozen_count = 0
                    self.last_frame = frame.copy()
                    # Si tout va bien
                    if self.black_count == 0 and self.frozen_count == 0:
                        self._set_status("OK")
                    # Envoi de la frame à la GUI
                    if self.frame_callback:
                        try:
                            self.frame_callback(frame)
                        except Exception as cb_err:
                            self._log_event(f"Frame callback error: {cb_err}")
                    time.sleep(0.5)
                except Exception as loop_err:
                                            self._log_event(f"Exception in monitor_loop: {loop_err}")
                    time.sleep(2)
        except Exception as fatal_err:
                                    self._log_event(f"Fatal crash of monitor_loop thread: {fatal_err}")
        finally:
            if cap:
                cap.release()

    def _set_status(self, status):
        if status != self.last_status:
            self.status = status
            if self.status_callback:
                try:
                    self.status_callback(status)
                except Exception as cb_err:
                                            self._log_event(f"Status callback error: {cb_err}")
            self.last_status = status
            if status != "OK":
                now = datetime.now()
                date_str = now.strftime('%Y-%m-%d')
                heure_str = now.strftime('%H:%M:%S')
                incident_str = f"{date_str} {heure_str} | {status} | Incident detected on stream Medi1TV."
                self.incidents.append(incident_str)
                # Enregistrer dans data/incidents.db
                data_dir = os.path.join(os.getcwd(), "data")
                if not os.path.exists(data_dir):
                    os.makedirs(data_dir)
                db_path = os.path.join(data_dir, "incidents.db")
                with open(db_path, "a", encoding="utf-8") as f:
                    f.write(incident_str + "\n")
                # Enregistrement temps réel dans incidents.csv
                csv_path = os.path.join(data_dir, "incidents.csv")
                write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
                with open(csv_path, "a", encoding="utf-8", newline='') as fout:
                    writer = csv.writer(fout)
                    if write_header:
                        writer.writerow(["Date", "Heure", "Type", "Message"])
                    writer.writerow([date_str, heure_str, status, "Incident detected on stream Medi1TV."])
                print(incident_str)

    def _log_event(self, msg):
        self.logger.info(f"{datetime.now().isoformat()} - {msg}")
        if self.log_callback:
            try:
                self.log_callback(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")
            except Exception as cb_err:
                self._log_event(f"Log callback error: {cb_err}")

    def export_report(self):
        if self.incidents:
            # Export TXT
            with open("incidents_report.txt", "w", encoding="utf-8") as f:
                for incident in self.incidents:
                    f.write(f"{incident}\n")
            # Export CSV
            with open("incidents_report.csv", "w", encoding="utf-8") as f:
                f.write("date,heure,incident\n")
                for incident in self.incidents:
                    # incident format: 2025-06-01T12:34:56.789123 - STATUS
                    try:
                        dt, status = incident.split(" - ", 1)
                        date, heure = dt.split("T")
                        heure = heure.split(".")[0]  # remove microseconds
                        f.write(f"{date},{heure},{status}\n")
                    except Exception:
                        f.write(f",,{incident}\n") 