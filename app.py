from __future__ import annotations

import streamlit as st
import pandas as pd

from processor import process_excel


def main() -> None:
    st.set_page_config(
        page_title="Excel komponentų apdorojimas",
        layout="wide",
    )

    st.title("Excel komponentų apdorojimas")

    uploaded_file = st.file_uploader(
        "Įkelk Excel failą", type=["xlsx"]
    )

    if uploaded_file is None:
        st.info(
            "Norėdami pradėti, įkelkite Excel (.xlsx) failą, kuriame yra "
            "stulpeliai: **Name**, **Type**, **Quantity**, **Group Sorting**."
        )
        return

    if st.button("Apdoroti failą"):
        try:
            file_bytes = uploaded_file.getvalue()

            cleaned_df, removed_df, output_bytes = process_excel(file_bytes)

            total_rows = len(cleaned_df) + len(removed_df)

            st.subheader("Santrauka")
            st.write(f"Bendras eilučių skaičius: **{total_rows}**")
            st.write(f"Eilučių „Cleaned“ lape: **{len(cleaned_df)}**")
            st.write(f"Eilučių „Removed“ lape: **{len(removed_df)}**")

            st.subheader("Apdoroti duomenys (Cleaned)")
            st.dataframe(cleaned_df)

            st.subheader("Ištrintos eilutės (Removed)")
            if len(removed_df) == 0:
                st.info("Nė viena eilutė nebuvo pašalinta.")
            else:
                st.dataframe(removed_df)

            st.download_button(
                label="Atsisiųsti rezultatą (Excel)",
                data=output_bytes,
                file_name="processed_components.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
            )

        except ValueError as e:
            # Missing or invalid columns
            st.error(
                "Trūksta privalomų stulpelių arba neteisinga failo struktūra. "
                f"Patikrink stulpelius: {e}"
            )
        except Exception as e:
            # Generic error, but still readable
            st.error(
                "Įvyko netikėta klaida apdorojant failą. "
                f"Detalės (techninė informacija): {e}"
            )


if __name__ == "__main__":
    main()
