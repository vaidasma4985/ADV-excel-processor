from __future__ import annotations

import streamlit as st

from processor import process_excel


def main() -> None:
    st.set_page_config(page_title="Excel komponentų apdorojimas", layout="wide")
    st.title("Excel komponentų apdorojimas")

    uploaded = st.file_uploader("Įkelk Excel failą", type=["xlsx"])

    if uploaded is None:
        st.info("Įkelk Excel (.xlsx) failą, tada spausk „Apdoroti failą“.")
        return

    if st.button("Apdoroti failą"):
        try:
            cleaned_df, removed_df, out_bytes, stats = process_excel(uploaded.getvalue())

            st.subheader("Statistika")
            st.write(f"Įvesties eilučių: **{stats['input_rows']}**")
            st.write(f"Cleaned eilučių: **{stats['cleaned_rows']}**")
            st.write(f"Removed eilučių: **{stats['removed_rows']}**")

            st.subheader("Apdoroti duomenys (Cleaned)")
            st.dataframe(cleaned_df, use_container_width=True)

            st.subheader("Ištrintos eilutės (Removed)")
            if removed_df.empty:
                st.info("Ištrintų eilučių nėra.")
            else:
                st.dataframe(removed_df, use_container_width=True)

            st.download_button(
                label="Atsisiųsti rezultatą (Excel)",
                data=out_bytes,
                file_name="processed_components.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except ValueError as e:
            st.error(f"Klaida: {e}")
        except Exception as e:
            st.error(f"Įvyko netikėta klaida apdorojant failą: {e}")


if __name__ == "__main__":
    main()
