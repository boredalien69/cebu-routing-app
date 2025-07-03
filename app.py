
import streamlit as st
import pandas as pd
import folium
from folium import Marker
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from sklearn.cluster import KMeans
import base64
import time

st.set_page_config(page_title="Cebu Routing App", layout="wide")
st.title("📦 Cebu Routing Optimizer with Suggestions & Manual Start")

ors_key = st.text_input("🔑 Enter OpenRouteService API Key", type="password")
uploaded_file = st.file_uploader("📁 Upload Excel File", type=["xlsx"])
num_trucks = st.number_input("🚛 Number of Trucks", min_value=1, value=3)

driver_names = []
st.subheader("👥 Driver Names")
for i in range(num_trucks):
    name = st.text_input(f"Driver {i+1}", value=f"Driver {i+1}")
    driver_names.append(name)

if uploaded_file and ors_key:
    df = pd.read_excel(uploaded_file)
    st.subheader("📄 Uploaded Data")
    st.dataframe(df)

    geolocator = Nominatim(user_agent="cebu_router")
    depot_coords = (10.3363, 123.9381)

    df["Full Address"] = df["Address"].astype(str) + ", Cebu, Philippines"
    df["Latitude"] = None
    df["Longitude"] = None
    df["Suggested"] = ""
    failed_rows = []

    st.subheader("🔄 Step 1: Attempt Geocoding")
    with st.spinner("Trying to locate addresses..."):
        for i, row in df.iterrows():
            try:
                location = geolocator.geocode(row["Full Address"], timeout=10)
                if location:
                    df.at[i, "Latitude"] = location.latitude
                    df.at[i, "Longitude"] = location.longitude
                else:
                    failed_rows.append(i)
                    time.sleep(1)
                    results = geolocator.geocode(row["Address"] + ", Cebu", timeout=10)
                    if results:
                        df.at[i, "Suggested"] = results.address
            except:
                failed_rows.append(i)
                df.at[i, "Suggested"] = ""

    if failed_rows:
        st.warning(f"{len(failed_rows)} address(es) could not be located. Review and fix below:")
        df_failed = df.loc[failed_rows, ["Client", "Address", "Suggested"]].copy()
        new_inputs = {}
        for idx in df_failed.index:
            raw_suggestion = str(df_failed.at[idx, "Suggested"])
            suggested = raw_suggestion.strip() if raw_suggestion and raw_suggestion != "None" else ""
            if suggested:
                display_text = f"Suggested for '{df_failed.at[idx, 'Address']}'"
                new_inputs[idx] = st.text_input(display_text, value=suggested)

        if st.button("🔁 Retry Geocoding with Fixes"):
            for idx, new_addr in new_inputs.items():
                try:
                    loc = geolocator.geocode(new_addr, timeout=10)
                    if loc:
                        df.at[idx, "Latitude"] = loc.latitude
                        df.at[idx, "Longitude"] = loc.longitude
                        df.at[idx, "Full Address"] = new_addr
                except:
                    pass
            failed_rows = df[df["Latitude"].isna()].index.tolist()
            if len(failed_rows) == 0:
                st.success("✅ All addresses geocoded successfully.")
            else:
                st.warning(f"⚠️ Still {len(failed_rows)} unresolved addresses.")

    valid_df = df.dropna(subset=["Latitude", "Longitude"])

    if len(valid_df) >= num_trucks:
        if st.button("🚀 Start Optimization"):
            kmeans = KMeans(n_clusters=num_trucks, random_state=42)
            df.loc[valid_df.index, "Assigned Truck"] = kmeans.fit_predict(valid_df[["Latitude", "Longitude"]])
            colors = ["red", "blue", "green", "orange", "purple"]
            m = folium.Map(location=(10.3363, 123.9381), zoom_start=12)
            Marker((10.3363, 123.9381), tooltip="🏭 Depot").add_to(m)

            for i, row in df.iterrows():
                if pd.notna(row["Latitude"]):
                    truck_id = int(row["Assigned Truck"]) if pd.notna(row["Assigned Truck"]) else 0
                    driver_label = driver_names[truck_id] if truck_id < len(driver_names) else f"Truck {truck_id+1}"
                    Marker(
                        location=[row["Latitude"], row["Longitude"]],
                        popup=f"{row['Client']}<br>{row['Address']}",
                        tooltip=f"{driver_label}",
                        icon=folium.Icon(color=colors[truck_id % len(colors)], icon="truck", prefix='fa')
                    ).add_to(m)

            st.subheader("🗺️ Route Map")
            st_folium(m, width=700, height=500)

            html_map = m._repr_html_()
            b64_map = base64.b64encode(html_map.encode()).decode()
            map_link = f'<a href="data:text/html;base64,{b64_map}" download="cebu_route_map.html">📥 Download Map (HTML)</a>'
            st.markdown(map_link, unsafe_allow_html=True)

            st.subheader("⬇️ Download Optimized Excel")
            df_export = df[["Client", "Address", "Full Address", "Latitude", "Longitude", "Assigned Truck"]]
            st.download_button("Download Updated Excel", data=df_export.to_excel(index=False), file_name="OptimizedRoutes.xlsx")

    else:
        st.info("🛑 Not enough geocoded points for clustering. Please fix unresolved addresses above.")
