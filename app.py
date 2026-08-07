import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(
    page_title="PH Barangay Coordinate Locator",
    layout="wide"
)

st.title("🇵🇭 Philippine Barangay Spatial Locator")

st.markdown(
    """
    Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates 
    to identify their corresponding **Barangay, City, Province, and Region**.
    """
)

# Initialize session state
if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()

if "markers_to_plot" not in st.session_state:
    st.session_state.markers_to_plot = []

# Load Barangay GeoJSON / Parquet Data
@st.cache_resource
def load_barangay_data():
    gdf = gpd.read_parquet("barangays.parquet")

    # Ensure WGS84 coordinate reference system
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    return gdf

with st.spinner("Loading Philippine boundary data... Please wait."):
    brgy_gdf = load_barangay_data()

# Sidebar options
st.sidebar.header("Input Options")

input_mode = st.sidebar.radio(
    "Choose Input Method",
    ["Single Coordinate", "Batch Upload (CSV / XLSX)"]
)

# Single coordinate mode
if input_mode == "Single Coordinate":

    st.sidebar.subheader("Enter Lat/Long")

    lat = st.sidebar.number_input(
        "Latitude",
        value=14.5995,
        format="%.6f"
    )

    lon = st.sidebar.number_input(
        "Longitude",
        value=120.9842,
        format="%.6f"
    )

    if st.sidebar.button("Locate Barangay"):

        point = Point(lon, lat)

        # Find polygon containing point
        match = brgy_gdf[brgy_gdf.contains(point)]

        if not match.empty:

            match_row = match.iloc[0]

            st.session_state.results_df = pd.DataFrame([
                {
                    "Latitude": lat,
                    "Longitude": lon,
                    "Barangay": match_row.get("ADM4_EN", "N/A"),
                    "City/Municipality": match_row.get("ADM3_EN", "N/A"),
                    "Province": match_row.get("ADM2_EN", "N/A"),
                    "Region": match_row.get("ADM1_EN", "N/A")
                }
            ])

            st.session_state.markers_to_plot = [
                (
                    lat,
                    lon,
                    f"<b>{match_row.get('ADM4_EN', '')}</b>, {match_row.get('ADM3_EN', '')}"
                )
            ]

        else:
            st.session_state.results_df = pd.DataFrame()
            st.session_state.markers_to_plot = []
            st.warning("Coordinates fall outside the boundaries of the loaded GeoJSON file.")

# Batch upload mode
else:

    st.sidebar.subheader("Upload File")

    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV or XLSX file",
        type=["csv", "xlsx"]
    )

    if uploaded_file is not None:

        if uploaded_file.name.endswith(".csv"):
            input_df = pd.read_csv(uploaded_file)
        else:
            input_df = pd.read_excel(uploaded_file)

        lat_col = st.sidebar.selectbox(
            "Select Latitude Column",
            input_df.columns
        )

        lon_col = st.sidebar.selectbox(
            "Select Longitude Column",
            input_df.columns
        )

        if st.sidebar.button("Process Batch"):

            with st.spinner("Processing spatial lookup..."):

                # Convert input dataframe to GeoDataFrame
                geometry = [
                    Point(xy)
                    for xy in zip(input_df[lon_col], input_df[lat_col])
                ]

                input_gdf = gpd.GeoDataFrame(
                    input_df,
                    geometry=geometry,
                    crs="EPSG:4326"
                )

                # Spatial join
                joined = gpd.sjoin(
                    input_gdf,
                    brgy_gdf,
                    how="left",
                    predicate="within"
                )

                output_list = []
                markers = []

                for idx, row in joined.iterrows():

                    lat_val = row[lat_col]
                    lon_val = row[lon_col]

                    brgy = row.get("ADM4_EN", "N/A")
                    city = row.get("ADM3_EN", "N/A")
                    prov = row.get("ADM2_EN", "N/A")
                    reg = row.get("ADM1_EN", "N/A")

                    output_list.append(
                        {
                            "Latitude": lat_val,
                            "Longitude": lon_val,
                            "Barangay": brgy,
                            "City/Municipality": city,
                            "Province": prov,
                            "Region": reg
                        }
                    )

                    if pd.notna(brgy) and brgy != "N/A":
                        markers.append(
                            (
                                lat_val,
                                lon_val,
                                f"<b>{brgy}</b>, {city}"
                            )
                        )

                st.session_state.results_df = pd.DataFrame(output_list)
                st.session_state.markers_to_plot = markers

# Retrieve saved state
results_df = st.session_state.results_df
markers_to_plot = st.session_state.markers_to_plot

# Map section
st.subheader("🗺️ Interactive Map")

# Default center to Metro Manila if no markers yet
map_center = [14.5995, 120.9842]
zoom_start = 11

if markers_to_plot:
    map_center = [
        markers_to_plot[0][0],
        markers_to_plot[0][1]
    ]

m = folium.Map(
    location=map_center,
    zoom_start=zoom_start
)

# Add markers
for lat, lon, popup_text in markers_to_plot:

    folium.Marker(
        location=[lat, lon],
        popup=popup_text,
        icon=folium.Icon(
            color="red",
            icon="map-marker",
            prefix="fa"
        )
    ).add_to(m)

st_folium(
    m,
    width=700,
    height=450,
    use_container_width=True
)

st.markdown("---")

# Table section
st.subheader("📋 Tabular Results")

if not results_df.empty:

    st.dataframe(
        results_df,
        use_container_width=True
    )

    csv_data = results_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Results as CSV",
        data=csv_data,
        file_name="barangay_lookup_results.csv",
        mime="text/csv"
    )

else:
    st.info("Input a coordinate or upload a file to view tabular results.")

# as of 5:04 pm

# import streamlit as st
# import pandas as pd
# import geopandas as gpd
# from shapely.geometry import Point
# import folium
# from streamlit_folium import st_folium

# # Page configuration

# st.set_page_config(page_title="PH Barangay Coordinate Locator", layout="wide")

# st.title("🇵🇭 Philippine Barangay Spatial Locator")

# st.markdown("Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates to identify their corresponding **Barangay, City, Province, and Region** using your GeoJSON dataset.")

# # 1. Load Barangay GeoJSON Data

# @st.cache_resource

# def load_barangay_data():

#     # Replace 'barangays.geojson' with your actual GeoJSON file name/path

#     gdf = gpd.read_parquet("barangays.parquet")

#     # Ensure standard WGS84 coordinate reference system (Lat/Long)

#     if gdf.crs != "EPSG:4326":

#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf

# with st.spinner("Loading Philippine boundary GeoJSON data... Please wait."):

#     brgy_gdf = load_barangay_data()

# # Sidebar options for input type

# st.sidebar.header("Input Options")

# input_mode = st.sidebar.radio("Choose Input Method", ["Single Coordinate", "Batch Upload (CSV / XLSX)"])

# # Container for results

# results_df = pd.DataFrame()

# markers_to_plot = []

# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Lat/Long")

#     lat = st.sidebar.number_input("Latitude", value=14.5995, format="%.6f")

#     lon = st.sidebar.number_input("Longitude", value=120.9842, format="%.6f")

#     if st.sidebar.button("Locate Barangay"):

#         point = Point(lon, lat)

#         # Spatial join / check which polygon contains the point

#         match = brgy_gdf[brgy_gdf.contains(point)]

#         if not match.empty:

#             match_row = match.iloc[0]

#             results_df = pd.DataFrame([{

#                 "Latitude": lat,

#                 "Longitude": lon,

#                 "Barangay": match_row.get('ADM4_EN', 'N/A'),

#                 "City/Municipality": match_row.get('ADM3_EN', 'N/A'),

#                 "Province": match_row.get('ADM2_EN', 'N/A'),

#                 "Region": match_row.get('ADM1_EN', 'N/A')

#             }])

#             markers_to_plot.append((lat, lon, f"<b>{match_row.get('ADM4_EN', '')}</b>, {match_row.get('ADM3_EN', '')}"))

#         else:

#             st.warning("Coordinates fall outside the boundaries of the loaded GeoJSON file.")

# else:

#     st.sidebar.subheader("Upload File")

#     uploaded_file = st.sidebar.file_uploader("Upload CSV or XLSX file", type=["csv", "xlsx"])

#     if uploaded_file is not None:

#         if uploaded_file.name.endswith('.csv'):

#             input_df = pd.read_csv(uploaded_file)

#         else:

#             input_df = pd.read_excel(uploaded_file)

#         lat_col = st.sidebar.selectbox("Select Latitude Column", input_df.columns)

#         lon_col = st.sidebar.selectbox("Select Longitude Column", input_df.columns)

#         if st.sidebar.button("Process Batch"):

#             with st.spinner("Processing spatial lookup..."):

#                 # Convert input dataframe to GeoDataFrame

#                 geometry = [Point(xy) for xy in zip(input_df[lon_col], input_df[lat_col])]

#                 input_gdf = gpd.GeoDataFrame(input_df, geometry=geometry, crs="EPSG:4326")

#                 # Spatial join

#                 joined = gpd.sjoin(input_gdf, brgy_gdf, how="left", predicate="within")

#                 # Format output using ADM fields

#                 output_list = []

#                 for idx, row in joined.iterrows():

#                     lat_val = row[lat_col]

#                     lon_val = row[lon_col]

#                     brgy = row.get('ADM4_EN', 'N/A')

#                     city = row.get('ADM3_EN', 'N/A')

#                     prov = row.get('ADM2_EN', 'N/A')

#                     reg = row.get('ADM1_EN', 'N/A')

#                     output_list.append({

#                         "Latitude": lat_val,

#                         "Longitude": lon_val,

#                         "Barangay": brgy,

#                         "City/Municipality": city,

#                         "Province": prov,

#                         "Region": reg

#                     })

#                     if pd.notna(brgy) and brgy != 'N/A':

#                         markers_to_plot.append((lat_val, lon_val, f"<b>{brgy}</b>, {city}"))

#                 results_df = pd.DataFrame(output_list)

# # Layout: Map on top/left, Table below

# col1, col2 = st.columns([1, 1])

# with st.container():

#     st.subheader("🗺️ Interactive Map")

#     # Default center to Metro Manila if no markers yet

#     map_center = [14.5995, 120.9842]

#     if markers_to_plot:

#         map_center = [markers_to_plot[0][0], markers_to_plot[0][1]]

#     m = folium.Map(location=map_center, zoom_start=11)

#     # Add markers

#     for lat, lon, popup_text in markers_to_plot:

#         folium.Marker(

#             location=[lat, lon],

#             popup=popup_text,

#             icon=folium.Icon(color="red", icon="map-marker", prefix="fa")

#         ).add_to(m)

#     st_folium(m, width=700, height=450, use_container_width=True)

# st.markdown("---")

# st.subheader("📋 Tabular Results")

# if not results_df.empty:

#     st.dataframe(results_df, use_container_width=True)

#     # Download button for batch output

#     csv_data = results_df.to_csv(index=False).encode('utf-8')

#     st.download_button(

#         label="Download Results as CSV",

#         data=csv_data,

#         file_name="barangay_lookup_results.csv",

#         mime="text/csv",

#     )

# else:
#     st.info("Input a coordinate or upload a file to view tabular results.")
