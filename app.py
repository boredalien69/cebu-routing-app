import streamlit as st
import pandas as pd
import re
from geopy.geocoders import Nominatim

st.set_page_config(layout="wide")
st.title("📍 Step 3 (Rebuilt): Persistent Geocoding Fixes")

REQUIRED_COLUMNS = ["Client", "Address", "Start Time", "End Time", "Time Type", "Order and Weight"]
geolocator = Nominatim(user_agent="cebu-routing-rebuilt")

def parse_weight(text):
    match = re.search(r"(\d+(\.\d+)?)\s*kg", str(text).lower())
    return float(match.group(1)) if match else 0.0

# Step 1: File upload and validation
uploaded_file = st.file_uploader("Upload Excel delivery file", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if list(df.columns) != REQUIRED_COLUMNS:
        st.error(f"❌ Excel must contain: {REQUIRED_COLUMNS}")
        st.stop()

    df["Weight (kg)"] = df["Order and Weight"].apply(parse_weight)
    df["Full Address"] = df["Address"].astype(str) + ", Cebu, Philippines"
    df["Latitude"] = None
    df["Longitude"] = None
    df["Suggested"] = None

    # Step 2: Only geocode once unless reset
    if "geocode_results" not in st.session_state:
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
        st.session_state["geocode_df"] = df
        st.session_state["geocode_failed"] = failed_rows
        st.session_state["geocode_fixes"] = {}

    df = st.session_state["geocode_df"]
    failed_rows = st.session_state["geocode_failed"]

    st.subheader("📄 Uploaded Data")
    st.dataframe(df)

    if failed_rows:
        st.warning(f"{len(failed_rows)} address(es) could not be geocoded. Please fix below:")

        for idx in failed_rows:
            row = df.loc[idx]
            suggestion = row.get("Suggested", None)
            st.markdown(f"**Client:** {row['Client']}  
**Original Address:** `{row['Address']}`")

            if suggestion and isinstance(suggestion, str) and suggestion.strip().lower() != "none":
                choice = st.selectbox(
                    f"Select suggestion for '{row['Client']}'",
                    options=[row["Address"], suggestion],
                    key=f"dropdown_{idx}"
                )
                st.session_state["geocode_fixes"][idx] = choice
            else:
                manual = st.text_input(
                    f"Enter address manually for '{row['Client']}'",
                    key=f"manual_{idx}"
                )
                if manual:
                    st.session_state["geocode_fixes"][idx] = manual

        if st.button("🔁 Retry Geocoding with Fixes"):
            for idx, new_addr in st.session_state["geocode_fixes"].items():
                try:
                    loc = geolocator.geocode(new_addr + ", Cebu, Philippines", timeout=10)
                    if loc:
                        df.at[idx, "Latitude"] = loc.latitude
                        df.at[idx, "Longitude"] = loc.longitude
                        df.at[idx, "Full Address"] = new_addr
                        st.success(f"✅ Fixed: {new_addr}")
                    else:
                        st.error(f"❌ Still failed: {new_addr}")
                except Exception as e:
                    st.error(f"❌ Error geocoding '{new_addr}': {e}")

            # Refresh session data
            st.session_state["geocode_df"] = df
            st.session_state["geocode_failed"] = df[df["Latitude"].isna()].index.tolist()

    # Show final result table
    st.subheader("✅ Geocoding Result Preview")
    st.dataframe(df)

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

        if st.session_state.Driver:
            valid_coords["Driver"] = valid_coords["Assigned Truck"].map(st.session_state.Driver)
        else:
            valid_coords["Driver"] = valid_coords["Assigned Truck"].apply(lambda x: f"Truck {x+1}")

        plant = geolocator.geocode(start_point + ", Cebu, Philippines")
        if plant:
            start_lat = plant.latitude
            start_lon = plant.longitude
        else:
            st.error("❌ Could not locate starting point.")
            st.stop()

        st.subheader("📍 Final Map with Drivers")
        m = folium.Map(location=[valid_coords["Latitude"].mean(), valid_coords["Longitude"].mean()], zoom_start=11)

        folium.Marker(
            [start_lat, start_lon],
            popup="📦 Plant Dispatch",
            icon=folium.Icon(color='black', icon='home')
        ).add_to(m)

        for _, row in valid_coords.iterrows():
            folium.Marker(
                [row["Latitude"], row["Longitude"]],
                popup=f"{row['Client']}<br>Driver: {row['Driver']}",
            ).add_to(m)

        st_folium(m, width=1000, height=600)

        st.download_button(
            label="📥 Download Final Route Plan",
            data=valid_coords.to_excel(index=False),
            file_name="Final_Optimized_Routes.xlsx"
        )
