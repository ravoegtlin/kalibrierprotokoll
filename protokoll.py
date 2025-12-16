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
import os
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
    Sammelt alle eindeutigen Seriennummern aus kalibrierlauf_verify DutMessungen.
    Returns: Set von Seriennummern
    """
    seriennummern = set()
    # Only use kalibrierlauf_verify for protocols
    kl = getattr(kal, 'kalibrierlauf_verify', None)
    if kl is None:
        return seriennummern
    # Iterate through all messpunkte in kalibrierlauf_verify
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
    output_template = cfg.get('layout', 'output_template', fallback='rohdaten_{uid}.pdf')
    # Modify output template to include seriennummer if provided
    if seriennummer is not None:
        # Insert seriennummer before file extension
        base, ext = os.path.splitext(output_template)
        if not ext:
            ext = '.pdf'
        outname = f"{base}_{seriennummer}{ext}".format(uid=uid)
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
    # Add a compact table of messpunkte from kalibrierlauf_verify
    story.append(Paragraph("<b>Messpunkte (Auszug)</b>", styles['Heading3']))
    table_data = [['MP UID', 'Referenz Flow', 'Set Flow', 'Device (avg)', 'Temp in/out']]
    # Only use kalibrierlauf_verify for protocols (limit to first 60 rows)
    rows_added = 0
    kl = getattr(kal, 'kalibrierlauf_verify', None)
    if kl is not None:
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


def generate_protokoll_pdf(uid, seriennummer):
    """
    Erzeugt ein Kalibrierprotokoll-PDF mit Kopfdaten.
    
    Args:
        uid: Die uid der Kalibrierung
        seriennummer: Die Seriennummer des Geräts
    """
    # prepare DB session
    Session = sessionmaker(bind=mdb.engine)
    session = Session()
    kal = session.query(mdb.Kalibrierung).filter_by(uid=uid).one_or_none()
    if kal is None:
        raise ValueError(f"Keine Kalibrierung mit uid={uid} gefunden")
    
    # Find the Lookup entry for this Kalibrierung
    lookup = None
    for lk in kal.lookups:
        if str(lk.seriennummer) == str(seriennummer):
            lookup = lk
            break
    
    if lookup is None:
        print(f"WARNUNG: Kein Lookup-Eintrag für Seriennummer {seriennummer} gefunden. Verwende ersten Lookup.")
        if kal.lookups:
            lookup = kal.lookups[0]
    
    # Collect statistics from kalibrierlauf_verify
    kl = getattr(kal, 'kalibrierlauf_verify', None)
    if kl is None:
        raise ValueError("Kein kalibrierlauf_verify gefunden")
    
    # Collect pressure, temperature values from messpunkte
    pressure_in_values = []
    pressure_out_values = []
    temp_amb_values = []
    temp_in_values = []
    
    for mp in getattr(kl, 'messpunkte', []) or []:
        if mp.pressure_in is not None and mp.pressure_in != 0.0:
            pressure_in_values.append(mp.pressure_in)
        if mp.pressure_out is not None and mp.pressure_out != 0.0:
            pressure_out_values.append(mp.pressure_out)
        if mp.temp_amb is not None and mp.temp_amb != 0.0:
            temp_amb_values.append(mp.temp_amb)
        if mp.temp_in is not None and mp.temp_in != 0.0:
            temp_in_values.append(mp.temp_in)
    
    # Create PDF
    outname = f"protokoll_{uid}_{seriennummer}.pdf"
    doc = SimpleDocTemplate(outname, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    story.append(Paragraph("<b>Kalibrierergebnis:</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    
    # Header table
    header_data = []
    header_data.append(['<b>Station</b>', 'KS05 / A5 / 37'])
    
    # Datum from Lookup
    if lookup and lookup.date and lookup.time:
        datum_str = f"{lookup.date.strftime('%Y.%m.%d')} {lookup.time.strftime('%H:%M:%S')}"
    elif lookup and lookup.date:
        datum_str = lookup.date.strftime('%Y.%m.%d')
    else:
        datum_str = 'N/A'
    header_data.append(['<b>Datum</b>', datum_str])
    
    # Typ - always the same
    header_data.append(['<b>Typ</b>', 'Smart 6 / GSxxxxA_xxxx____'])
    
    # Gas
    gas_str = lookup.gas if lookup and lookup.gas else 'N/A'
    header_data.append(['<b>Gas</b>', gas_str])
    
    # Seriennummer
    header_data.append(['<b>Seriennummer</b>', str(seriennummer)])
    
    # Eingangsdruck (min / avg / max)
    if pressure_in_values:
        min_p = min(pressure_in_values)
        max_p = max(pressure_in_values)
        avg_p = mean(pressure_in_values)
        pressure_in_str = f"{min_p:.3f} / {avg_p:.3f} / {max_p:.3f} Bar"
    else:
        pressure_in_str = 'N/A'
    header_data.append(['<b>Eingangsdruck</b>', pressure_in_str])
    
    # Ausgangsdruck (min / avg / max)
    if pressure_out_values:
        min_p = min(pressure_out_values)
        max_p = max(pressure_out_values)
        avg_p = mean(pressure_out_values)
        pressure_out_str = f"{min_p:.3f} / {avg_p:.3f} / {max_p:.3f} Bar"
    else:
        pressure_out_str = 'N/A'
    header_data.append(['<b>Ausgangsdruck</b>', pressure_out_str])
    
    # Kammertemperatur (min / max)
    if temp_amb_values:
        min_t = min(temp_amb_values)
        max_t = max(temp_amb_values)
        temp_amb_str = f"{min_t:.1f} / {max_t:.1f} °C"
    else:
        temp_amb_str = 'N/A'
    header_data.append(['<b>Kammertemperatur</b>', temp_amb_str])
    
    # Plattentemperatur (min / max)
    if temp_in_values:
        min_t = min(temp_in_values)
        max_t = max(temp_in_values)
        temp_in_str = f"{min_t:.1f} / {max_t:.1f} °C"
    else:
        temp_in_str = 'N/A'
    header_data.append(['<b>Plattentemperatur</b>', temp_in_str])
    
    # DATA Eintrag
    data_eintrag = f"[DATA{lookup.dat_file_sektions_nr_verify}]" if lookup and hasattr(lookup, 'dat_file_sektions_nr_verify') and lookup.dat_file_sektions_nr_verify is not None else 'N/A'
    header_data.append(['<b>DATA Eintrag</b>', data_eintrag])
    
    # LOOKUP Eintrag
    lookup_eintrag = f"[LOOKUP{lookup.dat_file_sektions_nr:02d}]" if lookup and hasattr(lookup, 'dat_file_sektions_nr') and lookup.dat_file_sektions_nr is not None else 'N/A'
    header_data.append(['<b>LOOKUP Eintrag</b>', lookup_eintrag])
    
    # Create table
    header_table = Table(header_data, colWidths=[50*mm, 120*mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Add note
    note_text = """<i>Hinweis: Wenn 2 Zahlenwerte angegeben sind, sind diese Minimum und Maximum,<br/>
    bei drei Werten sind es Minimum, Mittelwert und Maximum.</i>"""
    story.append(Paragraph(note_text, styles['Normal']))
    
    # build PDF
    doc.build(story)
    print(f"Protokoll PDF erzeugt: {outname}")


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
            # Generate PDFs per seriennummer
            for sn in sorted(seriennummern):
                print(f"\nErzeuge Rohdaten für Seriennummer: {sn}")
                generate_pdf(uid, cfg, seriennummer=sn)
                print(f"Erzeuge Protokoll für Seriennummer: {sn}")
                generate_protokoll_pdf(uid, seriennummer=sn)
            print(f"\n{len(seriennummern)} Rohdaten- und Protokoll-PDFs erfolgreich erstellt.")
    except Exception as e:
        print("Fehler beim Erzeugen des Protokolls:", e)
        raise

if __name__ == '__main__':
    main()
