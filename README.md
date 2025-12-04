# Kalibrierprotokoll — Anleitung für protokoll.py

Kurzbeschreibung
----------------
Dieses Repository enthält ein Skript `protokoll.py`, das aus Einträgen in der lokalen Datenbank (`messwerte_db.py`) ein Kalibrierprotokoll als PDF erzeugt. Die Zuordnung, welche Datenfelder in welches Protokollfeld kommen, wird über die Datei `config.ini` gesteuert.

Voraussetzungen
---------------
- Python (siehe `Pipfile`; empfohlen wird die dort angegebene Version)
- Abhängigkeiten: `reportlab`, `matplotlib`, `pillow`, `sqlalchemy`, `pymssql`

Installation und Ausführung
--------------------------
Mit pipenv (empfohlen):
```bash
pip install pipenv
pipenv install
pipenv run python protokoll.py <kalibrierung_uid>
```

Alternativ mit pip:
```bash
pip install reportlab matplotlib pillow sqlalchemy pymssql
python protokoll.py <kalibrierung_uid>
```

Wichtige Dateien in der Branch `feature/protokoll_generierung`
-------------------------------------------------------------
- `protokoll.py` — Script zur Erzeugung des PDF-Protokolls
- `config.ini`   — Mapping-Konfiguration: Zuordnung Protokollfeld → DB-Feld
- `Pipfile`      — Pipenv-Definition der Abhängigkeiten

Konfiguration (`config.ini`)
----------------------------
Die Datei `config.ini` enthält mehrere Sektionen:

- `[mapping]`
  Hier werden Protokoll-Feldnamen auf DB-Pfade gemappt, z. B.:
  ```
  Seriennummer = lookup.seriennummer
  Datum = lookup.date
  Operator = kalibrierlauf_23.operator_name
  ```
  Pfade werden relativ zu einer `mdb.Kalibrierung`-Instanz aufgelöst (z. B. `lookup.seriennummer`, `kalibrierlauf_23.set_temp`).

- `[plots]`
  Definiert, welche Kalibrierläufe als Diagramme dargestellt werden:
  ```
  Kalibrierlauf_23 = kalibrierlauf_23
  ```

- `[layout]`
  - `output_template`: Name der Ausgabedatei, Platzhalter `{uid}` wird ersetzt (z. B. `protokoll_{uid}.pdf`)
  - `title`: Titel, der im PDF angezeigt wird

Beispielausführung
------------------
1. Branch auschecken (falls nötig):
```bash
git checkout feature/protokoll_generierung
```

2. Skript ausführen (Beispiel):
```bash
python protokoll.py 123
```
Dabei ist `123` die `uid` der Kalibrierung in der Datenbank.

Ergebnis
--------
- Es wird standardmäßig eine PDF-Datei `protokoll_<uid>.pdf` im aktuellen Verzeichnis erzeugt (konfigurierbar via `config.ini`).
- Falls keine Messpunkte oder Diagrammdaten vorhanden sind, erzeugt das Skript trotzdem ein Protokoll mit den verfügbaren Metadaten.

Wichtige Hinweise
-----------------
- Die Datenbankverbindung wird in `messwerte_db.py` konfiguriert (`engine = create_engine(...)`). Prüfe und passe die Verbindung an deine Umgebung an.
- `config.ini` verwendet Groß-/Kleinschreibung für die Keys — das Skript bewahrt die Option-Casing.
- `.gitignore` sollte Pipenv‑Artefakte ignorieren (z. B. `.venv/`, `Pipfile.lock`, `.pipenv/`).

Fehlerbehebung
--------------
- Probleme mit Plots oder PDF: Prüfe, ob `reportlab`, `matplotlib` und `pillow` installiert sind.
- DB-Verbindung: Prüfe die `engine`-URL in `messwerte_db.py` und ob dein Ausführungsumgebung Zugriff auf die DB hat.
- Bei Exceptions: Kopiere die Fehlermeldung in ein Issue oder sende sie an den Maintainer.

Mitwirken
---------
- Entwickle Änderungen in eigenen Branches gegen `feature/protokoll_generierung`.
- Ich kann bei Bedarf Layout‑Anpassungen, weitere Mapping‑Felder oder Verbesserungen direkt in diese Feature‑Branch committen.

Ende
