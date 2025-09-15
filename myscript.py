# ===================================================================
# ==       PAIR-BASED, CLEAN OUTPUT COMPILER (v8 - With Sorting)   ==
# ==          (Sorts the final master file by PART_NO)             ==
# ===================================================================
import streamlit as st
import pandas as pd
import os
import zipfile
import tempfile
import shutil
from collections import defaultdict
from io import BytesIO

st.set_page_config(layout="wide")
st.title('🗂️ Pair-Based, Sorting & Compiling Tool')
st.info(
    "This tool creates a clean zip file containing one master CSV for each folder, sorted by the 'PART_NO' column."
)

# --- UI for File Upload ---
with st.sidebar:
    st.header('1. Upload Your Data')
    st.write("Upload a .zip file containing your constituency folders.")
    uploaded_zip = st.file_uploader("Upload CSV Data (.zip)", type="zip")

st.header('2. Run the Compilation Process')

if st.button('🚀 Start Compilation', type="primary", disabled=(not uploaded_zip)):
    with tempfile.TemporaryDirectory() as temp_dir:
        # --- Unzip ---
        with st.spinner('Extracting zip file...'):
            try:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except Exception as e:
                st.error(f"Error extracting zip file: {e}"); st.stop()

        extracted_contents = os.listdir(temp_dir)
        base_path = os.path.join(temp_dir, extracted_contents[0]) if len(extracted_contents) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_contents[0])) else temp_dir

        clean_output_path = os.path.join(temp_dir, "clean_output_for_zip")
        os.makedirs(clean_output_path)

        # --- PHASE 1: Global Scan and Reporting ---
        st.subheader("Part 1: Finding and Grouping File Pairs")
        with st.spinner("Scanning all folders to identify matching pairs..."):
            file_map = defaultdict(lambda: defaultdict(dict))
            for root, _, files in os.walk(base_path):
                for filename in files:
                    if filename.endswith('_e_detail.csv'):
                        base = filename.replace('_e_detail.csv', '')
                        file_map[root][base]['detail'] = os.path.join(root, filename)
                    elif filename.endswith('_e_sup.csv'):
                        base = filename.replace('_e_sup.csv', '')
                        file_map[root][base]['sup'] = os.path.join(root, filename)
            
            total_pairs_found = sum(1 for bases in file_map.values() for paths in bases.values() if 'detail' in paths and 'sup' in paths)
        
        st.success(f"Grouping complete. Found {total_pairs_found} unique pairs to process across all folders.")
        
        # --- PHASE 2: Two-Step Compilation ---
        st.subheader("Part 2: Processing, Concatenating, and Saving Files")
        progress_bar = st.progress(0, text="Starting compilation...")
        
        folders_to_process = list(file_map.keys())
        total_folders = len(folders_to_process)
        summary_data = []

        for i, folder_path in enumerate(folders_to_process):
            folder_name = os.path.basename(folder_path)
            progress_bar.progress((i + 1) / total_folders, text=f"Processing Folder: {folder_name}")
            st.markdown(f"--- \n#### Folder: `{folder_name}`")

            compiled_pair_files_paths = []
            pairs_in_folder = 0

            # Step A: Compile each pair
            for base_name, paths in file_map[folder_path].items():
                if 'detail' in paths and 'sup' in paths:
                    pairs_in_folder += 1
                    try:
                        df_detail = pd.read_csv(paths['detail'], low_memory=False)
                        df_sup = pd.read_csv(paths['sup'], low_memory=False)
                        compiled_pair_df = pd.concat([df_detail, df_sup], ignore_index=True)
                        output_filename = f"{base_name}_COMPILED.csv"
                        output_path = os.path.join(folder_path, output_filename)
                        compiled_pair_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                        compiled_pair_files_paths.append(output_path)
                        st.write(f"  - Pair `{base_name}`: Compiled -> `{output_filename}` ({len(compiled_pair_df):,} rows).")
                    except Exception as e:
                        st.warning(f"  - Could not process pair `{base_name}`: {e}")
            
            # Step B: Compile and sort the folder's master file
            master_file_rows = 0
            if compiled_pair_files_paths:
                master_df_list = [pd.read_csv(f, low_memory=False) for f in compiled_pair_files_paths]
                if master_df_list:
                    final_master_df = pd.concat(master_df_list, ignore_index=True)

                    # ==================== NEW SORTING LOGIC ====================
                    if 'PART_NO' in final_master_df.columns:
                        # Convert to numeric to ensure correct sorting (1, 2, 10) not (1, 10, 2)
                        final_master_df['PART_NO'] = pd.to_numeric(final_master_df['PART_NO'], errors='coerce')
                        final_master_df = final_master_df.sort_values(by='PART_NO', ascending=True)
                        st.write(f"  - Sorting master file by 'PART_NO' column.")
                    else:
                        st.warning(f"  - 'PART_NO' column not found. Skipping sort for this folder.")
                    # ==========================================================

                    master_file_rows = len(final_master_df)
                    clean_subfolder_path = os.path.join(clean_output_path, folder_name)
                    os.makedirs(clean_subfolder_path, exist_ok=True)
                    new_master_filename = f"{folder_name}_compiled_file.csv"
                    final_output_path = os.path.join(clean_subfolder_path, new_master_filename)
                    final_master_df.to_csv(final_output_path, index=False, encoding='utf-8-sig')
                    st.success(f"✅ **Folder Master**: Created `{new_master_filename}` ({master_file_rows:,} rows).")
            else:
                st.info("No complete pairs found in this folder to create a master file.")

            summary_data.append({"Folder": folder_name, "Pairs Found": pairs_in_folder, "Master Rows": master_file_rows})

        progress_bar.empty()
        st.markdown("---")
        
        # --- Summary Report ---
        st.header("3. Compilation Summary")
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        col1, col2 = st.columns(2)
        col1.metric("Total Folders with Pairs", f"{len(summary_df[summary_df['Pairs Found'] > 0])}")
        col2.metric("Grand Total Rows in All Master Files", f"{summary_df['Master Rows'].sum():,}")

        # --- Zipping and Download ---
        st.header("4. Download Your Compiled Data")
        with st.spinner("Zipping clean results for download..."):
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, _, files in os.walk(clean_output_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        archive_name = os.path.relpath(file_path, clean_output_path)
                        zip_file.write(file_path, archive_name)

        st.download_button(
            label="📥 Download Clean Compiled Data (.zip)",
            data=zip_buffer,
            file_name="clean_compiled_folders.zip",
            mime="application/zip",
            type="primary"
        )
else:
    st.info("Please upload a zip file to begin the compilation process.")
