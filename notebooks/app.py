import streamlit as st
import pandas as pd

# Load harmonized extraction results
df_articles = pd.read_csv("notebooks\output_with_normalized.csv")

# Collect all unique harmonized targets
all_extracted_targets = set()
for targets_str in df_articles['normalized_text'].dropna():
    if isinstance(targets_str, str):
        targets = eval(targets_str)  # Only use eval on trusted data
    else:
        targets = targets_str
    all_extracted_targets.update(targets)
all_extracted_targets = sorted(list(all_extracted_targets))

# Define the known drug targets (could come from a curated list, e.g. UniProt, HGNC, etc.)
known_drug_targets = [
    "insulin receptor", "glucagon receptor", "GLP1R", "MTOR", "PPARγ", "TNF", "LEPR",
    # ...extend with your own list of drug targets
]

# --- APP UI ---
st.title("Gene/Protein Target Selection App")

st.subheader("Extracted Targets From Data")
st.write("These are all harmonized targets found in your dataset (read-only):")
st.write(all_extracted_targets)

st.subheader("Select Known Drug Creation Targets")
selected_targets = st.multiselect(
    "Choose drug targets for prioritization or further analysis:",
    known_drug_targets
)

st.write("### Your Selected Drug Targets")
if selected_targets:
    st.write(selected_targets)
else:
    st.write("No drug targets selected.")

