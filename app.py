
import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from sklearn.cluster import KMeans
import folium
from streamlit_folium import st_folium
from datetime import datetime
import re

st.set_page_config(layout="wide")
st.title("📦 Cebu Delivery Route Optimization App")

REQUIRED_COLUMNS = ["Client", "Address", "Start Time", "End Time", "Time Type", "Order and Weight"]
geolocator = Nominatim(user_agent="cebu-routing-app")

def parse_weight(text):
    match = re.search(r"(\d+(\.\d+)?)\s*kg", text.lower())
    return float(match.group(1)) if match else 0.0

uploaded_file = st.file_uploader("Upload your Excel delivery file", type=["xlsx"])

api_key = st.text_input("Enter your OpenRouteService API key", type="password")
num_trucks = st.number_input("How many trucks are available?", min_value=1, max_value=20, step=1)
start_point = st.text_input("Enter dispatch/start point (e.g. '8WVX+7HC Plant, S Jayme St, Mandaue, 6014 Cebu')")

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if list(df.columns) != REQUIRED_COLUMNS:
        st.error(f"❌ Excel file must have these exact columns: {REQUIRED_COLUMNS}")
        st.stop()

    st.success("✅ File format is correct.")

    df["Weight (kg)"] = df["Order and Weight"].apply(parse_weight)
    df["Full Address"] = df["Address"].astype(str) + ", Cebu, Philippines"
    df["Latitude"] = None
    df["Longitude"] = None
    df["Suggested"] = None

    # Step 1: Attempt Geocoding
    st.subheader("Step 1: Attempt Geocoding")
    failed_rows = []

    for idx, row in df.iterrows():
        addr = row["Full Address"]
        try:
            loc = geolocator.geocode(addr, timeout=10)
            if loc:
                df.at[idx, "Latitude"] = loc.latitude
                df.at[idx, "Longitude"] = loc.longitude
            else:
                raw_loc = geolocator.geocode(row["Address"], timeout=10)
                if raw_loc:
                    df.at[idx, "Suggested"] = raw_loc.address
                    failed_rows.append(idx)
                else:
                    failed_rows.append(idx)
        except:
            failed_rows.append(idx)

    if failed_rows:
        st.warning(f"{len(failed_rows)} address(es) could not be located. Review and fix below:")

        df_failed = df.loc[failed_rows].copy()
        new_inputs = {}

        st.subheader("📍 Review Problematic Addresses")

        for idx, row in df_failed.iterrows():
            client = row["Client"]
            addr = row["Address"]
            suggested = str(row.get("Suggested", "")).strip()

            st.markdown(f"**Client:** {client}  
**Original Address:** {addr}")

            if suggested and suggested.lower() != "none":
                choice = st.selectbox(
                    f"Suggestion for '{addr}':",
                    options=[addr, suggested],
                    key=f"select_{idx}"
                )
                new_inputs[idx] = choice
            else:
                manual = st.text_input(
                    f"No suggestion for '{addr}' — enter manually:",
                    key=f"manual_{idx}"
                )
                new_inputs[idx] = manual

        if st.button("🔁 Retry Geocoding"):
            for idx, new_addr in new_inputs.items():
                if new_addr:
                    try:
                        loc = geolocator.geocode(new_addr + ", Cebu, Philippines", timeout=10)
                        if loc:
                            df.at[idx, "Latitude"] = loc.latitude
                            df.at[idx, "Longitude"] = loc.longitude
                            df.at[idx, "Full Address"] = new_addr
                    except:
                        pass

    valid_coords = df.dropna(subset=["Latitude", "Longitude"])

    if len(valid_coords) >= num_trucks:
        st.success("✅ Enough valid addresses to proceed.")
        optimize = st.button("🚀 Start Optimization")

        if optimize:
            coords = valid_coords[["Latitude", "Longitude"]].to_numpy()
            kmeans = KMeans(n_clusters=num_trucks, random_state=42).fit(coords)
            valid_coords["Assigned Truck"] = kmeans.labels_

            st.subheader("📍 Optimized Map with Routes")
            m = folium.Map(location=[valid_coords["Latitude"].mean(), valid_coords["Longitude"].mean()], zoom_start=11)

            for _, row in valid_coords.iterrows():
                folium.Marker(
                    [row["Latitude"], row["Longitude"]],
                    popup=f"{row['Client']} ({row['Address']}) - Truck {int(row['Assigned Truck']) + 1}"
                ).add_to(m)

            st_data = st_folium(m, width=1000, height=600)

            st.download_button(
                label="📥 Download Optimized Excel",
                data=valid_coords.to_excel(index=False),
                file_name="Optimized_Routes.xlsx"
            )
    else:
        st.warning("⚠️ Not enough valid addresses to run optimization. Please fix address issues first.")
