import streamlit as st
import pandas as pd
import re
from geopy.geocoders import Nominatim
from sklearn.cluster import KMeans
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("📦 Cebu Routing Optimizer – Final Version")

geolocator = Nominatim(user_agent="cebu-final-app")
REQUIRED_COLUMNS = ["Client", "Address", "Start Time", "End Time", "Time Type", "Order and Weight"]

def parse_weight(text):
    match = re.search(r"(\d+(\.\d+)?)\s*kg", str(text).lower())
    return float(match.group(1)) if match else 0.0

# Step 1: Upload
uploaded = st.file_uploader("Upload Excel file", type=["xlsx"])
if uploaded:
    df = pd.read_excel(uploaded)
    if list(df.columns) != REQUIRED_COLUMNS:
        st.error("Invalid columns. Please follow template.")
        st.stop()

    df["Weight (kg)"] = df["Order and Weight"].apply(parse_weight)
    df["Full Address"] = df["Address"].astype(str) + ", Cebu, Philippines"
    df["Latitude"] = None
    df["Longitude"] = None
    df["Suggested"] = None

    if "raw_df" not in st.session_state:
        st.session_state["raw_df"] = df.copy()
        st.session_state["fixes"] = {}
        st.session_state["failed"] = []
        st.session_state["geocode_complete"] = False
        st.session_state["retry_ready"] = False

# Step 2: Geocode
if "raw_df" in st.session_state and not st.session_state["geocode_complete"]:
    df = st.session_state["raw_df"]
    failed = []
    for idx, row in df.iterrows():
        try:
            loc = geolocator.geocode(row["Full Address"], timeout=10)
            if loc:
                df.at[idx, "Latitude"] = loc.latitude
                df.at[idx, "Longitude"] = loc.longitude
            else:
                backup = geolocator.geocode(row["Address"], timeout=10)
                if backup:
                    df.at[idx, "Suggested"] = backup.address
                failed.append(idx)
        except:
            failed.append(idx)
    st.session_state["raw_df"] = df
    st.session_state["failed"] = failed
    st.session_state["geocode_complete"] = True

# Step 3: Fix Panel
if st.session_state.get("failed"):
    df = st.session_state["raw_df"]
    st.warning("Some addresses could not be geocoded. Please review them below.")

    for idx in st.session_state["failed"]:
        row = df.loc[idx]
        st.markdown(f"**Client:** {row['Client']} — `{row['Address']}`")
        suggestion = row.get("Suggested")
        if suggestion and suggestion.strip().lower() != "none":
            selected = st.selectbox(
                f"Suggested fix for '{row['Client']}'",
                [row["Address"], suggestion],
                key=f"dropdown_{idx}"
            )
            st.session_state["fixes"][idx] = selected
        else:
            manual = st.text_input(
                f"Enter fixed address for '{row['Client']}'",
                key=f"manual_{idx}"
            )
            if manual:
                st.session_state["fixes"][idx] = manual

    if st.button("🔁 Retry Geocoding"):
        df = st.session_state["raw_df"]
        fixes = st.session_state["fixes"]
        still_failed = []
        for idx, new_addr in fixes.items():
            try:
                loc = geolocator.geocode(new_addr + ", Cebu, Philippines", timeout=10)
                if loc:
                    df.at[idx, "Latitude"] = loc.latitude
                    df.at[idx, "Longitude"] = loc.longitude
                    df.at[idx, "Full Address"] = new_addr
                else:
                    still_failed.append(idx)
            except:
                still_failed.append(idx)
        st.session_state["raw_df"] = df
        st.session_state["failed"] = still_failed
        if not still_failed:
            st.success("✅ All addresses fixed.")
        else:
            st.warning("Some addresses still failed.")
        st.session_state["retry_ready"] = True

# Step 4: Final Optimization
if st.session_state.get("geocode_complete") and not st.session_state.get("failed"):
    df = st.session_state["raw_df"]
    st.subheader("🚛 Route Optimization")

    num_trucks = st.number_input("Number of Trucks", 1, 20, 3)
    dispatch = st.text_input("Enter starting address", "S Jayme St, Mandaue, 6014 Cebu")
    assign = st.checkbox("Assign driver names?")

    if assign:
        drivers = {}
        for i in range(num_trucks):
            drivers[i] = st.text_input(f"Driver for Truck {i+1}", key=f"driver_{i}")
    else:
        drivers = {i: f"Truck {i+1}" for i in range(num_trucks)}

    if st.button("🚀 Optimize Now"):
        valid = df.dropna(subset=["Latitude", "Longitude"]).copy()
        if valid.shape[0] < num_trucks:
            st.warning("Not enough addresses to form clusters.")
            st.stop()
        kmeans = KMeans(n_clusters=num_trucks, random_state=42)
        valid["Assigned Truck"] = kmeans.fit_predict(valid[["Latitude", "Longitude"]])
        valid["Driver"] = valid["Assigned Truck"].map(drivers)

        # Get dispatch coordinates
        plant = geolocator.geocode(dispatch + ", Cebu, Philippines")
        if plant:
            start_lat, start_lon = plant.latitude, plant.longitude
        else:
            st.error("❌ Could not locate dispatch address.")
            st.stop()

        st.subheader("🗺️ Delivery Map")
        m = folium.Map(location=[valid["Latitude"].mean(), valid["Longitude"].mean()], zoom_start=11)
        folium.Marker([start_lat, start_lon], popup="Dispatch Point", icon=folium.Icon(color="black")).add_to(m)

        for _, row in valid.iterrows():
            folium.Marker(
                [row["Latitude"], row["Longitude"]],
                popup=f"{row['Client']}<br>Driver: {row['Driver']}"
            ).add_to(m)

        st_folium(m, width=1000, height=600)

        st.download_button(
            label="📥 Download Optimized Routes",
            data=valid.to_excel(index=False),
            file_name="Final_Optimized_Routes.xlsx"
        )
