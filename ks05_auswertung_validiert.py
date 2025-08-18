import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import tkinter as tk
from tkinter import filedialog
import argparse
import os

def create_overview(input_file, pdf):
    data = pd.read_csv(input_file)

    # Filter last 25 rows per sollwert for DUT means
    dut_columns = [f'dut{i}_durchfluss' for i in range(1, 16)]
    grouped_dut = data.groupby('sollwert').apply(lambda g: g.tail(25)[dut_columns].mean())

    # Filter last row per sollwert for Molbloc
    molbloc_values = data.groupby('sollwert').tail(1).set_index('sollwert')['mittelwert']

    # Calculate deviations
    deviations = {}
    for dut in dut_columns:
        deviations[dut] = ((grouped_dut[dut] - molbloc_values) / molbloc_values) * 100

    deviations_df = pd.DataFrame(deviations)

    # Calculate Spec lines
    sollwerts = deviations_df.index
    max_sollwert = sollwerts.max()
    spec_pos = ((0.005 * sollwerts) + (0.003 * max_sollwert)) / sollwerts * 100
    spec_neg = -1 * spec_pos

    # Plotting
    fig, ax = plt.subplots(figsize=(15, 8))
    for dut in dut_columns:
        ax.plot(sollwerts, deviations_df[dut], marker='o', markersize=3, label=dut)

    ax.plot(sollwerts, spec_pos, 'r--', label='Spec +')
    ax.plot(sollwerts, spec_neg, 'r--', label='Spec -')

    ax.set_title('Kalibrierergebnis')
    ax.set_xlabel('Sollwert')
    ax.set_ylabel('Abweichung v.M. in %')
    ax.set_ylim(-5, 5)
    ax.set_xlim(left=0)
    ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close()

    # Prepare data for Excel export (transposed and sorted descending)
    deviations_df['Spec +'] = spec_pos
    deviations_df['Spec -'] = spec_neg
    result_df = deviations_df.T[sollwerts.sort_values(ascending=False)]

    return result_df

def create_details(input_files, pdf, excel_writer):
    order = [2, 0, 1]
    headings = ["Verify", "23°-Daten", "40°-Daten"]

    for i in order:
        input_file = input_files[i]
        heading = headings[order.index(i)]
        data = pd.read_csv(input_file)

        fig, axs = plt.subplots(3, 2, figsize=(15, 10))
        fig.suptitle(heading, fontsize=16)

        axs[0, 0].plot(data.index, data['temperatur_platte_eingang'], label='Eingang')
        axs[0, 0].plot(data.index, data['temperatur_platte_ausgang'], label='Ausgang')
        axs[0, 0].plot(data.index, data['temperatur_platte_links'], label='Platte Links')
        axs[0, 0].plot(data.index, data['temperatur_platte_rechts'], label='Platte Rechts')
        axs[0, 0].plot(data.index, data['temperatur_umgebung'], label='Umgebung')
        axs[0, 0].plot(data.index, data['temperatur_versorgung'], label='Versorgung')
        axs[0, 0].plot(data.index, data['regloplas_istwert'], label='Regloplas Istwert')
        axs[0, 0].set_title('Temperaturen')
        axs[0, 0].legend(loc='upper left', bbox_to_anchor=(1.05, 1))

        for j in range(1, 16):
            axs[0, 1].plot(data.index, data[f'dut{j}_temperatur'], label=f'DUT{j}')
        axs[0, 1].set_title('DUT Temperaturen')
        axs[0, 1].legend(loc='upper left', bbox_to_anchor=(1.05, 1))

        axs[1, 0].plot(data.index, data['sollwert'], label='Sollwert')
        axs[1, 0].set_title('Sollwert')
        axs[1, 0].legend(loc='upper left', bbox_to_anchor=(1.05, 1))

        for j in range(1, 16):
            axs[1, 1].plot(data.index, data[f'dut{j}_durchfluss'], label=f'DUT{j}')
        axs[1, 1].set_title('DUT Flow')
        axs[1, 1].legend(loc='upper left', bbox_to_anchor=(1.05, 1))

        if 'letzter_messwert' in data.columns and 'mittelwert' in data.columns:
            axs[2, 0].plot(data.index, data['letzter_messwert'], label='Letzter Messwert')
            axs[2, 0].plot(data.index, data['mittelwert'], label='Mittelwert')
            axs[2, 0].set_title('Molbloc')
            axs[2, 0].legend(loc='upper left', bbox_to_anchor=(1.05, 1))

        fig.delaxes(axs[2, 1])
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()

    def split_blocks(df, column):
        blocks = []
        current = []
        last_val = object()
        for idx, val in df[column].items():
            if val != last_val:
                if current:
                    blocks.append(current)
                current = []
                last_val = val
            current.append(idx)
        if current:
            blocks.append(current)
        return blocks

    def process_grouped(data):
        blocks = split_blocks(data, 'sollwert')
        grouped = {}
        counter = {}
        for block in blocks:
            block_df = data.loc[block]
            for sollwert, group in block_df.groupby('sollwert'):
                label = str(sollwert)
                if label in counter:
                    counter[label] += 1
                    label = f"{label}_{counter[label]}"
                else:
                    counter[label] = 0
                grouped[label] = group['letzter_messwert'].tail(25).mean()
        return grouped

    grouped_23 = process_grouped(pd.read_csv(input_files[0]))
    grouped_40 = process_grouped(pd.read_csv(input_files[1]))

    data_verify = pd.read_csv(input_files[2])
    blocks_verify = split_blocks(data_verify, 'sollwert')
    verify_columns = ['letzter_messwert'] + [f'dut{i}_durchfluss' for i in range(1, 16)]
    verify_rows = {col: {} for col in verify_columns}
    counter_verify = {}

    for block in blocks_verify:
        block_df = data_verify.loc[block]
        for sollwert, group in block_df.groupby('sollwert'):
            label = str(sollwert)
            if label in counter_verify:
                counter_verify[label] += 1
                label = f"{label}_{counter_verify[label]}"
            else:
                counter_verify[label] = 0
            for col in verify_columns:
                verify_rows[col][label] = group[col].tail(25).mean()

    all_columns_23_40 = list(dict.fromkeys(
        list(grouped_23.keys()) +
        list(grouped_40.keys())
    ))

    row_23 = [grouped_23.get(col, None) for col in all_columns_23_40]
    row_40 = [grouped_40.get(col, None) for col in all_columns_23_40]

    excel_data_23_40 = pd.DataFrame(
        [row_23, row_40],
        index=['23°-Daten', '40°-Daten'],
        columns=all_columns_23_40
    )

    all_columns_verify = list(dict.fromkeys(
        [key for row in verify_rows.values() for key in row.keys()]
    ))

    verify_data_rows = [[row.get(col, None) for col in all_columns_verify] for row in verify_rows.values()]

    excel_data_verify = pd.DataFrame(
        verify_data_rows,
        index=verify_columns,
        columns=all_columns_verify
    )

    excel_data_23_40.to_excel(excel_writer, sheet_name='Data', startrow=0)
    excel_data_verify.to_excel(excel_writer, sheet_name='Data', startrow=len(excel_data_23_40) + 2)

def main():
    parser = argparse.ArgumentParser(description="Process calibration data and generate a report.")
    parser.add_argument("-f", "--find-files", action="store_true", help="Automatically find input files (alles.csv) in subdirectories and use default output names (protokoll.pdf/.xlsx).")
    parser.add_argument("-T", dest="file_23", help="Path to 23° data file (*.csv)")
    parser.add_argument("-H", dest="file_40", help="Path to 40° data file (*.csv)")
    parser.add_argument("-V", dest="file_verify", help="Path to verify data file (*.csv)")
    parser.add_argument("-P", dest="pdf_output", help="Path to save the output PDF report (e.g., report.pdf)")
    parser.add_argument("-E", dest="excel_output", help="Path to save the output Excel file (e.g., report.xlsx)")
    args = parser.parse_args()

    if args.find_files and (args.file_23 or args.file_40 or args.file_verify or args.pdf_output or args.excel_output):
        parser.error("-f/--find-files cannot be used with manual path arguments (-T, -H, -V, -P, -E).")

    if args.find_files:
        # Auto-find logic
        search_dir = '.'
        found_paths = {'23': None, '40': None, 'verify': None}

        try:
            with os.scandir(search_dir) as it:
                for entry in it:
                    if not entry.is_dir():
                        continue

                    name_lower = entry.name.lower()
                    if 'temp' in name_lower:
                        continue

                    csv_path = os.path.join(entry.path, 'alles.csv')
                    if not os.path.isfile(csv_path):
                        continue

                    if '23' in name_lower and not found_paths['23']:
                        found_paths['23'] = csv_path
                    if '40' in name_lower and not found_paths['40']:
                        found_paths['40'] = csv_path
                    if 'verify' in name_lower and not found_paths['verify']:
                        found_paths['verify'] = csv_path
        except FileNotFoundError:
            print(f"Error: Could not scan directory '{os.path.abspath(search_dir)}'. It might not exist.")
            return

        file_23 = found_paths['23']
        file_40 = found_paths['40']
        file_verify = found_paths['verify']

        if not all([file_23, file_40, file_verify]):
            print("Error: Could not automatically find all required input files using -f.")
            if not file_23: print("- 23° file ('alles.csv' in a directory with '23' in its name) not found.")
            if not file_40: print("- 40° file ('alles.csv' in a directory with '40' in its name) not found.")
            if not file_verify: print("- Verify file ('alles.csv' in a directory with 'verify' in its name) not found.")
            return

        input_files = [file_23, file_40, file_verify]
        output_pdf = 'protokoll.pdf'
        output_excel = 'protokoll.xlsx'
    else:
        # Manual path logic
        if args.pdf_output and not args.pdf_output.lower().endswith('.pdf'):
            print(f"Error: The PDF output file specified with -P must have a .pdf extension. Provided: {args.pdf_output}")
            return

        if args.excel_output and not args.excel_output.lower().endswith(('.xlsx', '.xls')):
            print(f"Error: The Excel output file specified with -E must have an .xlsx or .xls extension. Provided: {args.excel_output}")
            return

        root = tk.Tk()
        root.withdraw()

        # --- Input files ---
        file_23 = args.file_23
        if not file_23:
            file_23 = filedialog.askopenfilename(title="Select 23° Data", initialdir="\\\\ks05-dev.kem-muc.local\\config\\messdaten", filetypes=[("CSV Files", "*.csv")])
        if not file_23:
            print("No input file selected for 23° Data. Exiting.")
            return

        file_40 = args.file_40
        if not file_40:
            file_40 = filedialog.askopenfilename(title="Select 40° Data", initialdir="\\\\ks05-dev.kem-muc.local\\config\\messdaten", filetypes=[("CSV Files", "*.csv")])
        if not file_40:
            print("No input file selected for 40° Data. Exiting.")
            return

        file_verify = args.file_verify
        if not file_verify:
            file_verify = filedialog.askopenfilename(title="Select Verify Data", initialdir="\\\\ks05-dev.kem-muc.local\\config\\messdaten", filetypes=[("CSV Files", "*.csv")])
        if not file_verify:
            print("No input file selected for Verify Data. Exiting.")
            return

        input_files = [file_23, file_40, file_verify]

        # --- Output files ---
        output_pdf = args.pdf_output
        if not output_pdf:
            output_pdf = filedialog.asksaveasfilename(title="Save Output PDF File As", defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not output_pdf:
            print("No output file selected for PDF. Exiting.")
            return

        output_excel = args.excel_output
        if not output_excel:
            output_excel = filedialog.asksaveasfilename(title="Save Output Excel File As", defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if not output_excel:
            print("No output file selected for Excel. Exiting.")
            return

    with PdfPages(output_pdf) as pdf, pd.ExcelWriter(output_excel) as writer:
        result_df = create_overview(input_files[2], pdf)
        result_df.to_excel(writer, sheet_name='Result')
        create_details(input_files, pdf, writer)

    print(f"Processed PDF saved to {output_pdf}")
    print(f"Processed Excel saved to {output_excel}")

if __name__ == "__main__":
    main()
