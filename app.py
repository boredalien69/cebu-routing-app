
import streamlit as st
import pandas as pd
import re
from geopy.geocoders import Nominatim
from sklearn.cluster import KMeans
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🛣️ Step 5: Final Optimization with Driver Assignment & Time Constraints")

REQUIRED_COLUMNS = ["Client", "Address", "Start Time", "End Time", "Time Type", "Order and Weight"]
geolocator = Nominatim(user_agent="cebu-routing-step5")

def parse_weight(text):
    match = re.search(r"(\d+(\.\d+)?)\s*kg", str(text).lower())
    return float(match.group(1)) if match else 0.0

uploaded_file = st.file_uploader("Upload your Excel delivery file", type=["xlsx"])
num_trucks = st.number_input("Number of Trucks", min_value=1, max_value=20, value=3)
start_point = st.text_input("Enter Starting Address for All Trucks", value="S Jayme St, Mandaue, 6014 Cebu")

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if list(df.columns) != REQUIRED_COLUMNS:
        st.error(f"❌ Excel must have: {REQUIRED_COLUMNS}")
        st.stop()

    df["Weight (kg)"] = df["Order and Weight"].apply(parse_weight)
    df["Full Address"] = df["Address"].astype(str) + ", Cebu, Philippines"
    df["Latitude"] = None
    df["Longitude"] = None
    df["Suggested"] = None

    failed_rows = []
    for idx, row in df.iterrows():
        addr = row["Full Address"]
        try:
            loc = geolocator.geocode(addr, timeout=10)
            if loc:
                df.at[idx, "Latitude"] = loc.latitude
                df.at[idx, "Longitude"] = loc.longitude
            else:
                backup = geolocator.geocode(row["Address"], timeout=10)
                if backup:
                    df.at[idx, "Suggested"] = backup.address
                failed_rows.append(idx)
        except:
            failed_rows.append(idx)

    valid_coords = df.dropna(subset=["Latitude", "Longitude"]).copy()

    if valid_coords.shape[0] < num_trucks:
        st.warning("⚠️ Not enough valid addresses for requested trucks.")
        st.stop()

    if "Driver" not in st.session_state:
        st.session_state.Driver = {}

    if st.checkbox("🧍‍♂️ Assign Driver Names Manually"):
        for i in range(num_trucks):
            st.session_state.Driver[i] = st.text_input(f"Driver for Truck {i + 1}", key=f"driver_{i}")

    if st.button("🚀 Final Optimization"):
        kmeans = KMeans(n_clusters=num_trucks, random_state=42)
        valid_coords["Assigned Truck"] = kmeans.fit_predict(valid_coords[["Latitude", "Longitude"]])

        # Attach driver names
        if st.session_state.Driver:
            valid_coords["Driver"] = valid_coords["Assigned Truck"].map(st.session_state.Driver)
        else:
            valid_coords["Driver"] = valid_coords["Assigned Truck"].apply(lambda x: f"Truck {x+1}")

        # Geocode the start point
        if start_point:
            plant = geolocator.geocode(start_point + ", Cebu, Philippines")
            if plant:
                start_lat = plant.latitude
                start_lon = plant.longitude
            else:
                st.error("❌ Could not locate starting point.")
                st.stop()
        else:
            st.warning("⚠️ Please enter a valid starting address.")
            st.stop()

        # Map visualization
        st.subheader("📍 Final Map with Drivers")
        m = folium.Map(location=[valid_coords["Latitude"].mean(), valid_coords["Longitude"].mean()], zoom_start=11)

        # Add plant marker
        folium.Marker(
            [start_lat, start_lon],
            popup="📦 Plant Dispatch",
            icon=folium.Icon(color='black', icon='home')
        ).add_to(m)

        # Add delivery points
        for _, row in valid_coords.iterrows():
            folium.Marker(
                [row["Latitude"], row["Longitude"]],
                popup=f"{row['Client']}<br>Driver: {row['Driver']}",
            ).add_to(m)

        st_data = st_folium(m, width=1000, height=600)

        st.download_button(
            label="📥 Download Final Route Plan",
            data=valid_coords.to_excel(index=False),
            file_name="Final_Optimized_Routes.xlsx"
        )
