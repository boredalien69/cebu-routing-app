
import streamlit as st
import pandas as pd
import folium
from folium import Marker
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from sklearn.cluster import KMeans
import base64

st.set_page_config(page_title="Cebu Delivery Route Planner", layout="wide")
st.title("🚚 Cebu Delivery Route Optimizer (with Geocode Suggestions)")

ors_key = st.text_input("🔑 Enter your OpenRouteService API Key", type="password")
uploaded_file = st.file_uploader("📁 Upload Excel File", type=["xlsx"])
num_trucks = st.number_input("🚛 Number of Trucks", min_value=1, value=3)
start_time = st.time_input("🕖 Start Time (All Trucks)", value=pd.to_datetime("07:00").time())
flexibility = st.number_input("🕗 Flexibility (mins for flexible clients)", min_value=0, value=30)
driver_names = [st.text_input(f"👤 Driver name for Truck {i+1}", value=f"Driver {i+1}") for i in range(num_trucks)]

if uploaded_file and ors_key:
    df = pd.read_excel(uploaded_file)
    st.subheader("📄 Uploaded Data Preview")
    st.dataframe(df)

    geolocator = Nominatim(user_agent="cebu_route_planner")
    depot_coords = (10.3363, 123.9381)

    lat_list = []
    lon_list = []
    failed_rows = []
    suggestions = []

    with st.spinner("🔄 Geocoding addresses..."):
        for i, addr in enumerate(df["Address"]):
            full_addr = str(addr) + ", Cebu, Philippines"
            try:
                location = geolocator.geocode(full_addr, timeout=10)
                if location:
                    lat_list.append(location.latitude)
                    lon_list.append(location.longitude)
                    suggestions.append("")
                else:
                    lat_list.append(None)
                    lon_list.append(None)
                    failed_rows.append(i)
                    suggestions.append("Suggestion unavailable")
            except:
                lat_list.append(None)
                lon_list.append(None)
                failed_rows.append(i)
                suggestions.append("Suggestion unavailable")

    df["Latitude"] = lat_list
    df["Longitude"] = lon_list

    if failed_rows:
        st.warning(f"⚠️ {len(failed_rows)} address(es) could not be geocoded. Suggestions shown below.")
        failed_df = df.iloc[failed_rows].copy()
        failed_df["Suggested Fix"] = [suggestions[i] for i in failed_rows]
        st.dataframe(failed_df[["Client", "Address", "Suggested Fix"]])

    valid_coords = df.dropna(subset=["Latitude", "Longitude"])
    if len(valid_coords) >= num_trucks:
        kmeans = KMeans(n_clusters=num_trucks, random_state=42)
        df.loc[valid_coords.index, "Assigned Truck"] = kmeans.fit_predict(valid_coords[["Latitude", "Longitude"]])

        cluster_map = folium.Map(location=depot_coords, zoom_start=12)
        colors = ["red", "blue", "green", "orange", "purple"]
        for i, row in df.iterrows():
            if pd.notna(row["Latitude"]):
                truck_id = int(row["Assigned Truck"]) if pd.notna(row["Assigned Truck"]) else 0
                Marker(
                    location=[row["Latitude"], row["Longitude"]],
                    popup=f"{row['Client']}<br>ETA: TBD",
                    tooltip=f"Truck {truck_id+1}",
                    icon=folium.Icon(color=colors[truck_id % len(colors)], icon="truck", prefix='fa')
                ).add_to(cluster_map)
        Marker(location=depot_coords, tooltip="🏭 Depot").add_to(cluster_map)

        st.subheader("🗺️ Cluster Map Preview")
        st_folium(cluster_map, width=700, height=500)

        html_str = cluster_map._repr_html_()
        b64 = base64.b64encode(html_str.encode()).decode()
        href = f'<a href="data:text/html;base64,{b64}" download="route_map.html">📥 Download Interactive Map (HTML)</a>'
        st.markdown(href, unsafe_allow_html=True)

        st.subheader("📋 Reassign Clients to Trucks (Manual Override)")
        for i in range(len(df)):
            if pd.notna(df.loc[i, "Assigned Truck"]):
                df.loc[i, "Assigned Truck"] = st.selectbox(
                    f"Client: {df.loc[i, 'Client']}",
                    [f"Truck {j+1}" for j in range(num_trucks)],
                    index=int(df.loc[i, "Assigned Truck"]),
                    key=f"truck_select_{i}"
                )

        st.download_button("⬇️ Download Updated File", data=df.to_excel(index=False), file_name="Updated_Routes.xlsx")
