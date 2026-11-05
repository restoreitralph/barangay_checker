# ==================================================
# PHILIPPINE BARANGAY SPATIAL LOCATOR
# ==================================================

import streamlit as st
import pandas as pd
import geopandas as gpd

from shapely.geometry import Point

import folium
from streamlit_folium import st_folium


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="PH Barangay Spatial Locator",
    page_icon="🇵🇭",
    layout="wide"
)

st.title("🇵🇭 Philippine Barangay Spatial Locator")

st.markdown(
    """
    Enter a single coordinate or upload a CSV/XLSX file containing multiple
    coordinates to identify the corresponding **Barangay, City, Province,
    Region, and ADM4_PCODE**.
    """
)


# ==================================================
# SESSION STATE
# ==================================================

if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()

if "markers_to_plot" not in st.session_state:
    st.session_state.markers_to_plot = []

if "batch_processed" not in st.session_state:
    st.session_state.batch_processed = False

if "selected_point" not in st.session_state:
    st.session_state.selected_point = None

if "uploaded_file_id" not in st.session_state:
    st.session_state.uploaded_file_id = None


# ==================================================
# LOAD BARANGAY DATA
# ==================================================

@st.cache_resource
def load_barangay_data():
    """
    Load Philippine barangay boundary data and ensure
    the coordinate reference system is EPSG:4326.
    """

    gdf = gpd.read_parquet("barangays.parquet")

    if gdf.crs is None:
        raise ValueError(
            "The barangays.parquet file does not have a defined CRS."
        )

    if gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    return gdf


try:
    with st.spinner("Loading Philippine boundary data... Please wait."):
        brgy_gdf = load_barangay_data()

except Exception as error:
    st.error(
        f"Unable to load barangay boundary data: {error}"
    )
    st.stop()


# ==================================================
# SIDEBAR: INPUT OPTIONS
# ==================================================

st.sidebar.header("Input Options")

input_mode = st.sidebar.radio(
    "Choose Input Method",
    [
        "Single Coordinate",
        "Batch Upload (CSV / XLSX)"
    ]
)


# ==================================================
# SIDEBAR: BASEMAP SELECTION
# ==================================================

st.sidebar.divider()
st.sidebar.subheader("Map Settings")

basemap_name = st.sidebar.selectbox(
    "Select Basemap",
    [
        "OpenStreetMap",
        "OpenStreetMap HOT",
        "OpenTopoMap"
    ],
    index=0,
    help="Available basemaps you can choose."
)


# ==================================================
# BASEMAP CONFIGURATION
# ==================================================

BASEMAPS = {
    "OpenStreetMap": {
        "tiles": (
            "https://{s}.tile.openstreetmap.org/"
            "{z}/{x}/{y}.png"
        ),
        "attr": (
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            "OpenStreetMap contributors"
            "</a>"
        ),
        "max_zoom": 19
    },

    "OpenStreetMap HOT": {
        "tiles": (
            "https://{s}.tile.openstreetmap.fr/hot/"
            "{z}/{x}/{y}.png"
        ),
        "attr": (
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            "OpenStreetMap contributors"
            "</a>, "
            "Tiles style by Humanitarian OpenStreetMap Team"
        ),
        "max_zoom": 19
    },

    "OpenTopoMap": {
        "tiles": (
            "https://{s}.tile.opentopomap.org/"
            "{z}/{x}/{y}.png"
        ),
        "attr": (
            "Map data: "
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            "OpenStreetMap contributors"
            "</a>, "
            "SRTM | "
            "Map style: "
            '&copy; '
            '<a href="https://opentopomap.org">'
            "OpenTopoMap"
            "</a>"
        ),
        "max_zoom": 17
    }
}

selected_basemap = BASEMAPS[basemap_name]


# ==================================================
# SINGLE COORDINATE INPUT
# ==================================================

if input_mode == "Single Coordinate":

    st.sidebar.subheader("Enter Latitude and Longitude")

    lat = st.sidebar.number_input(
        "Latitude",
        min_value=-90.0,
        max_value=90.0,
        value=14.599500,
        step=0.000001,
        format="%.6f"
    )

    lon = st.sidebar.number_input(
        "Longitude",
        min_value=-180.0,
        max_value=180.0,
        value=120.984200,
        step=0.000001,
        format="%.6f"
    )

    if st.sidebar.button(
        "Locate Barangay",
        type="primary",
        use_container_width=True
    ):

        point = Point(lon, lat)

        # Intersects is used here so that points on a polygon
        # boundary can still return a match.
        match = brgy_gdf[
            brgy_gdf.geometry.intersects(point)
        ]

        if not match.empty:

            match_row = match.iloc[0]

            barangay = match_row.get("ADM4_EN", "N/A")
            city = match_row.get("ADM3_EN", "N/A")
            province = match_row.get("ADM2_EN", "N/A")
            region = match_row.get("ADM1_EN", "N/A")
            pcode = match_row.get("ADM4_PCODE", "N/A")

            st.session_state.results_df = pd.DataFrame(
                [
                    {
                        "Latitude": lat,
                        "Longitude": lon,
                        "ADM4_PCODE": pcode,
                        "Barangay": barangay,
                        "City/Municipality": city,
                        "Province": province,
                        "Region": region
                    }
                ]
            )

            popup_text = (
                f"<b>{barangay}</b><br>"
                f"{city}<br>"
                f"{province}<br>"
                f"{region}<br>"
                f"<b>ADM4_PCODE:</b> {pcode}"
            )

            st.session_state.markers_to_plot = [
                (
                    float(lat),
                    float(lon),
                    popup_text
                )
            ]

            st.session_state.selected_point = {
                "lat": float(lat),
                "lon": float(lon),
                "label": barangay
            }

        else:

            st.session_state.results_df = pd.DataFrame()
            st.session_state.markers_to_plot = []
            st.session_state.selected_point = None

            st.warning(
                "The coordinates fall outside the boundaries "
                "of the loaded barangay dataset."
            )


# ==================================================
# BATCH FILE UPLOAD
# ==================================================

else:

    st.sidebar.subheader("Upload Coordinate File")

    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV or XLSX file",
        type=["csv", "xlsx"]
    )

    if uploaded_file is None:

        st.session_state.batch_processed = False
        st.session_state.selected_point = None
        st.session_state.uploaded_file_id = None

    if uploaded_file is not None:

        current_file_id = (
            uploaded_file.name,
            uploaded_file.size
        )

        # Reset processing status when a different file is uploaded.
        if st.session_state.uploaded_file_id != current_file_id:

            st.session_state.uploaded_file_id = current_file_id
            st.session_state.batch_processed = False
            st.session_state.results_df = pd.DataFrame()
            st.session_state.markers_to_plot = []
            st.session_state.selected_point = None

        try:

            if uploaded_file.name.lower().endswith(".csv"):

                input_df = pd.read_csv(uploaded_file)

            else:

                input_df = pd.read_excel(uploaded_file)

        except Exception as error:

            st.error(
                f"Unable to read the uploaded file: {error}"
            )
            st.stop()

        if input_df.empty:

            st.warning(
                "The uploaded file does not contain any records."
            )
            st.stop()

        if not st.session_state.batch_processed:

            st.write("### Preview of Uploaded Data")

            st.dataframe(
                input_df.head(),
                use_container_width=True,
                hide_index=True
            )

        available_columns = input_df.columns.tolist()

        # Attempt to identify likely latitude and longitude columns.
        latitude_candidates = [
            col
            for col in available_columns
            if str(col).lower() in [
                "latitude",
                "lat",
                "y"
            ]
        ]

        longitude_candidates = [
            col
            for col in available_columns
            if str(col).lower() in [
                "longitude",
                "long",
                "lon",
                "lng",
                "x"
            ]
        ]

        default_lat_index = 0

        if latitude_candidates:
            default_lat_index = available_columns.index(
                latitude_candidates[0]
            )

        default_lon_index = 0

        if longitude_candidates:
            default_lon_index = available_columns.index(
                longitude_candidates[0]
            )
        elif len(available_columns) > 1:
            default_lon_index = 1

        lat_col = st.sidebar.selectbox(
            "Select Latitude Column",
            available_columns,
            index=default_lat_index
        )

        lon_col = st.sidebar.selectbox(
            "Select Longitude Column",
            available_columns,
            index=default_lon_index
        )

        if st.sidebar.button(
            "Process Batch",
            type="primary",
            use_container_width=True
        ):

            if lat_col == lon_col:

                st.error(
                    "Latitude and longitude must use different columns."
                )

            else:

                working_df = input_df.copy()

                working_df[lat_col] = pd.to_numeric(
                    working_df[lat_col],
                    errors="coerce"
                )

                working_df[lon_col] = pd.to_numeric(
                    working_df[lon_col],
                    errors="coerce"
                )

                valid_coordinate_mask = (
                    working_df[lat_col].between(-90, 90)
                    & working_df[lon_col].between(-180, 180)
                )

                invalid_count = int(
                    (~valid_coordinate_mask).sum()
                )

                valid_df = working_df[
                    valid_coordinate_mask
                ].copy()

                if valid_df.empty:

                    st.error(
                        "No valid coordinate records were found. "
                        "Latitude must be between -90 and 90, and "
                        "longitude must be between -180 and 180."
                    )

                else:

                    st.session_state.batch_processed = True
                    st.session_state.selected_point = None

                    with st.spinner(
                        "Performing spatial lookup..."
                    ):

                        geometry = gpd.points_from_xy(
                            valid_df[lon_col],
                            valid_df[lat_col]
                        )

                        input_gdf = gpd.GeoDataFrame(
                            valid_df.copy(),
                            geometry=geometry,
                            crs="EPSG:4326"
                        )

                        joined = gpd.sjoin(
                            input_gdf,
                            brgy_gdf,
                            how="left",
                            predicate="within"
                        )

                        # A point can occasionally match more than one
                        # polygon if the source polygons overlap.
                        # Keep the first matched polygon per input record.
                        joined = joined[
                            ~joined.index.duplicated(keep="first")
                        ].copy()

                        output_list = []
                        markers = []

                        for _, row in joined.iterrows():

                            lat_val = row.get(lat_col)
                            lon_val = row.get(lon_col)

                            result_row = {
                                column: row.get(column)
                                for column in input_df.columns
                            }

                            barangay = row.get(
                                "ADM4_EN",
                                "N/A"
                            )

                            city = row.get(
                                "ADM3_EN",
                                "N/A"
                            )

                            province = row.get(
                                "ADM2_EN",
                                "N/A"
                            )

                            region = row.get(
                                "ADM1_EN",
                                "N/A"
                            )

                            pcode = row.get(
                                "ADM4_PCODE",
                                "N/A"
                            )

                            # Replace missing spatial results with N/A.
                            barangay = (
                                barangay
                                if pd.notna(barangay)
                                else "N/A"
                            )

                            city = (
                                city
                                if pd.notna(city)
                                else "N/A"
                            )

                            province = (
                                province
                                if pd.notna(province)
                                else "N/A"
                            )

                            region = (
                                region
                                if pd.notna(region)
                                else "N/A"
                            )

                            pcode = (
                                pcode
                                if pd.notna(pcode)
                                else "N/A"
                            )

                            result_row.update(
                                {
                                    "Latitude": float(lat_val),
                                    "Longitude": float(lon_val),
                                    "ADM4_PCODE": pcode,
                                    "Barangay": barangay,
                                    "City/Municipality": city,
                                    "Province": province,
                                    "Region": region
                                }
                            )

                            output_list.append(result_row)

                            if barangay != "N/A":

                                popup_text = (
                                    f"<b>{barangay}</b><br>"
                                    f"{city}<br>"
                                    f"{province}<br>"
                                    f"{region}<br>"
                                    f"<b>ADM4_PCODE:</b> {pcode}"
                                )

                                markers.append(
                                    (
                                        float(lat_val),
                                        float(lon_val),
                                        popup_text
                                    )
                                )

                        st.session_state.results_df = pd.DataFrame(
                            output_list
                        )

                        st.session_state.markers_to_plot = markers

                    if invalid_count > 0:

                        st.warning(
                            f"{invalid_count:,} record(s) were excluded "
                            "because of missing or invalid coordinates."
                        )


# ==================================================
# RETRIEVE SAVED RESULTS
# ==================================================

results_df = st.session_state.results_df
markers_to_plot = st.session_state.markers_to_plot


# ==================================================
# MAP AND TABLE LAYOUT
# ==================================================

map_col, table_col = st.columns(
    [2, 2],
    gap="large"
)


# ==================================================
# TABLE
# Render table first so selected row controls the map.
# ==================================================

with table_col:

    st.subheader("📋 Tabular Results")

    if not results_df.empty:

        row_count = len(results_df)

        table_height = min(
            max(
                90 + (row_count * 35),
                130
            ),
            750
        )

        table_event = st.dataframe(
            results_df,
            use_container_width=True,
            height=table_height,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="results_table"
        )

        selected_rows = table_event.selection.rows

        if selected_rows:

            selected_row_index = selected_rows[0]

            selected_row = results_df.iloc[
                selected_row_index
            ]

            selected_lat = selected_row.get(
                "Latitude"
            )

            selected_lon = selected_row.get(
                "Longitude"
            )

            if (
                pd.notna(selected_lat)
                and pd.notna(selected_lon)
            ):

                st.session_state.selected_point = {
                    "lat": float(selected_lat),
                    "lon": float(selected_lon),
                    "label": selected_row.get(
                        "Barangay",
                        ""
                    )
                }

        csv_data = results_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="⬇️ Download Results as CSV",
            data=csv_data,
            file_name="barangay_lookup_results.csv",
            mime="text/csv",
            use_container_width=True
        )

    else:

        st.session_state.selected_point = None

        st.info(
            "Input a coordinate or upload a file "
            "to view tabular results."
        )


# ==================================================
# MAP
# ==================================================

with map_col:

    st.subheader("🗺️ Interactive Map")

    selected_point = st.session_state.selected_point

    # Default center of the Philippines.
    map_center = [
        12.8797,
        121.7740
    ]

    zoom_start = 6

    if selected_point is not None:

        map_center = [
            selected_point["lat"],
            selected_point["lon"]
        ]

        zoom_start = 15

    # Create the map without a default tile layer.
    m = folium.Map(
        location=map_center,
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
        prefer_canvas=True
    )

    # Add the user-selected free basemap.
    folium.TileLayer(
        tiles=selected_basemap["tiles"],
        attr=selected_basemap["attr"],
        name=basemap_name,
        max_zoom=selected_basemap["max_zoom"],
        overlay=False,
        control=False
    ).add_to(m)

    # Add all result markers.
    for lat, lon, popup_text in markers_to_plot:

        marker_color = "red"
        marker_icon = "map-marker"

        if selected_point is not None:

            latitude_difference = abs(
                float(lat)
                - float(selected_point["lat"])
            )

            longitude_difference = abs(
                float(lon)
                - float(selected_point["lon"])
            )

            if (
                latitude_difference < 0.000001
                and longitude_difference < 0.000001
            ):

                marker_color = "blue"
                marker_icon = "info-sign"

        folium.Marker(
            location=[
                float(lat),
                float(lon)
            ],
            tooltip="Click to view location details",
            popup=folium.Popup(
                popup_text,
                max_width=300
            ),
            icon=folium.Icon(
                color=marker_color,
                icon=marker_icon,
                prefix="fa"
            )
        ).add_to(m)

    # Automatically fit the map to all markers if no
    # specific table row is selected.
    if selected_point is None:

        if len(markers_to_plot) > 1:

            bounds = [
                [
                    float(lat),
                    float(lon)
                ]
                for lat, lon, _ in markers_to_plot
            ]

            m.fit_bounds(
                bounds,
                padding=[
                    30,
                    30
                ]
            )

        elif len(markers_to_plot) == 1:

            single_lat = float(
                markers_to_plot[0][0]
            )

            single_lon = float(
                markers_to_plot[0][1]
            )

            m.location = [
                single_lat,
                single_lon
            ]

            m.zoom_start = 14

    st_folium(
        m,
        height=850,
        use_container_width=True,
        key=f"barangay_map_{basemap_name}"
    )


# # test clickable experiment

# import streamlit as st
# import pandas as pd
# import geopandas as gpd
# from shapely.geometry import Point
# import folium
# from streamlit_folium import st_folium

# # ==================================================
# # PAGE CONFIGURATION
# # ==================================================

# st.set_page_config(
#     page_title="PH Barangay Spatial Locator",
#     layout="wide"
# )

# st.title("🇵🇭 Philippine Barangay Spatial Locator")

# st.markdown(
#     """
#     Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates
#     to identify their corresponding **Barangay, City, Province, Region, and ADM4_PCODE**.
#     """
# )

# # ==================================================
# # SESSION STATE
# # ==================================================

# if "results_df" not in st.session_state:
#     st.session_state.results_df = pd.DataFrame()

# if "markers_to_plot" not in st.session_state:
#     st.session_state.markers_to_plot = []

# if "batch_processed" not in st.session_state:
#     st.session_state.batch_processed = False

# if "selected_point" not in st.session_state:
#     st.session_state.selected_point = None

# # ==================================================
# # LOAD BARANGAY DATA
# # ==================================================

# @st.cache_resource
# def load_barangay_data():

#     gdf = gpd.read_parquet("barangays.parquet")

#     if gdf.crs != "EPSG:4326":
#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf


# with st.spinner("Loading Philippine boundary data... Please wait."):
#     brgy_gdf = load_barangay_data()

# # ==================================================
# # SIDEBAR
# # ==================================================

# st.sidebar.header("Input Options")

# input_mode = st.sidebar.radio(
#     "Choose Input Method",
#     [
#         "Single Coordinate",
#         "Batch Upload (CSV / XLSX)"
#     ]
# )

# # ==================================================
# # SINGLE COORDINATE
# # ==================================================

# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Lat/Long")

#     lat = st.sidebar.number_input(
#         "Latitude",
#         value=14.599500,
#         format="%.6f"
#     )

#     lon = st.sidebar.number_input(
#         "Longitude",
#         value=120.984200,
#         format="%.6f"
#     )

#     if st.sidebar.button("Locate Barangay"):

#         point = Point(lon, lat)

#         match = brgy_gdf[brgy_gdf.intersects(point)]

#         if not match.empty:

#             match_row = match.iloc[0]

#             st.session_state.results_df = pd.DataFrame([
#                 {
#                     "Latitude": lat,
#                     "Longitude": lon,
#                     "ADM4_PCODE": match_row.get("ADM4_PCODE", "N/A"),
#                     "Barangay": match_row.get("ADM4_EN", "N/A"),
#                     "City/Municipality": match_row.get("ADM3_EN", "N/A"),
#                     "Province": match_row.get("ADM2_EN", "N/A"),
#                     "Region": match_row.get("ADM1_EN", "N/A")
#                 }
#             ])

#             st.session_state.markers_to_plot = [
#                 (
#                     lat,
#                     lon,
#                     f"<b>{match_row.get('ADM4_EN', '')}</b>, "
#                     f"{match_row.get('ADM3_EN', '')}"
#                 )
#             ]

#             st.session_state.selected_point = {
#                 "lat": lat,
#                 "lon": lon,
#                 "label": match_row.get("ADM4_EN", "")
#             }

#         else:

#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []
#             st.session_state.selected_point = None

#             st.warning(
#                 "Coordinates fall outside the boundaries of the loaded dataset."
#             )

# # ==================================================
# # BATCH UPLOAD
# # ==================================================

# else:

#     st.sidebar.subheader("Upload File")

#     uploaded_file = st.sidebar.file_uploader(
#         "Upload CSV or XLSX file",
#         type=["csv", "xlsx"]
#     )

#     if uploaded_file is None:
#         st.session_state.batch_processed = False
#         st.session_state.selected_point = None

#     if uploaded_file is not None:

#         if uploaded_file.name.endswith(".csv"):
#             input_df = pd.read_csv(uploaded_file)
#         else:
#             input_df = pd.read_excel(uploaded_file)

#         if not st.session_state.batch_processed:
#             st.write("Preview of Uploaded Data")
#             st.dataframe(
#                 input_df.head(),
#                 use_container_width=True
#             )

#         lat_col = st.sidebar.selectbox(
#             "Select Latitude Column",
#             input_df.columns
#         )

#         lon_col = st.sidebar.selectbox(
#             "Select Longitude Column",
#             input_df.columns
#         )

#         if st.sidebar.button("Process Batch"):

#             st.session_state.batch_processed = True
#             st.session_state.selected_point = None

#             with st.spinner("Performing spatial lookup..."):

#                 geometry = [
#                     Point(xy)
#                     for xy in zip(
#                         input_df[lon_col],
#                         input_df[lat_col]
#                     )
#                 ]

#                 input_gdf = gpd.GeoDataFrame(
#                     input_df.copy(),
#                     geometry=geometry,
#                     crs="EPSG:4326"
#                 )

#                 joined = gpd.sjoin(
#                     input_gdf,
#                     brgy_gdf,
#                     how="left",
#                     predicate="within"
#                 )

#                 output_list = []
#                 markers = []

#                 for _, row in joined.iterrows():

#                     lat_val = row[lat_col]
#                     lon_val = row[lon_col]

#                     result_row = row[input_df.columns].to_dict()

#                     # Standardize coordinate columns for row-click map zoom
#                     result_row.update({
#                         "Latitude": lat_val,
#                         "Longitude": lon_val,
#                         "ADM4_PCODE": row.get("ADM4_PCODE", "N/A"),
#                         "Barangay": row.get("ADM4_EN", "N/A"),
#                         "City/Municipality": row.get("ADM3_EN", "N/A"),
#                         "Province": row.get("ADM2_EN", "N/A"),
#                         "Region": row.get("ADM1_EN", "N/A")
#                     })

#                     output_list.append(result_row)

#                     if pd.notna(row.get("ADM4_EN")):

#                         markers.append(
#                             (
#                                 lat_val,
#                                 lon_val,
#                                 f"<b>{row.get('ADM4_EN', '')}</b>, "
#                                 f"{row.get('ADM3_EN', '')}"
#                             )
#                         )

#                 st.session_state.results_df = pd.DataFrame(output_list)
#                 st.session_state.markers_to_plot = markers

# # ==================================================
# # RETRIEVE SAVED RESULTS
# # ==================================================

# results_df = st.session_state.results_df
# markers_to_plot = st.session_state.markers_to_plot

# # ==================================================
# # MAP + TABLE LAYOUT
# # ==================================================

# map_col, table_col = st.columns([2, 2])

# # ==================================================
# # TABLE
# # Render table first so selected row can control map
# # ==================================================

# with table_col:

#     st.subheader("📋 Tabular Results")

#     if not results_df.empty:

#         row_count = len(results_df)

#         table_height = min(
#             max(90 + (row_count * 35), 130),
#             750
#         )

#         table_event = st.dataframe(
#             results_df,
#             use_container_width=True,
#             height=table_height,
#             on_select="rerun",
#             selection_mode="single-row",
#             key="results_table"
#         )

#         selected_rows = table_event.selection.rows

#         if selected_rows:

#             selected_row_index = selected_rows[0]
#             selected_row = results_df.iloc[selected_row_index]

#             selected_lat = selected_row.get("Latitude")
#             selected_lon = selected_row.get("Longitude")

#             if pd.notna(selected_lat) and pd.notna(selected_lon):

#                 st.session_state.selected_point = {
#                     "lat": float(selected_lat),
#                     "lon": float(selected_lon),
#                     "label": selected_row.get("Barangay", "")
#                 }

#         csv_data = results_df.to_csv(
#             index=False
#         ).encode("utf-8")

#         st.download_button(
#             label="⬇️ Download Results as CSV",
#             data=csv_data,
#             file_name="barangay_lookup_results.csv",
#             mime="text/csv",
#             use_container_width=True
#         )

#     else:

#         st.session_state.selected_point = None

#         st.info(
#             "Input a coordinate or upload a file to view tabular results."
#         )

# # ==================================================
# # MAP
# # ==================================================

# with map_col:

#     st.subheader("🗺️ Interactive Map")

#     selected_point = st.session_state.selected_point

#     map_center = [12.8797, 121.7740]
#     zoom_start = 6

#     if selected_point is not None:

#         map_center = [
#             selected_point["lat"],
#             selected_point["lon"]
#         ]

#         zoom_start = 15

#     m = folium.Map(
#         location=map_center,
#         zoom_start=zoom_start,
#         tiles="CartoDB positron"
#     )

#     for lat, lon, popup_text in markers_to_plot:

#         marker_color = "red"
#         marker_icon = "map-marker"

#         if selected_point is not None:

#             if (
#                 abs(float(lat) - float(selected_point["lat"])) < 0.000001
#                 and abs(float(lon) - float(selected_point["lon"])) < 0.000001
#             ):
#                 marker_color = "blue"
#                 marker_icon = "info-sign"

#         folium.Marker(
#             location=[lat, lon],
#             popup=popup_text,
#             icon=folium.Icon(
#                 color=marker_color,
#                 icon=marker_icon,
#                 prefix="fa"
#             )
#         ).add_to(m)

#     if selected_point is None:

#         if len(markers_to_plot) > 1:

#             bounds = [
#                 [lat, lon]
#                 for lat, lon, _ in markers_to_plot
#             ]

#             m.fit_bounds(bounds)

#         elif len(markers_to_plot) == 1:

#             m.location = [
#                 markers_to_plot[0][0],
#                 markers_to_plot[0][1]
#             ]

#             m.zoom_start = 14

#     st_folium(
#         m,
#         height=850,
#         use_container_width=True
#     )

# ---------------------------------------------------

# test - vertical layout

# import streamlit as st
# import pandas as pd
# import geopandas as gpd
# from shapely.geometry import Point
# import folium
# from streamlit_folium import st_folium

# # ==================================================
# # PAGE CONFIGURATION
# # ==================================================

# st.set_page_config(
#     page_title="PH Barangay Spatial Locator",
#     layout="wide"
# )

# st.title("Philippine Barangay Spatial Locator")

# st.markdown(
#     """
#     Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates
#     to identify their corresponding **Barangay, City, Province, Region, and ADM4_PCODE**.
#     """
# )

# # ==================================================
# # SESSION STATE
# # ==================================================

# if "results_df" not in st.session_state:
#     st.session_state.results_df = pd.DataFrame()

# if "markers_to_plot" not in st.session_state:
#     st.session_state.markers_to_plot = []

# if "batch_processed" not in st.session_state:
#     st.session_state.batch_processed = False

# # ==================================================
# # LOAD BARANGAY DATA
# # ==================================================

# @st.cache_resource
# def load_barangay_data():

#     gdf = gpd.read_parquet("barangays.parquet")

#     if gdf.crs != "EPSG:4326":
#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf


# with st.spinner("Loading Philippine boundary data... Please wait."):
#     brgy_gdf = load_barangay_data()

# # ==================================================
# # SIDEBAR
# # ==================================================

# st.sidebar.header("Input Options")

# input_mode = st.sidebar.radio(
#     "Choose Input Method",
#     [
#         "Single Coordinate",
#         "Batch Upload (CSV / XLSX)"
#     ]
# )

# # ==================================================
# # SINGLE COORDINATE
# # ==================================================

# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Lat/Long")

#     lat = st.sidebar.number_input(
#         "Latitude",
#         value=14.599500,
#         format="%.6f"
#     )

#     lon = st.sidebar.number_input(
#         "Longitude",
#         value=120.984200,
#         format="%.6f"
#     )

#     if st.sidebar.button("Locate Barangay"):

#         point = Point(lon, lat)

#         match = brgy_gdf[brgy_gdf.intersects(point)]

#         if not match.empty:

#             match_row = match.iloc[0]

#             st.session_state.results_df = pd.DataFrame([
#                 {
#                     "Latitude": lat,
#                     "Longitude": lon,
#                     "ADM4_PCODE": match_row.get("ADM4_PCODE", "N/A"),
#                     "Barangay": match_row.get("ADM4_EN", "N/A"),
#                     "City/Municipality": match_row.get("ADM3_EN", "N/A"),
#                     "Province": match_row.get("ADM2_EN", "N/A"),
#                     "Region": match_row.get("ADM1_EN", "N/A")
#                 }
#             ])

#             st.session_state.markers_to_plot = [
#                 (
#                     lat,
#                     lon,
#                     f"<b>{match_row.get('ADM4_EN', '')}</b>, "
#                     f"{match_row.get('ADM3_EN', '')}"
#                 )
#             ]

#         else:

#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []

#             st.warning(
#                 "Coordinates fall outside the boundaries of the loaded dataset."
#             )

# # ==================================================
# # BATCH UPLOAD
# # ==================================================

# else:

#     st.sidebar.subheader("Upload File")

#     uploaded_file = st.sidebar.file_uploader(
#         "Upload CSV or XLSX file",
#         type=["csv", "xlsx"]
#     )

#     if uploaded_file is None:
#         st.session_state.batch_processed = False

#     if uploaded_file is not None:

#         if uploaded_file.name.endswith(".csv"):
#             input_df = pd.read_csv(uploaded_file)
#         else:
#             input_df = pd.read_excel(uploaded_file)

#         if not st.session_state.batch_processed:
#             st.write("Preview of Uploaded Data")
#             st.dataframe(
#                 input_df.head(),
#                 use_container_width=True
#             )

#         lat_col = st.sidebar.selectbox(
#             "Select Latitude Column",
#             input_df.columns
#         )

#         lon_col = st.sidebar.selectbox(
#             "Select Longitude Column",
#             input_df.columns
#         )

#         if st.sidebar.button("Process Batch"):

#             st.session_state.batch_processed = True

#             with st.spinner("Performing spatial lookup..."):

#                 geometry = [
#                     Point(xy)
#                     for xy in zip(
#                         input_df[lon_col],
#                         input_df[lat_col]
#                     )
#                 ]

#                 input_gdf = gpd.GeoDataFrame(
#                     input_df.copy(),
#                     geometry=geometry,
#                     crs="EPSG:4326"
#                 )

#                 joined = gpd.sjoin(
#                     input_gdf,
#                     brgy_gdf,
#                     how="left",
#                     predicate="within"
#                 )

#                 output_list = []
#                 markers = []

#                 for _, row in joined.iterrows():

#                     lat_val = row[lat_col]
#                     lon_val = row[lon_col]

#                     result_row = row[input_df.columns].to_dict()

#                     result_row.update({
#                         "ADM4_PCODE": row.get("ADM4_PCODE", "N/A"),
#                         "Barangay": row.get("ADM4_EN", "N/A"),
#                         "City/Municipality": row.get("ADM3_EN", "N/A"),
#                         "Province": row.get("ADM2_EN", "N/A"),
#                         "Region": row.get("ADM1_EN", "N/A")
#                     })

#                     output_list.append(result_row)

#                     if pd.notna(row.get("ADM4_EN")):

#                         markers.append(
#                             (
#                                 lat_val,
#                                 lon_val,
#                                 f"<b>{row.get('ADM4_EN', '')}</b>, "
#                                 f"{row.get('ADM3_EN', '')}"
#                             )
#                         )

#                 st.session_state.results_df = pd.DataFrame(output_list)
#                 st.session_state.markers_to_plot = markers

# # ==================================================
# # RETRIEVE SAVED RESULTS
# # ==================================================

# results_df = st.session_state.results_df
# markers_to_plot = st.session_state.markers_to_plot

# # ==================================================
# # MAP + TABLE LAYOUT
# # ==================================================

# map_col, table_col = st.columns([2, 2])

# # ==================================================
# # MAP
# # ==================================================

# with map_col:

#     st.subheader("🗺️ Interactive Map")

#     map_center = [12.8797, 121.7740]

#     m = folium.Map(
#         location=map_center,
#         zoom_start=6,
#         tiles="CartoDB positron"
#     )

#     for lat, lon, popup_text in markers_to_plot:

#         folium.Marker(
#             location=[lat, lon],
#             popup=popup_text,
#             icon=folium.Icon(
#                 color="red",
#                 icon="map-marker",
#                 prefix="fa"
#             )
#         ).add_to(m)

#     if len(markers_to_plot) > 1:

#         bounds = [
#             [lat, lon]
#             for lat, lon, _ in markers_to_plot
#         ]

#         m.fit_bounds(bounds)

#     elif len(markers_to_plot) == 1:

#         m.location = [
#             markers_to_plot[0][0],
#             markers_to_plot[0][1]
#         ]

#         m.zoom_start = 14

#     st_folium(
#         m,
#         height=850,
#         use_container_width=True
#     )

# # ==================================================
# # TABLE
# # ==================================================

# with table_col:

#     st.subheader("📋 Tabular Results")

#     if not results_df.empty:

#         st.dataframe(
#             results_df,
#             use_container_width=True
#         )

#         csv_data = results_df.to_csv(
#             index=False
#         ).encode("utf-8")

#         st.download_button(
#             label="⬇️ Download Results as CSV",
#             data=csv_data,
#             file_name="barangay_lookup_results.csv",
#             mime="text/csv",
#             use_container_width=True
#         )

#     else:

#         st.info(
#             "Input a coordinate or upload a file to view tabular results."
#         )



# add adm4_pcode in the results

# import streamlit as st
# import pandas as pd
# import geopandas as gpd
# from shapely.geometry import Point
# import folium
# from streamlit_folium import st_folium

# # Page configuration
# st.set_page_config(
#     page_title="PH Barangay Coordinate Locator",
#     layout="wide"
# )

# st.title("🇵🇭 Philippine Barangay Spatial Locator")

# st.markdown(
#     """
#     Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates
#     to identify their corresponding **Barangay, City, Province, Region, and ADM4_PCODE**
#     using your barangay boundary dataset.
#     """
# )

# # Initialize session state
# if "results_df" not in st.session_state:
#     st.session_state.results_df = pd.DataFrame()

# if "markers_to_plot" not in st.session_state:
#     st.session_state.markers_to_plot = []

# # Load Barangay Data
# @st.cache_resource
# def load_barangay_data():
#     gdf = gpd.read_parquet("barangays.parquet")

#     if gdf.crs != "EPSG:4326":
#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf

# with st.spinner("Loading Philippine boundary data... Please wait."):
#     brgy_gdf = load_barangay_data()

# # Sidebar
# st.sidebar.header("Input Options")

# input_mode = st.sidebar.radio(
#     "Choose Input Method",
#     [
#         "Single Coordinate",
#         "Batch Upload (CSV / XLSX)"
#     ]
# )

# # --------------------------------------------------
# # SINGLE COORDINATE MODE
# # --------------------------------------------------
# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Lat/Long")

#     lat = st.sidebar.number_input(
#         "Latitude",
#         value=14.5995,
#         format="%.6f"
#     )

#     lon = st.sidebar.number_input(
#         "Longitude",
#         value=120.9842,
#         format="%.6f"
#     )

#     if st.sidebar.button("Locate Barangay"):

#         point = Point(lon, lat)

#         match = brgy_gdf[brgy_gdf.contains(point)]

#         if not match.empty:

#             match_row = match.iloc[0]

#             st.session_state.results_df = pd.DataFrame([
#                 {
#                     "Latitude": lat,
#                     "Longitude": lon,
#                     "ADM4_PCODE": match_row.get("ADM4_PCODE", "N/A"),
#                     "Barangay": match_row.get("ADM4_EN", "N/A"),
#                     "City/Municipality": match_row.get("ADM3_EN", "N/A"),
#                     "Province": match_row.get("ADM2_EN", "N/A"),
#                     "Region": match_row.get("ADM1_EN", "N/A")
#                 }
#             ])

#             st.session_state.markers_to_plot = [
#                 (
#                     lat,
#                     lon,
#                     f"<b>{match_row.get('ADM4_EN', '')}</b>, "
#                     f"{match_row.get('ADM3_EN', '')}"
#                 )
#             ]

#         else:
#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []

#             st.warning(
#                 "Coordinates fall outside the boundaries of the loaded dataset."
#             )

# # --------------------------------------------------
# # BATCH UPLOAD MODE
# # --------------------------------------------------
# else:

#     st.sidebar.subheader("Upload File")

#     uploaded_file = st.sidebar.file_uploader(
#         "Upload CSV or XLSX file",
#         type=["csv", "xlsx"]
#     )

#     if uploaded_file is not None:

#         if uploaded_file.name.endswith(".csv"):
#             input_df = pd.read_csv(uploaded_file)
#         else:
#             input_df = pd.read_excel(uploaded_file)

#         st.write("Preview of Uploaded Data")
#         st.dataframe(input_df.head())

#         lat_col = st.sidebar.selectbox(
#             "Select Latitude Column",
#             input_df.columns
#         )

#         lon_col = st.sidebar.selectbox(
#             "Select Longitude Column",
#             input_df.columns
#         )

#         if st.sidebar.button("Process Batch"):

#             with st.spinner("Performing spatial lookup..."):

#                 # Create point geometries
#                 geometry = [
#                     Point(xy)
#                     for xy in zip(
#                         input_df[lon_col],
#                         input_df[lat_col]
#                     )
#                 ]

#                 input_gdf = gpd.GeoDataFrame(
#                     input_df.copy(),
#                     geometry=geometry,
#                     crs="EPSG:4326"
#                 )

#                 # Spatial join
#                 joined = gpd.sjoin(
#                     input_gdf,
#                     brgy_gdf,
#                     how="left",
#                     predicate="within"
#                 )

#                 output_list = []
#                 markers = []

#                 for _, row in joined.iterrows():

#                     lat_val = row[lat_col]
#                     lon_val = row[lon_col]

#                     # Preserve all uploaded columns
#                     result_row = row[input_df.columns].to_dict()

#                     result_row.update({
#                         "ADM4_PCODE": row.get("ADM4_PCODE", "N/A"),
#                         "Barangay": row.get("ADM4_EN", "N/A"),
#                         "City/Municipality": row.get("ADM3_EN", "N/A"),
#                         "Province": row.get("ADM2_EN", "N/A"),
#                         "Region": row.get("ADM1_EN", "N/A")
#                     })

#                     output_list.append(result_row)

#                     if pd.notna(row.get("ADM4_EN")):

#                         markers.append(
#                             (
#                                 lat_val,
#                                 lon_val,
#                                 f"<b>{row.get('ADM4_EN', '')}</b>, "
#                                 f"{row.get('ADM3_EN', '')}"
#                             )
#                         )

#                 st.session_state.results_df = pd.DataFrame(output_list)
#                 st.session_state.markers_to_plot = markers

# # --------------------------------------------------
# # RETRIEVE SAVED RESULTS
# # --------------------------------------------------
# results_df = st.session_state.results_df
# markers_to_plot = st.session_state.markers_to_plot

# # --------------------------------------------------
# # MAP
# # --------------------------------------------------
# st.subheader("🗺️ Interactive Map")

# map_center = [14.5995, 120.9842]
# zoom_start = 11

# if markers_to_plot:
#     map_center = [
#         markers_to_plot[0][0],
#         markers_to_plot[0][1]
#     ]

# m = folium.Map(
#     location=map_center,
#     zoom_start=zoom_start
# )

# for lat, lon, popup_text in markers_to_plot:

#     folium.Marker(
#         location=[lat, lon],
#         popup=popup_text,
#         icon=folium.Icon(
#             color="red",
#             icon="map-marker",
#             prefix="fa"
#         )
#     ).add_to(m)

# st_folium(
#     m,
#     width=700,
#     height=450,
#     use_container_width=True
# )

# # --------------------------------------------------
# # RESULTS TABLE
# # --------------------------------------------------
# st.markdown("---")

# st.subheader("📋 Tabular Results")

# if not results_df.empty:

#     st.dataframe(
#         results_df,
#         use_container_width=True
#     )

#     csv_data = results_df.to_csv(
#         index=False
#     ).encode("utf-8")

#     st.download_button(
#         label="Download Results as CSV",
#         data=csv_data,
#         file_name="barangay_lookup_results.csv",
#         mime="text/csv"
#     )

# else:
#     st.info(
#         "Input a coordinate or upload a file to view tabular results."
#     )



# as of aug 10 2026

# import streamlit as st
# import pandas as pd
# import geopandas as gpd
# from shapely.geometry import Point
# import folium
# from streamlit_folium import st_folium

# # Page configuration
# st.set_page_config(
#     page_title="PH Barangay Coordinate Locator",
#     layout="wide"
# )

# st.title("🇵🇭 Philippine Barangay Spatial Locator")

# st.markdown(
#     """
#     Enter a single coordinate or upload a CSV/XLSX file containing multiple coordinates 
#     to identify their corresponding **Barangay, City, Province, and Region**.
#     """
# )

# # Initialize session state
# if "results_df" not in st.session_state:
#     st.session_state.results_df = pd.DataFrame()

# if "markers_to_plot" not in st.session_state:
#     st.session_state.markers_to_plot = []

# # Load Barangay GeoJSON / Parquet Data
# @st.cache_resource
# def load_barangay_data():
#     gdf = gpd.read_parquet("barangays.parquet")

#     # Ensure WGS84 coordinate reference system
#     if gdf.crs != "EPSG:4326":
#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf

# with st.spinner("Loading Philippine boundary data... Please wait."):
#     brgy_gdf = load_barangay_data()

# # Sidebar options
# st.sidebar.header("Input Options")

# input_mode = st.sidebar.radio(
#     "Choose Input Method",
#     ["Single Coordinate", "Batch Upload (CSV / XLSX)"]
# )

# # Single coordinate mode
# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Lat/Long")

#     lat = st.sidebar.number_input(
#         "Latitude",
#         value=14.5995,
#         format="%.6f"
#     )

#     lon = st.sidebar.number_input(
#         "Longitude",
#         value=120.9842,
#         format="%.6f"
#     )

#     if st.sidebar.button("Locate Barangay"):

#         point = Point(lon, lat)

#         # Find polygon containing point
#         match = brgy_gdf[brgy_gdf.contains(point)]

#         if not match.empty:

#             match_row = match.iloc[0]

#             st.session_state.results_df = pd.DataFrame([
#                 {
#                     "Latitude": lat,
#                     "Longitude": lon,
#                     "Barangay": match_row.get("ADM4_EN", "N/A"),
#                     "City/Municipality": match_row.get("ADM3_EN", "N/A"),
#                     "Province": match_row.get("ADM2_EN", "N/A"),
#                     "Region": match_row.get("ADM1_EN", "N/A")
#                 }
#             ])

#             st.session_state.markers_to_plot = [
#                 (
#                     lat,
#                     lon,
#                     f"<b>{match_row.get('ADM4_EN', '')}</b>, {match_row.get('ADM3_EN', '')}"
#                 )
#             ]

#         else:
#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []
#             st.warning("Coordinates fall outside the boundaries of the loaded GeoJSON file.")

# # Batch upload mode
# else:

#     st.sidebar.subheader("Upload File")

#     uploaded_file = st.sidebar.file_uploader(
#         "Upload CSV or XLSX file",
#         type=["csv", "xlsx"]
#     )

#     if uploaded_file is not None:

#         if uploaded_file.name.endswith(".csv"):
#             input_df = pd.read_csv(uploaded_file)
#         else:
#             input_df = pd.read_excel(uploaded_file)

#         lat_col = st.sidebar.selectbox(
#             "Select Latitude Column",
#             input_df.columns
#         )

#         lon_col = st.sidebar.selectbox(
#             "Select Longitude Column",
#             input_df.columns
#         )

#         if st.sidebar.button("Process Batch"):

#             with st.spinner("Processing spatial lookup..."):

#                 # Convert input dataframe to GeoDataFrame
#                 geometry = [
#                     Point(xy)
#                     for xy in zip(input_df[lon_col], input_df[lat_col])
#                 ]

#                 input_gdf = gpd.GeoDataFrame(
#                     input_df,
#                     geometry=geometry,
#                     crs="EPSG:4326"
#                 )

#                 # Spatial join
#                 joined = gpd.sjoin(
#                     input_gdf,
#                     brgy_gdf,
#                     how="left",
#                     predicate="within"
#                 )

#                 output_list = []
#                 markers = []

#                 for idx, row in joined.iterrows():

#                     lat_val = row[lat_col]
#                     lon_val = row[lon_col]

#                     brgy = row.get("ADM4_EN", "N/A")
#                     city = row.get("ADM3_EN", "N/A")
#                     prov = row.get("ADM2_EN", "N/A")
#                     reg = row.get("ADM1_EN", "N/A")

#                     output_list.append(
#                         {
#                             "Latitude": lat_val,
#                             "Longitude": lon_val,
#                             "Barangay": brgy,
#                             "City/Municipality": city,
#                             "Province": prov,
#                             "Region": reg
#                         }
#                     )

#                     if pd.notna(brgy) and brgy != "N/A":
#                         markers.append(
#                             (
#                                 lat_val,
#                                 lon_val,
#                                 f"<b>{brgy}</b>, {city}"
#                             )
#                         )

#                 st.session_state.results_df = pd.DataFrame(output_list)
#                 st.session_state.markers_to_plot = markers

# # Retrieve saved state
# results_df = st.session_state.results_df
# markers_to_plot = st.session_state.markers_to_plot

# # Map section
# st.subheader("🗺️ Interactive Map")

# # Default center to Metro Manila if no markers yet
# map_center = [14.5995, 120.9842]
# zoom_start = 11

# if markers_to_plot:
#     map_center = [
#         markers_to_plot[0][0],
#         markers_to_plot[0][1]
#     ]

# m = folium.Map(
#     location=map_center,
#     zoom_start=zoom_start
# )

# # Add markers
# for lat, lon, popup_text in markers_to_plot:

#     folium.Marker(
#         location=[lat, lon],
#         popup=popup_text,
#         icon=folium.Icon(
#             color="red",
#             icon="map-marker",
#             prefix="fa"
#         )
#     ).add_to(m)

# st_folium(
#     m,
#     width=700,
#     height=450,
#     use_container_width=True
# )

# st.markdown("---")

# # Table section
# st.subheader("📋 Tabular Results")

# if not results_df.empty:

#     st.dataframe(
#         results_df,
#         use_container_width=True
#     )

#     csv_data = results_df.to_csv(index=False).encode("utf-8")

#     st.download_button(
#         label="Download Results as CSV",
#         data=csv_data,
#         file_name="barangay_lookup_results.csv",
#         mime="text/csv"
#     )

# else:
#     st.info("Input a coordinate or upload a file to view tabular results.")

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
