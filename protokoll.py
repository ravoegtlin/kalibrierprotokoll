#!/usr/bin/env python3
# coding: utf-8
"""
protokoll.py
Erzeugt ein Kalibrierprotokoll-PDF basierend auf Einträgen in der DB (messwerte_db.py).
Verwendung:
    python protokoll.py <kalibrierung_uid>
Voraussetzungen:
    - config.ini im gleichen Verzeichnis
    - Zugriff auf die DB wie in messwerte_db.engine konfiguriert
    - pip install reportlab matplotlib pillow
"""
import sys
import io
import configparser
from datetime import datetime, date
from statistics import mean

# Reporting / PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# Plots
import matplotlib.pyplot as plt

# DB (lokales Modul im Repo)
import messwerte_db as mdb
from sqlalchemy.orm import sessionmaker

# Helper: resolve attribute path like "lookup.seriennummer" starting from Kalibrierung instance
def resolve_path(root, path):
    if root is None:
        return None
    parts = path.split('.')
    cur = root
    for p in parts:
        if cur is None:
            return None
        # support attribute access
        if hasattr(cur, p):
            cur = getattr(cur, p)
        else:
            # try numeric index if current is list-like and p is integer index
            try:
                idx = int(p)
                cur = cur[idx]
            except Exception:
                return None
    return cur


def get_all_seriennummern(kal):
    """
    Sammelt alle eindeutigen Seriennummern aus allen DutMessungen einer Kalibrierung.
    Returns: Set von Seriennummern
    """
    seriennummern = set()
    # Iterate through all kalibrierläufe
    for attr_name in ['kalibrierlauf_lecktest', 'temperierung_23', 'kalibrierlauf_23', 
                      'temperierung_40', 'kalibrierlauf_40', 'temperierung_verify', 'kalibrierlauf_verify']:
        kl = getattr(kal, attr_name, None)
        if kl is None:
            continue
        # Iterate through all messpunkte in this kalibrierlauf
        for mp in getattr(kl, 'messpunkte', []) or []:
            # Iterate through all dut_messungen in this messpunkt
            for dm in getattr(mp, 'dut_messungen', []) or []:
                sn = getattr(dm, 'seriennummer', None)
                if sn is not None:
                    seriennummern.add(sn)
    return seriennummern


def render_plot_for_kalibrierlauf(kalibrierlauf, title=None, seriennummer=None):
    """
    Erzeugt ein Diagramm (PNG bytes) für einen Kalibrierlauf:
    x = Referenzfluss (messpunkt.flow_ref oder set_flow)
    y = Mittelwert der DutMessung.flow_device pro Messpunkt
    seriennummer: Wenn angegeben, werden nur DutMessungen mit dieser Seriennummer berücksichtigt
    """
    if kalibrierlauf is None:
        return None
    messpunkte = getattr(kalibrierlauf, 'messpunkte', []) or []
    x = []
    y = []
    for mp in messpunkte:
        # Referenzfluss aus Messpunkt (flow_ref bevorzugt, sonst set_flow)
        ref = getattr(mp, 'flow_ref', None) or getattr(mp, 'set_flow', None)
        # DutMessungen sind in mp.dut_messungen (relationship)
        dev_vals = []
        if hasattr(mp, 'dut_messungen') and mp.dut_messungen:
            for dm in mp.dut_messungen:
                # Filter by seriennummer if provided
                if seriennummer is not None:
                    dm_sn = getattr(dm, 'seriennummer', None)
                    if dm_sn != seriennummer:
                        continue
                val = getattr(dm, 'flow_device', None)
                if val is not None:
                    dev_vals.append(val)
        if ref is None:
            continue
        measured = mean(dev_vals) if dev_vals else None
        x.append(ref)
        y.append(measured if measured is not None else 0.0)
    if not x:
        return None
    # create plot
    plt.switch_backend('Agg')
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
    ax.plot(x, y, marker='o', linestyle='-', color='tab:blue', label='Gerät')
    # plot identity line if x is numeric
    try:
        ax.plot(x, x, linestyle='--', color='gray', label='Referenz = Messwert')
    except Exception:
        pass
    ax.set_xlabel('Referenz (Flow)')
    ax.set_ylabel('Gemessener Flow (Device)')
    ax.set_title(title or f"Kalibrierlauf {getattr(kalibrierlauf, 'uid', '')}")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf(uid, cfg, seriennummer=None):
    """
    Erzeugt ein PDF-Protokoll für eine Kalibrierung.
    
    Args:
        uid: Die uid der Kalibrierung
        cfg: ConfigParser-Objekt mit Mapping und Layout-Einstellungen
        seriennummer: Wenn angegeben, werden nur Daten dieser Seriennummer verwendet
    """
    # prepare DB session
    Session = sessionmaker(bind=mdb.engine)
    session = Session()
    kal = session.query(mdb.Kalibrierung).filter_by(uid=uid).one_or_none()
    if kal is None:
        raise ValueError(f"Keine Kalibrierung mit uid={uid} gefunden")
    # read mappings
    mapping = {}
    if cfg.has_section('mapping'):
        mapping = dict(cfg.items('mapping'))
    # collect mapped values
    values = {}
    for key, path in mapping.items():
        val = resolve_path(kal, path)
        # Format dates nicely
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        values[key] = val
    # Override Seriennummer with the actual seriennummer parameter if provided
    if seriennummer is not None:
        values['Seriennummer'] = str(seriennummer)
    # read plots config
    plots = {}
    if cfg.has_section('plots'):
        plots = dict(cfg.items('plots'))
    plot_images = []
    for k, path in plots.items():
        target = resolve_path(kal, path)
        buf = render_plot_for_kalibrierlauf(target, title=k, seriennummer=seriennummer)
        if buf is not None:
            plot_images.append((k, buf))
    # layout and create PDF
    output_template = cfg.get('layout', 'output_template', fallback='protokoll_{uid}.pdf')
    # Modify output template to include seriennummer if provided
    if seriennummer is not None:
        # Insert seriennummer before file extension
        import os
        base, ext = os.path.splitext(output_template)
        if not ext:
            ext = '.pdf'
        outname = f"{base}_SN{seriennummer}{ext}".format(uid=uid)
    else:
        outname = output_template.format(uid=uid)
    doc = SimpleDocTemplate(outname, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []
    # Title
    title = cfg.get('layout', 'title', fallback='Kalibrierprotokoll')
    story.append(Paragraph(f"<b>{title}</b>", styles['Title']))
    story.append(Spacer(1, 6))
    # Key metadata table from mapping (show only some relevant fields)
    meta_rows = []
    # choose an order: use mapping order if possible
    for k in mapping.keys():
        meta_rows.append([Paragraph(f"<b>{k}</b>", styles['Normal']), Paragraph(str(values.get(k, '')), styles['Normal'])])
    if meta_rows:
        t = Table(meta_rows, hAlign='LEFT', colWidths=(80*mm, 90*mm))
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.2, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))
    # Add plots
    for name, buf in plot_images:
        # convert BytesIO -> reportlab Image expects filename or a file-like with seek; pass buf directly
        img = Image(buf, width=160*mm, height=90*mm)  # scale to fit page
        story.append(Paragraph(f"<b>Diagramm: {name}</b>", styles['Heading3']))
        story.append(img)
        story.append(Spacer(1, 6))
    # Add a compact table of messpunkte and first dut measurement
    story.append(Paragraph("<b>Messpunkte (Auszug)</b>", styles['Heading3']))
    table_data = [['MP UID', 'Referenz Flow', 'Set Flow', 'Device (avg)', 'Temp in/out']]
    # iterate over kalibrierung's kalibrierläufe and collect messpunkte (limit to first 60 rows)
    rows_added = 0
    for attr_name in ['kalibrierlauf_lecktest', 'temperierung_23', 'kalibrierlauf_23', 'temperierung_40', 'kalibrierlauf_40', 'temperierung_verify', 'kalibrierlauf_verify']:
        kl = getattr(kal, attr_name, None)
        if kl is None:
            continue
        for mp in getattr(kl, 'messpunkte', []) or []:
            # avg device - filter by seriennummer if provided
            dev_vals = []
            for dm in getattr(mp, 'dut_messungen', []) or []:
                if seriennummer is not None:
                    dm_sn = getattr(dm, 'seriennummer', None)
                    if dm_sn != seriennummer:
                        continue
                val = getattr(dm, 'flow_device', None)
                if val is not None:
                    dev_vals.append(val)
            avg_dev = f"{mean(dev_vals):.3f}" if dev_vals else ''
            table_data.append([str(mp.uid),
                               f"{getattr(mp, 'flow_ref', '')}",
                               f"{getattr(mp, 'set_flow', '')}",
                               avg_dev,
                               f"{getattr(mp, 'temp_in', '')} / {getattr(mp, 'temp_out', '')}"])
            rows_added += 1
            if rows_added > 60:
                break
        if rows_added > 60:
            break
    if len(table_data) > 1:
        t2 = Table(table_data, colWidths=[18*mm, 30*mm, 30*mm, 30*mm, 45*mm])
        t2.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.2, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        story.append(t2)
    else:
        story.append(Paragraph("Keine Messpunkte gefunden.", styles['Normal']))
    # build PDF
    doc.build(story)
    print(f"PDF erzeugt: {outname}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python protokoll.py <kalibrierung_uid>")
        sys.exit(1)
    try:
        uid = int(sys.argv[1])
    except ValueError:
        print("uid muss eine Ganzzahl sein")
        sys.exit(1)
    cfg = configparser.ConfigParser()
    # preserve option case (German field names)
    cfg.optionxform = str
    cfg.read('config.ini')
    try:
        # First, get the Kalibrierung to find all seriennummern
        Session = sessionmaker(bind=mdb.engine)
        session = Session()
        kal = session.query(mdb.Kalibrierung).filter_by(uid=uid).one_or_none()
        if kal is None:
            print(f"Keine Kalibrierung mit uid={uid} gefunden")
            sys.exit(1)
        
        # Get all unique seriennummern
        seriennummern = get_all_seriennummern(kal)
        
        if not seriennummern:
            print("WARNUNG: Keine DutMessungen mit Seriennummern gefunden!")
            print("Mögliche Ursachen:")
            print("  - Die Kalibrierung enthält keine Messpunkte")
            print("  - Die Messpunkte enthalten keine DutMessungen")
            print("  - Die DutMessungen haben keine Seriennummern gesetzt")
            print("\nErstelle allgemeines Protokoll ohne Filterung nach Seriennummer.")
            generate_pdf(uid, cfg, seriennummer=None)
        else:
            print(f"Gefundene Seriennummern: {sorted(seriennummern)}")
            # Generate one PDF per seriennummer
            for sn in sorted(seriennummern):
                print(f"\nErzeuge Protokoll für Seriennummer: {sn}")
                generate_pdf(uid, cfg, seriennummer=sn)
            print(f"\n{len(seriennummern)} Protokolle erfolgreich erstellt.")
    except Exception as e:
        print("Fehler beim Erzeugen des Protokolls:", e)
        raise

if __name__ == '__main__':
    main()
