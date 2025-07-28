import cv2
import numpy as np
import threading
import time
import logging
from datetime import datetime
import os
import csv
import ffmpeg
import io
import wave
import numpy as np
import content_moderation
from PyQt5.QtCore import QObject, pyqtSignal

class StreamMonitor(QObject):
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, stream_url, db_name, channel_name):
        super().__init__()
        self.stream_url = stream_url
        self.db_name = db_name
        self.channel_name = channel_name
        self.status = "INIT"
        self.incidents = []
        self.running = False
        self.logger = logging.getLogger(f"StreamMonitor-{channel_name}")
        self.logger.setLevel(logging.INFO)
        # Chaque moniteur aura son propre fichier de log
        handler = logging.FileHandler(f"stream_events_{channel_name.lower().replace(' ', '_')}.log", encoding="utf-8")
        self.logger.addHandler(handler)
        self.frame_callback = None  # Pour envoyer les frames à la GUI
        self.last_frame = None
        self.last_status = None
        self.frozen_count = 0
        self.black_count = 0
        self.error_count = 0
        self.silence_threshold = 25  # Seuil RMS pour le silence (ajusté pour éviter les faux positifs)

    

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
        last_audio_check = 0
        silence_detected = False
        timeout_count = 0
        audio_timeout_count = 0  # Compteur de timeouts consécutifs
        try:
            while self.running:
                try:
                    now = time.time()
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
                    # Détection silence audio (analyse toutes les 2 minutes avec silencedetect)
                    if now - last_audio_check > 120:
                        last_audio_check = now
                        try:
                            import subprocess
                            # Utilisation de silencedetect sur 5s
                            cmd = [
                                'ffmpeg', '-y', '-i', self.stream_url,
                                '-af', 'silencedetect=noise=-40dB:d=10',
                                '-t', '3',  # Durée analysée réduite à 3s
                                '-f', 'null', '-'
                            ]
                            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7)
                            audio_timeout_count = 0  # Reset si succès
                            # Correction : proc.stderr est déjà str si text=True
                            err_str = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode('utf-8', errors='ignore')
                            # Chercher la durée du silence détecté
                            import re
                            silences = re.findall(r'silence_start: (.*?)\n|silence_end: (.*?) \| silence_duration: (.*?)\n', err_str)
                            silence_long = False
                            for silence in silences:
                                if silence[2]:
                                    try:
                                        duration = float(silence[2])
                                        self._log_event(f"Silence detected: {duration:.1f}s")
                                        if duration >= 10:
                                            silence_long = True
                                    except Exception:
                                        pass
                            if silence_long and not silence_detected:
                                self._set_status("SILENCE AUDIO")
                                self._log_event("Audio silence detected (>10s)")
                                silence_detected = True
                            elif not silence_long:
                                silence_detected = False
                        except subprocess.TimeoutExpired:
                            audio_timeout_count += 1
                            # hide timeout log except if 3 consecutive
                            if audio_timeout_count >= 3:
                                self._log_event('Warning: 3 consecutive timeouts on audio analysis (silencedetect)')
                            continue  # don't block, continue to next
                        except Exception as e:
                            self._log_event(f'Audio analysis error (silencedetect): {e}')
                    # in the image analysis loop (where you analyze frames for black screen, frozen, etc.)
                    unsafe_score = content_moderation.detect_nsfw(frame)
                    if unsafe_score > 0.8:
                        self._log_event('Inappropriate content detected (NSFW)')
                        self.add_incident('NSFW', 'Inappropriate content detected (NSFW)')
                    forbidden = content_moderation.detect_forbidden_text(frame)
                    if forbidden:
                        self._log_event(f'Forbidden text detected: {forbidden}')
                        self.add_incident('FORBIDDEN TEXT', f'Forbidden text detected: {forbidden}')
                    # unauthorized_logo = content_moderation.detect_unauthorized_logo(frame)
                    # if unauthorized_logo:
                    #     self._log_event('Logo non autorisé détecté')
                    #     self.add_incident('LOGO', 'Logo non autorisé détecté')
                    # if everything is ok
                    if self.black_count == 0 and self.frozen_count == 0 and not silence_detected:
                        self._set_status("OK")
                    # send frame to GUI
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
            self._log_event(f"Status change: {status}")
            self.status_signal.emit(status) # Emit signal instead of direct call
            self.last_status = status
            if status != "OK":
                self.add_incident(status, f"Incident detected on stream {self.channel_name}.")

    def _log_event(self, msg):
        self.logger.info(f"{datetime.now().isoformat()} - {msg}")
        self.log_signal.emit(f"{datetime.now().strftime('%H:%M:%S')} - {msg}") # Emit signal instead of direct call

    def add_incident(self, incident_type, message):
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        heure_str = now.strftime('%H:%M:%S')
        incident_str = f"{date_str} {heure_str} | {incident_type} | {message}"
        self.incidents.append(incident_str)
        # save to data/db_name
        data_dir = os.path.join(os.getcwd(), "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        db_path = os.path.join(data_dir, self.db_name)
        with open(db_path, "a", encoding="utf-8") as f:
            f.write(incident_str + "\n")
        # real-time recording in csv_name
        csv_path = os.path.join(data_dir, self.db_name.replace(".db", ".csv"))
        write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
        with open(csv_path, "a", encoding="utf-8", newline='') as fout:
            writer = csv.writer(fout)
            if write_header:
                writer.writerow(["Date", "Heure", "Type", "Message"])
            writer.writerow([date_str, heure_str, incident_type, message])
        print(incident_str)

    def export_report(self):
        if self.incidents:
            # export TXT
            with open(f"incidents_report_{self.channel_name.lower().replace(' ', '_')}.txt", "w", encoding="utf-8") as f:
                for incident in self.incidents:
                    f.write(f"{incident}\n")
            # export CSV
            with open(f"incidents_report_{self.channel_name.lower().replace(' ', '_')}.csv", "w", encoding="utf-8") as f:
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