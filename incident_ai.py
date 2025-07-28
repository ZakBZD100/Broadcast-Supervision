import os
import collections

def analyser_incidents(incidents_path):
    recommandations = []
    if not os.path.exists(incidents_path):
        return ["No incidents detected. System stable."]
    
    # incident analysis
    types = collections.Counter()
    with open(incidents_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                parts = line.strip().split('|', 2)
                if len(parts) >= 2:
                    incident_type = parts[1].strip()
                    types[incident_type] += 1
    total = sum(types.values())
    if total == 0:
        return ["No incidents detected. System stable."]
    # recommendations based on incident types
    if types['BLACK SCREEN'] > 3:
        recommandations.append("Multiple black screens detected: check video source, cabling or network connection.")
    if types['LAG'] > 3:
        recommandations.append("Multiple frozen frames: monitor bandwidth or stream stability.")
    if types['ERROR'] > 2:
        recommandations.append("Frequent errors: check stream accessibility and network configuration.")
    if types['SILENCE AUDIO'] > 2:
        recommandations.append("Repeated audio silence: check source audio track and sound level.")
    if not recommandations:
        recommandations.append("No critical recurring issues detected. System generally stable.")
    return recommandations

if __name__ == "__main__":
    recos = analyser_incidents("data/incidents.db")
    for reco in recos:
        print("-", reco) 