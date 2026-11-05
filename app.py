# ============================================================
# PHILIPPINE BARANGAY SPATIAL LOCATOR
# ============================================================

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium

from shapely.geometry import Point
from streamlit_folium import st_folium


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="PH Barangay Spatial Locator",
    page_icon="🇵🇭",
    layout="wide"
)

st.title("🇵🇭 PH Philippine Barangay Spatial Locator")

st.markdown(
    """
    Enter a single coordinate or upload a CSV/XLSX file containing multiple
    coordinates to identify the corresponding **Barangay, City/Municipality,
    Province, Region, and ADM4_PCODE**.

    Matched barangays are displayed with both a **location pin** and a
    **highlighted barangay boundary**.
    """
)


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_MAP_CENTER = [12.8797, 121.7740]
DEFAULT_MAP_ZOOM = 6

# Normal matched barangay
MATCHED_BORDER = "#1976D2"
MATCHED_FILL = "#42A5F5"

# Currently selected barangay
SELECTED_BORDER = "#0D47A1"
SELECTED_FILL = "#1976D2"


# ============================================================
# SESSION STATE
# ============================================================

if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()

if "markers_to_plot" not in st.session_state:
    st.session_state.markers_to_plot = []

if "matched_barangay_codes" not in st.session_state:
    st.session_state.matched_barangay_codes = []

if "selected_point" not in st.session_state:
    st.session_state.selected_point = None

if "selected_barangay_code" not in st.session_state:
    st.session_state.selected_barangay_code = None

if "batch_processed" not in st.session_state:
    st.session_state.batch_processed = False

if "uploaded_file_id" not in st.session_state:
    st.session_state.uploaded_file_id = None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_value(value, default="N/A"):
    """
    Convert missing values into a display-friendly value.
    """

    if pd.isna(value):
        return default

    return value


def reset_results():
    """
    Clear all saved lookup results.
    """

    st.session_state.results_df = pd.DataFrame()

    st.session_state.markers_to_plot = []

    st.session_state.matched_barangay_codes = []

    st.session_state.selected_point = None

    st.session_state.selected_barangay_code = None


def build_popup(
    barangay,
    city,
    province,
    region,
    pcode
):
    """
    Build HTML popup displayed when clicking map markers.
    """

    return f"""
        <div style="font-size:13px;">
            <b>Barangay:</b> {barangay}<br>
            <b>City/Municipality:</b> {city}<br>
            <b>Province:</b> {province}<br>
            <b>Region:</b> {region}<br>
            <b>ADM4_PCODE:</b> {pcode}
        </div>
    """


# ============================================================
# LOAD BARANGAY DATA
# ============================================================

@st.cache_resource
def load_barangay_data():

    gdf = gpd.read_parquet(
        "barangays.parquet"
    )

    required_columns = [
        "ADM4_PCODE",
        "ADM4_EN",
        "ADM3_EN",
        "ADM2_EN",
        "ADM1_EN",
        "geometry"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in gdf.columns
    ]

    if missing_columns:

        raise ValueError(
            "barangays.parquet is missing: "
            + ", ".join(missing_columns)
        )

    if gdf.crs is None:

        raise ValueError(
            "barangays.parquet does not have a CRS."
        )

    if gdf.crs.to_string() != "EPSG:4326":

        gdf = gdf.to_crs(
            "EPSG:4326"
        )

    gdf = gdf[
        [
            "ADM4_PCODE",
            "ADM4_EN",
            "ADM3_EN",
            "ADM2_EN",
            "ADM1_EN",
            "geometry"
        ]
    ].copy()

    return gdf


try:

    with st.spinner(
        "Loading Philippine barangay boundary data..."
    ):

        brgy_gdf = load_barangay_data()

except Exception as error:

    st.error(
        f"Unable to load barangay data: {error}"
    )

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Input Options")


# ============================================================
# INPUT METHOD
# ============================================================

input_mode = st.sidebar.radio(
    "Choose Input Method",
    [
        "Single Coordinate",
        "Batch Upload (CSV / XLSX)"
    ],
    label_visibility="collapsed"
)


# ============================================================
# MAP SETTINGS
# ============================================================

st.sidebar.divider()

st.sidebar.subheader(
    "Map Settings"
)

basemap_name = st.sidebar.selectbox(
    "Select Basemap",
    [
        "OpenStreetMap",
        "OpenStreetMap HOT",
        "OpenTopoMap"
    ],
    index=0
)


# ============================================================
# BASEMAP DEFINITIONS
# ============================================================

BASEMAPS = {

    "OpenStreetMap": {

        "tiles":
            "https://{s}.tile.openstreetmap.org/"
            "{z}/{x}/{y}.png",

        "attr":
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            'OpenStreetMap contributors'
            '</a>',

        "max_zoom": 19
    },

    "OpenStreetMap HOT": {

        "tiles":
            "https://{s}.tile.openstreetmap.fr/hot/"
            "{z}/{x}/{y}.png",

        "attr":
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            'OpenStreetMap contributors'
            '</a>, '
            'Tiles style by Humanitarian '
            'OpenStreetMap Team',

        "max_zoom": 19
    },

    "OpenTopoMap": {

        "tiles":
            "https://{s}.tile.opentopomap.org/"
            "{z}/{x}/{y}.png",

        "attr":
            'Map data: '
            '&copy; '
            '<a href="https://www.openstreetmap.org/copyright">'
            'OpenStreetMap contributors'
            '</a> | '
            'Map style: '
            '&copy; OpenTopoMap',

        "max_zoom": 17
    }
}


selected_basemap = (
    BASEMAPS[basemap_name]
)


# ============================================================
# SINGLE COORDINATE
# ============================================================

if input_mode == "Single Coordinate":

    st.sidebar.divider()

    st.sidebar.subheader(
        "Enter Latitude and Longitude"
    )

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

    locate_button = st.sidebar.button(
        "Locate Barangay",
        type="primary",
        use_container_width=True
    )

    if locate_button:

        point = Point(
            lon,
            lat
        )

        match = brgy_gdf[
            brgy_gdf.geometry.intersects(
                point
            )
        ]

        if not match.empty:

            match_row = (
                match.iloc[0]
            )

            barangay = safe_value(
                match_row["ADM4_EN"]
            )

            city = safe_value(
                match_row["ADM3_EN"]
            )

            province = safe_value(
                match_row["ADM2_EN"]
            )

            region = safe_value(
                match_row["ADM1_EN"]
            )

            pcode = safe_value(
                match_row["ADM4_PCODE"]
            )

            # ----------------------------------------
            # SAVE TABLE RESULT
            # ----------------------------------------

            st.session_state.results_df = (
                pd.DataFrame(
                    [
                        {
                            "Latitude":
                                float(lat),

                            "Longitude":
                                float(lon),

                            "ADM4_PCODE":
                                pcode,

                            "Barangay":
                                barangay,

                            "City/Municipality":
                                city,

                            "Province":
                                province,

                            "Region":
                                region
                        }
                    ]
                )
            )

            # ----------------------------------------
            # SAVE MAP MARKER
            # ----------------------------------------

            popup_text = build_popup(
                barangay,
                city,
                province,
                region,
                pcode
            )

            st.session_state.markers_to_plot = [
                {
                    "lat":
                        float(lat),

                    "lon":
                        float(lon),

                    "popup":
                        popup_text,

                    "pcode":
                        pcode
                }
            ]

            # ----------------------------------------
            # SAVE BARANGAY POLYGON
            # ----------------------------------------

            st.session_state.matched_barangay_codes = [
                pcode
            ]

            # Automatically treat single result
            # as selected.

            st.session_state.selected_point = {

                "lat":
                    float(lat),

                "lon":
                    float(lon),

                "label":
                    barangay,

                "pcode":
                    pcode
            }

            st.session_state.selected_barangay_code = (
                pcode
            )

        else:

            reset_results()

            st.warning(
                "The coordinate falls outside "
                "the loaded barangay boundaries."
            )


# ============================================================
# BATCH UPLOAD
# ============================================================

else:

    st.sidebar.divider()

    st.sidebar.subheader(
        "Upload Coordinate File"
    )

    uploaded_file = (
        st.sidebar.file_uploader(
            "Upload CSV or XLSX",
            type=[
                "csv",
                "xlsx"
            ]
        )
    )

    if uploaded_file is None:

        st.session_state.batch_processed = (
            False
        )

        st.session_state.uploaded_file_id = (
            None
        )

    else:

        current_file_id = (
            uploaded_file.name,
            uploaded_file.size
        )

        if (
            st.session_state.uploaded_file_id
            != current_file_id
        ):

            st.session_state.uploaded_file_id = (
                current_file_id
            )

            st.session_state.batch_processed = (
                False
            )

            reset_results()

        # ====================================================
        # READ FILE
        # ====================================================

        try:

            if (
                uploaded_file
                .name
                .lower()
                .endswith(".csv")
            ):

                input_df = pd.read_csv(
                    uploaded_file
                )

            else:

                input_df = pd.read_excel(
                    uploaded_file
                )

        except Exception as error:

            st.error(
                f"Unable to read uploaded file: {error}"
            )

            st.stop()

        if input_df.empty:

            st.warning(
                "The uploaded file contains "
                "no records."
            )

            st.stop()


        # ====================================================
        # DATA PREVIEW
        # ====================================================

        if not st.session_state.batch_processed:

            st.markdown(
                "### Preview of Uploaded Data"
            )

            st.dataframe(
                input_df.head(),
                use_container_width=True,
                hide_index=True
            )


        # ====================================================
        # DETECT COORDINATE COLUMNS
        # ====================================================

        available_columns = (
            input_df.columns.tolist()
        )

        latitude_candidates = [

            column

            for column in available_columns

            if str(column).strip().lower()
            in [
                "latitude",
                "lat",
                "y"
            ]
        ]

        longitude_candidates = [

            column

            for column in available_columns

            if str(column).strip().lower()
            in [
                "longitude",
                "long",
                "lon",
                "lng",
                "x"
            ]
        ]


        if latitude_candidates:

            default_lat_index = (
                available_columns.index(
                    latitude_candidates[0]
                )
            )

        else:

            default_lat_index = 0


        if longitude_candidates:

            default_lon_index = (
                available_columns.index(
                    longitude_candidates[0]
                )
            )

        elif len(
            available_columns
        ) > 1:

            default_lon_index = 1

        else:

            default_lon_index = 0


        # ====================================================
        # COLUMN SELECTORS
        # ====================================================

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


        process_button = st.sidebar.button(
            "Process Batch",
            type="primary",
            use_container_width=True
        )


        # ====================================================
        # PROCESS BATCH
        # ====================================================

        if process_button:

            if lat_col == lon_col:

                st.error(
                    "Latitude and longitude "
                    "must use different columns."
                )

            else:

                working_df = (
                    input_df.copy()
                )

                # Unique source row ID ensures spatial
                # join duplicates can be handled.

                working_df["_SOURCE_ROW_ID"] = (
                    range(
                        len(working_df)
                    )
                )


                # =================================================
                # CONVERT COORDINATES
                # =================================================

                working_df[lat_col] = (
                    pd.to_numeric(
                        working_df[lat_col],
                        errors="coerce"
                    )
                )

                working_df[lon_col] = (
                    pd.to_numeric(
                        working_df[lon_col],
                        errors="coerce"
                    )
                )


                # =================================================
                # VALIDATE COORDINATES
                # =================================================

                valid_mask = (

                    working_df[
                        lat_col
                    ].between(
                        -90,
                        90
                    )

                    &

                    working_df[
                        lon_col
                    ].between(
                        -180,
                        180
                    )

                )


                invalid_count = int(
                    (
                        ~valid_mask
                    ).sum()
                )


                valid_df = (
                    working_df[
                        valid_mask
                    ].copy()
                )


                if valid_df.empty:

                    reset_results()

                    st.error(
                        "No valid coordinates "
                        "were found."
                    )

                else:

                    st.session_state.batch_processed = (
                        True
                    )

                    st.session_state.selected_point = (
                        None
                    )

                    st.session_state.selected_barangay_code = (
                        None
                    )


                    # =================================================
                    # CREATE POINT GEOMETRY
                    # =================================================

                    with st.spinner(
                        "Performing spatial lookup..."
                    ):

                        geometry = (
                            gpd.points_from_xy(
                                valid_df[
                                    lon_col
                                ],
                                valid_df[
                                    lat_col
                                ]
                            )
                        )


                        input_gdf = (
                            gpd.GeoDataFrame(
                                valid_df.copy(),
                                geometry=geometry,
                                crs="EPSG:4326"
                            )
                        )


                        # =================================================
                        # SPATIAL JOIN
                        # =================================================

                        joined = gpd.sjoin(
                            input_gdf,
                            brgy_gdf,
                            how="left",
                            predicate="within"
                        )


                        # =================================================
                        # REMOVE DUPLICATE JOIN RESULTS
                        # =================================================

                        joined = (
                            joined
                            .sort_values(
                                "_SOURCE_ROW_ID"
                            )
                            .drop_duplicates(
                                subset="_SOURCE_ROW_ID",
                                keep="first"
                            )
                            .copy()
                        )


                        output_list = []
                        markers = []
                        matched_codes = []


                        # =================================================
                        # BUILD OUTPUT
                        # =================================================

                        for _, row in (
                            joined.iterrows()
                        ):

                            lat_val = (
                                row[lat_col]
                            )

                            lon_val = (
                                row[lon_col]
                            )


                            result_row = {

                                column:
                                    row.get(
                                        column
                                    )

                                for column
                                in input_df.columns

                            }


                            barangay = safe_value(
                                row.get(
                                    "ADM4_EN"
                                )
                            )

                            city = safe_value(
                                row.get(
                                    "ADM3_EN"
                                )
                            )

                            province = safe_value(
                                row.get(
                                    "ADM2_EN"
                                )
                            )

                            region = safe_value(
                                row.get(
                                    "ADM1_EN"
                                )
                            )

                            pcode = safe_value(
                                row.get(
                                    "ADM4_PCODE"
                                )
                            )


                            result_row.update(
                                {

                                    "Latitude":
                                        float(
                                            lat_val
                                        ),

                                    "Longitude":
                                        float(
                                            lon_val
                                        ),

                                    "ADM4_PCODE":
                                        pcode,

                                    "Barangay":
                                        barangay,

                                    "City/Municipality":
                                        city,

                                    "Province":
                                        province,

                                    "Region":
                                        region
                                }
                            )


                            output_list.append(
                                result_row
                            )


                            # =================================================
                            # MAP RESULTS
                            # =================================================

                            if pcode != "N/A":

                                popup_text = (
                                    build_popup(
                                        barangay,
                                        city,
                                        province,
                                        region,
                                        pcode
                                    )
                                )


                                markers.append(
                                    {

                                        "lat":
                                            float(
                                                lat_val
                                            ),

                                        "lon":
                                            float(
                                                lon_val
                                            ),

                                        "popup":
                                            popup_text,

                                        "pcode":
                                            pcode
                                    }
                                )


                                matched_codes.append(
                                    pcode
                                )


                        # =================================================
                        # SAVE RESULTS
                        # =================================================

                        st.session_state.results_df = (
                            pd.DataFrame(
                                output_list
                            )
                        )


                        st.session_state.markers_to_plot = (
                            markers
                        )


                        # Deduplicate barangays

                        st.session_state.matched_barangay_codes = (
                            list(
                                dict.fromkeys(
                                    matched_codes
                                )
                            )
                        )


                    if invalid_count > 0:

                        st.warning(
                            f"{invalid_count:,} "
                            f"record(s) were excluded "
                            f"due to invalid coordinates."
                        )


# ============================================================
# GET SAVED STATE
# ============================================================

results_df = (
    st.session_state.results_df
)

markers_to_plot = (
    st.session_state.markers_to_plot
)

matched_barangay_codes = (
    st.session_state.matched_barangay_codes
)


# ============================================================
# MAIN LAYOUT
# ============================================================

map_col, table_col = (
    st.columns(
        [1.3, 1],
        gap="large"
    )
)


# ============================================================
# TABLE
# Table rendered BEFORE map so selected row controls map.
# ============================================================

with table_col:

    st.subheader(
        "📋 Tabular Results"
    )


    if not results_df.empty:

        row_count = (
            len(results_df)
        )

        table_height = min(
            max(
                90
                + (
                    row_count
                    * 35
                ),
                160
            ),
            650
        )


        table_event = (
            st.dataframe(
                results_df,
                use_container_width=True,
                height=table_height,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="results_table"
            )
        )


        # ====================================================
        # HANDLE TABLE SELECTION
        # ====================================================

        selected_rows = (
            table_event
            .selection
            .rows
        )


        if selected_rows:

            row_index = (
                selected_rows[0]
            )

            selected_row = (
                results_df.iloc[
                    row_index
                ]
            )


            selected_lat = (
                selected_row.get(
                    "Latitude"
                )
            )

            selected_lon = (
                selected_row.get(
                    "Longitude"
                )
            )

            selected_pcode = (
                selected_row.get(
                    "ADM4_PCODE"
                )
            )


            if (
                pd.notna(
                    selected_lat
                )
                and
                pd.notna(
                    selected_lon
                )
            ):

                st.session_state.selected_point = {

                    "lat":
                        float(
                            selected_lat
                        ),

                    "lon":
                        float(
                            selected_lon
                        ),

                    "label":
                        selected_row.get(
                            "Barangay",
                            ""
                        ),

                    "pcode":
                        selected_pcode
                }


                st.session_state.selected_barangay_code = (
                    selected_pcode
                )


        # ====================================================
        # DOWNLOAD RESULTS
        # ====================================================

        csv_data = (
            results_df
            .to_csv(
                index=False
            )
            .encode(
                "utf-8-sig"
            )
        )


        st.download_button(
            label="⬇️ Download Results as CSV",
            data=csv_data,
            file_name=(
                "barangay_lookup_results.csv"
            ),
            mime="text/csv",
            use_container_width=True
        )


    else:

        st.session_state.selected_point = (
            None
        )

        st.session_state.selected_barangay_code = (
            None
        )

        st.info(
            "Input a coordinate or upload "
            "a file to view tabular results."
        )


# ============================================================
# MAP
# ============================================================

with map_col:

    st.subheader(
        "🗺️ Interactive Map"
    )


    selected_point = (
        st.session_state.selected_point
    )

    selected_barangay_code = (
        st.session_state.selected_barangay_code
    )


    # ========================================================
    # DEFAULT MAP POSITION
    # ========================================================

    map_center = (
        DEFAULT_MAP_CENTER.copy()
    )

    zoom_start = (
        DEFAULT_MAP_ZOOM
    )


    if selected_point is not None:

        map_center = [

            selected_point[
                "lat"
            ],

            selected_point[
                "lon"
            ]
        ]

        zoom_start = 15


    # ========================================================
    # CREATE MAP
    # ========================================================

    m = folium.Map(
        location=map_center,
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
        prefer_canvas=True
    )


    # ========================================================
    # BASEMAP
    # ========================================================

    folium.TileLayer(
        tiles=(
            selected_basemap[
                "tiles"
            ]
        ),
        attr=(
            selected_basemap[
                "attr"
            ]
        ),
        name=basemap_name,
        max_zoom=(
            selected_basemap[
                "max_zoom"
            ]
        ),
        overlay=False,
        control=False
    ).add_to(m)


    # ========================================================
    # GET MATCHED BARANGAY POLYGONS
    # ========================================================

    matched_barangays_gdf = (
        brgy_gdf.iloc[
            0:0
        ].copy()
    )


    if matched_barangay_codes:

        matched_barangays_gdf = (
            brgy_gdf[
                brgy_gdf[
                    "ADM4_PCODE"
                ]
                .astype(str)
                .isin(
                    [
                        str(code)
                        for code
                        in matched_barangay_codes
                    ]
                )
            ]
            .copy()
        )


    # ========================================================
    # DRAW BARANGAY BOUNDARIES
    # ========================================================

    if not matched_barangays_gdf.empty:

        for _, barangay_row in (
            matched_barangays_gdf
            .iterrows()
        ):

            polygon_pcode = (
                barangay_row[
                    "ADM4_PCODE"
                ]
            )


            # Determine whether the polygon
            # is the currently selected barangay.

            is_selected = (

                selected_barangay_code
                is not None

                and

                str(
                    polygon_pcode
                )
                ==
                str(
                    selected_barangay_code
                )
            )


            # =================================================
            # POLYGON COLORS
            # =================================================

            if is_selected:

                outline_color = (
                    SELECTED_BORDER
                )

                fill_color = (
                    SELECTED_FILL
                )

                weight = 4

                fill_opacity = 0.30

            else:

                outline_color = (
                    MATCHED_BORDER
                )

                fill_color = (
                    MATCHED_FILL
                )

                weight = 2.5

                fill_opacity = 0.18


            # =================================================
            # ONE-ROW GEODATAFRAME
            # =================================================

            barangay_feature = (
                gpd.GeoDataFrame(
                    [
                        barangay_row
                    ],
                    geometry="geometry",
                    crs=brgy_gdf.crs
                )
            )


            # =================================================
            # BARANGAY TOOLTIP
            # =================================================

            barangay_name = (
                safe_value(
                    barangay_row.get(
                        "ADM4_EN"
                    )
                )
            )

            city_name = (
                safe_value(
                    barangay_row.get(
                        "ADM3_EN"
                    )
                )
            )

            province_name = (
                safe_value(
                    barangay_row.get(
                        "ADM2_EN"
                    )
                )
            )

            region_name = (
                safe_value(
                    barangay_row.get(
                        "ADM1_EN"
                    )
                )
            )


            polygon_tooltip = (
                folium.GeoJsonTooltip(
                    fields=[
                        "ADM4_EN",
                        "ADM3_EN",
                        "ADM2_EN",
                        "ADM1_EN",
                        "ADM4_PCODE"
                    ],
                    aliases=[
                        "Barangay:",
                        "City/Municipality:",
                        "Province:",
                        "Region:",
                        "ADM4_PCODE:"
                    ],
                    sticky=False,
                    labels=True
                )
            )


            # =================================================
            # POLYGON POPUP
            # =================================================

            polygon_popup = folium.Popup(
                build_popup(
                    barangay_name,
                    city_name,
                    province_name,
                    region_name,
                    polygon_pcode
                ),
                max_width=350
            )


            # =================================================
            # ADD POLYGON TO MAP
            # =================================================

            folium.GeoJson(
                data=(
                    barangay_feature
                    .to_json()
                ),
                name=(
                    f"Barangay: "
                    f"{barangay_name}"
                ),
                style_function=(
                    lambda feature,
                    outline=outline_color,
                    fill=fill_color,
                    w=weight,
                    opacity=fill_opacity:
                    {
                        "fillColor":
                            fill,

                        "color":
                            outline,

                        "weight":
                            w,

                        "fillOpacity":
                            opacity
                    }
                ),
                highlight_function=(
                    lambda feature:
                    {
                        "fillColor":
                            "#FFD54F",

                        "color":
                            "#FF8F00",

                        "weight":
                            4,

                        "fillOpacity":
                            0.35
                    }
                ),
                tooltip=(
                    polygon_tooltip
                ),
                popup=(
                    polygon_popup
                ),
                zoom_on_click=False
            ).add_to(m)


    # ========================================================
    # DRAW PINS
    # ========================================================

    for marker in markers_to_plot:

        marker_lat = (
            marker["lat"]
        )

        marker_lon = (
            marker["lon"]
        )

        marker_pcode = (
            marker["pcode"]
        )

        popup_text = (
            marker["popup"]
        )


        # Default pin style
        marker_color = "red"
        marker_icon = "map-marker"


        # ====================================================
        # SELECTED PIN
        # ====================================================

        if (
            selected_point
            is not None
        ):

            lat_difference = abs(
                float(
                    marker_lat
                )
                -
                float(
                    selected_point[
                        "lat"
                    ]
                )
            )

            lon_difference = abs(
                float(
                    marker_lon
                )
                -
                float(
                    selected_point[
                        "lon"
                    ]
                )
            )


            if (
                lat_difference
                < 0.000001
                and
                lon_difference
                < 0.000001
            ):

                marker_color = "blue"

                marker_icon = (
                    "info-sign"
                )


        # ====================================================
        # ADD PIN
        # ====================================================

        folium.Marker(
            location=[
                float(
                    marker_lat
                ),
                float(
                    marker_lon
                )
            ],
            tooltip=(
                "Click to view location details"
            ),
            popup=(
                folium.Popup(
                    popup_text,
                    max_width=350
                )
            ),
            icon=(
                folium.Icon(
                    color=marker_color,
                    icon=marker_icon,
                    prefix="fa"
                )
            )
        ).add_to(m)


    # ========================================================
    # AUTOMATIC MAP ZOOM
    # ========================================================

    if (
        selected_point is not None
        and
        selected_barangay_code
        is not None
    ):

        selected_barangay_gdf = (
            brgy_gdf[
                brgy_gdf[
                    "ADM4_PCODE"
                ]
                .astype(str)
                ==
                str(
                    selected_barangay_code
                )
            ]
        )


        if not selected_barangay_gdf.empty:

            (
                min_x,
                min_y,
                max_x,
                max_y
            ) = (
                selected_barangay_gdf
                .total_bounds
            )


            m.fit_bounds(
                [
                    [
                        min_y,
                        min_x
                    ],
                    [
                        max_y,
                        max_x
                    ]
                ],
                padding=[
                    30,
                    30
                ],
                max_zoom=16
            )


    elif not matched_barangays_gdf.empty:

        (
            min_x,
            min_y,
            max_x,
            max_y
        ) = (
            matched_barangays_gdf
            .total_bounds
        )


        m.fit_bounds(
            [
                [
                    min_y,
                    min_x
                ],
                [
                    max_y,
                    max_x
                ]
            ],
            padding=[
                35,
                35
            ]
        )


    elif len(
        markers_to_plot
    ) > 1:

        marker_bounds = [

            [
                float(
                    marker[
                        "lat"
                    ]
                ),

                float(
                    marker[
                        "lon"
                    ]
                )
            ]

            for marker
            in markers_to_plot

        ]


        m.fit_bounds(
            marker_bounds,
            padding=[
                30,
                30
            ]
        )


    elif len(
        markers_to_plot
    ) == 1:

        m.location = [

            markers_to_plot[
                0
            ][
                "lat"
            ],

            markers_to_plot[
                0
            ][
                "lon"
            ]
        ]

        m.zoom_start = 14


    # ========================================================
    # MAP LEGEND
    # ========================================================

    if matched_barangay_codes:

        legend_html = f"""
        <div
            style="
                position: fixed;
                bottom: 35px;
                left: 35px;
                z-index: 9999;

                background-color: white;

                border:
                    1px solid
                    #BDBDBD;

                border-radius:
                    7px;

                padding:
                    12px 14px;

                font-size:
                    13px;

                color:
                    #212121;

                box-shadow:
                    0px 2px 7px
                    rgba(
                        0,
                        0,
                        0,
                        0.20
                    );
            "
        >

            <div
                style="
                    font-weight:700;
                    font-size:14px;
                    margin-bottom:9px;
                "
            >
                Map Legend
            </div>


            <!-- MATCHED BARANGAY -->

            <div
                style="
                    display:flex;
                    align-items:center;
                    margin-bottom:7px;
                "
            >

                <span
                    style="
                        width:20px;
                        height:14px;
                        background:
                            {MATCHED_FILL};
                        border:
                            2px solid
                            {MATCHED_BORDER};
                        margin-right:8px;
                    "
                >
                </span>

                Matched barangay

            </div>


            <!-- SELECTED BARANGAY -->

            <div
                style="
                    display:flex;
                    align-items:center;
                    margin-bottom:7px;
                "
            >

                <span
                    style="
                        width:20px;
                        height:14px;
                        background:
                            {SELECTED_FILL};
                        border:
                            3px solid
                            {SELECTED_BORDER};
                        margin-right:8px;
                    "
                >
                </span>

                Selected barangay

            </div>


            <!-- NORMAL PIN -->

            <div
                style="
                    display:flex;
                    align-items:center;
                    margin-bottom:7px;
                "
            >

                <span
                    style="
                        font-size:19px;
                        margin-right:7px;
                    "
                >
                    📍
                </span>

                Result location

            </div>


            <!-- SELECTED PIN -->

            <div
                style="
                    display:flex;
                    align-items:center;
                "
            >

                <span
                    style="
                        width:15px;
                        height:15px;
                        border-radius:50%;
                        display:inline-block;
                        background:#1976D2;
                        margin-left:2px;
                        margin-right:10px;
                        border:2px solid white;
                        box-shadow:
                            0 0 0 1px
                            #1976D2;
                    "
                >
                </span>

                Selected location

            </div>

        </div>
        """


        m.get_root().html.add_child(
            folium.Element(
                legend_html
            )
        )


    # ========================================================
    # RENDER MAP
    # ========================================================

    map_state_key = (
        "barangay_map_"
        f"{basemap_name}_"
        f"{selected_barangay_code}_"
        f"{len(matched_barangay_codes)}"
    )


    st_folium(
        m,
        height=850,
        use_container_width=True,
        key=map_state_key,
        returned_objects=[]
    )

# # ==================================================
# # PHILIPPINE BARANGAY SPATIAL LOCATOR
# # ==================================================

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
#     page_icon="🇵🇭",
#     layout="wide"
# )

# st.title("🇵🇭 Philippine Barangay Spatial Locator")

# st.markdown(
#     """
#     Enter a single coordinate or upload a CSV/XLSX file containing multiple
#     coordinates to identify the corresponding **Barangay, City, Province,
#     Region, and ADM4_PCODE**.
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

# if "uploaded_file_id" not in st.session_state:
#     st.session_state.uploaded_file_id = None


# # ==================================================
# # LOAD BARANGAY DATA
# # ==================================================

# @st.cache_resource
# def load_barangay_data():
#     """
#     Load Philippine barangay boundary data and ensure
#     the coordinate reference system is EPSG:4326.
#     """

#     gdf = gpd.read_parquet("barangays.parquet")

#     if gdf.crs is None:
#         raise ValueError(
#             "The barangays.parquet file does not have a defined CRS."
#         )

#     if gdf.crs.to_string() != "EPSG:4326":
#         gdf = gdf.to_crs("EPSG:4326")

#     return gdf


# try:
#     with st.spinner("Loading Philippine boundary data... Please wait."):
#         brgy_gdf = load_barangay_data()

# except Exception as error:
#     st.error(
#         f"Unable to load barangay boundary data: {error}"
#     )
#     st.stop()


# # ==================================================
# # SIDEBAR: INPUT OPTIONS
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
# # SIDEBAR: BASEMAP SELECTION
# # ==================================================

# st.sidebar.divider()
# st.sidebar.subheader("Map Settings")

# basemap_name = st.sidebar.selectbox(
#     "Select Basemap",
#     [
#         "OpenStreetMap",
#         "OpenStreetMap HOT",
#         "OpenTopoMap"
#     ],
#     index=0,
#     help="Available basemaps you can choose."
# )


# # ==================================================
# # BASEMAP CONFIGURATION
# # ==================================================

# BASEMAPS = {
#     "OpenStreetMap": {
#         "tiles": (
#             "https://{s}.tile.openstreetmap.org/"
#             "{z}/{x}/{y}.png"
#         ),
#         "attr": (
#             '&copy; '
#             '<a href="https://www.openstreetmap.org/copyright">'
#             "OpenStreetMap contributors"
#             "</a>"
#         ),
#         "max_zoom": 19
#     },

#     "OpenStreetMap HOT": {
#         "tiles": (
#             "https://{s}.tile.openstreetmap.fr/hot/"
#             "{z}/{x}/{y}.png"
#         ),
#         "attr": (
#             '&copy; '
#             '<a href="https://www.openstreetmap.org/copyright">'
#             "OpenStreetMap contributors"
#             "</a>, "
#             "Tiles style by Humanitarian OpenStreetMap Team"
#         ),
#         "max_zoom": 19
#     },

#     "OpenTopoMap": {
#         "tiles": (
#             "https://{s}.tile.opentopomap.org/"
#             "{z}/{x}/{y}.png"
#         ),
#         "attr": (
#             "Map data: "
#             '&copy; '
#             '<a href="https://www.openstreetmap.org/copyright">'
#             "OpenStreetMap contributors"
#             "</a>, "
#             "SRTM | "
#             "Map style: "
#             '&copy; '
#             '<a href="https://opentopomap.org">'
#             "OpenTopoMap"
#             "</a>"
#         ),
#         "max_zoom": 17
#     }
# }

# selected_basemap = BASEMAPS[basemap_name]


# # ==================================================
# # SINGLE COORDINATE INPUT
# # ==================================================

# if input_mode == "Single Coordinate":

#     st.sidebar.subheader("Enter Latitude and Longitude")

#     lat = st.sidebar.number_input(
#         "Latitude",
#         min_value=-90.0,
#         max_value=90.0,
#         value=14.599500,
#         step=0.000001,
#         format="%.6f"
#     )

#     lon = st.sidebar.number_input(
#         "Longitude",
#         min_value=-180.0,
#         max_value=180.0,
#         value=120.984200,
#         step=0.000001,
#         format="%.6f"
#     )

#     if st.sidebar.button(
#         "Locate Barangay",
#         type="primary",
#         use_container_width=True
#     ):

#         point = Point(lon, lat)

#         # Intersects is used here so that points on a polygon
#         # boundary can still return a match.
#         match = brgy_gdf[
#             brgy_gdf.geometry.intersects(point)
#         ]

#         if not match.empty:

#             match_row = match.iloc[0]

#             barangay = match_row.get("ADM4_EN", "N/A")
#             city = match_row.get("ADM3_EN", "N/A")
#             province = match_row.get("ADM2_EN", "N/A")
#             region = match_row.get("ADM1_EN", "N/A")
#             pcode = match_row.get("ADM4_PCODE", "N/A")

#             st.session_state.results_df = pd.DataFrame(
#                 [
#                     {
#                         "Latitude": lat,
#                         "Longitude": lon,
#                         "ADM4_PCODE": pcode,
#                         "Barangay": barangay,
#                         "City/Municipality": city,
#                         "Province": province,
#                         "Region": region
#                     }
#                 ]
#             )

#             popup_text = (
#                 f"<b>{barangay}</b><br>"
#                 f"{city}<br>"
#                 f"{province}<br>"
#                 f"{region}<br>"
#                 f"<b>ADM4_PCODE:</b> {pcode}"
#             )

#             st.session_state.markers_to_plot = [
#                 (
#                     float(lat),
#                     float(lon),
#                     popup_text
#                 )
#             ]

#             st.session_state.selected_point = {
#                 "lat": float(lat),
#                 "lon": float(lon),
#                 "label": barangay
#             }

#         else:

#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []
#             st.session_state.selected_point = None

#             st.warning(
#                 "The coordinates fall outside the boundaries "
#                 "of the loaded barangay dataset."
#             )


# # ==================================================
# # BATCH FILE UPLOAD
# # ==================================================

# else:

#     st.sidebar.subheader("Upload Coordinate File")

#     uploaded_file = st.sidebar.file_uploader(
#         "Upload CSV or XLSX file",
#         type=["csv", "xlsx"]
#     )

#     if uploaded_file is None:

#         st.session_state.batch_processed = False
#         st.session_state.selected_point = None
#         st.session_state.uploaded_file_id = None

#     if uploaded_file is not None:

#         current_file_id = (
#             uploaded_file.name,
#             uploaded_file.size
#         )

#         # Reset processing status when a different file is uploaded.
#         if st.session_state.uploaded_file_id != current_file_id:

#             st.session_state.uploaded_file_id = current_file_id
#             st.session_state.batch_processed = False
#             st.session_state.results_df = pd.DataFrame()
#             st.session_state.markers_to_plot = []
#             st.session_state.selected_point = None

#         try:

#             if uploaded_file.name.lower().endswith(".csv"):

#                 input_df = pd.read_csv(uploaded_file)

#             else:

#                 input_df = pd.read_excel(uploaded_file)

#         except Exception as error:

#             st.error(
#                 f"Unable to read the uploaded file: {error}"
#             )
#             st.stop()

#         if input_df.empty:

#             st.warning(
#                 "The uploaded file does not contain any records."
#             )
#             st.stop()

#         if not st.session_state.batch_processed:

#             st.write("### Preview of Uploaded Data")

#             st.dataframe(
#                 input_df.head(),
#                 use_container_width=True,
#                 hide_index=True
#             )

#         available_columns = input_df.columns.tolist()

#         # Attempt to identify likely latitude and longitude columns.
#         latitude_candidates = [
#             col
#             for col in available_columns
#             if str(col).lower() in [
#                 "latitude",
#                 "lat",
#                 "y"
#             ]
#         ]

#         longitude_candidates = [
#             col
#             for col in available_columns
#             if str(col).lower() in [
#                 "longitude",
#                 "long",
#                 "lon",
#                 "lng",
#                 "x"
#             ]
#         ]

#         default_lat_index = 0

#         if latitude_candidates:
#             default_lat_index = available_columns.index(
#                 latitude_candidates[0]
#             )

#         default_lon_index = 0

#         if longitude_candidates:
#             default_lon_index = available_columns.index(
#                 longitude_candidates[0]
#             )
#         elif len(available_columns) > 1:
#             default_lon_index = 1

#         lat_col = st.sidebar.selectbox(
#             "Select Latitude Column",
#             available_columns,
#             index=default_lat_index
#         )

#         lon_col = st.sidebar.selectbox(
#             "Select Longitude Column",
#             available_columns,
#             index=default_lon_index
#         )

#         if st.sidebar.button(
#             "Process Batch",
#             type="primary",
#             use_container_width=True
#         ):

#             if lat_col == lon_col:

#                 st.error(
#                     "Latitude and longitude must use different columns."
#                 )

#             else:

#                 working_df = input_df.copy()

#                 working_df[lat_col] = pd.to_numeric(
#                     working_df[lat_col],
#                     errors="coerce"
#                 )

#                 working_df[lon_col] = pd.to_numeric(
#                     working_df[lon_col],
#                     errors="coerce"
#                 )

#                 valid_coordinate_mask = (
#                     working_df[lat_col].between(-90, 90)
#                     & working_df[lon_col].between(-180, 180)
#                 )

#                 invalid_count = int(
#                     (~valid_coordinate_mask).sum()
#                 )

#                 valid_df = working_df[
#                     valid_coordinate_mask
#                 ].copy()

#                 if valid_df.empty:

#                     st.error(
#                         "No valid coordinate records were found. "
#                         "Latitude must be between -90 and 90, and "
#                         "longitude must be between -180 and 180."
#                     )

#                 else:

#                     st.session_state.batch_processed = True
#                     st.session_state.selected_point = None

#                     with st.spinner(
#                         "Performing spatial lookup..."
#                     ):

#                         geometry = gpd.points_from_xy(
#                             valid_df[lon_col],
#                             valid_df[lat_col]
#                         )

#                         input_gdf = gpd.GeoDataFrame(
#                             valid_df.copy(),
#                             geometry=geometry,
#                             crs="EPSG:4326"
#                         )

#                         joined = gpd.sjoin(
#                             input_gdf,
#                             brgy_gdf,
#                             how="left",
#                             predicate="within"
#                         )

#                         # A point can occasionally match more than one
#                         # polygon if the source polygons overlap.
#                         # Keep the first matched polygon per input record.
#                         joined = joined[
#                             ~joined.index.duplicated(keep="first")
#                         ].copy()

#                         output_list = []
#                         markers = []

#                         for _, row in joined.iterrows():

#                             lat_val = row.get(lat_col)
#                             lon_val = row.get(lon_col)

#                             result_row = {
#                                 column: row.get(column)
#                                 for column in input_df.columns
#                             }

#                             barangay = row.get(
#                                 "ADM4_EN",
#                                 "N/A"
#                             )

#                             city = row.get(
#                                 "ADM3_EN",
#                                 "N/A"
#                             )

#                             province = row.get(
#                                 "ADM2_EN",
#                                 "N/A"
#                             )

#                             region = row.get(
#                                 "ADM1_EN",
#                                 "N/A"
#                             )

#                             pcode = row.get(
#                                 "ADM4_PCODE",
#                                 "N/A"
#                             )

#                             # Replace missing spatial results with N/A.
#                             barangay = (
#                                 barangay
#                                 if pd.notna(barangay)
#                                 else "N/A"
#                             )

#                             city = (
#                                 city
#                                 if pd.notna(city)
#                                 else "N/A"
#                             )

#                             province = (
#                                 province
#                                 if pd.notna(province)
#                                 else "N/A"
#                             )

#                             region = (
#                                 region
#                                 if pd.notna(region)
#                                 else "N/A"
#                             )

#                             pcode = (
#                                 pcode
#                                 if pd.notna(pcode)
#                                 else "N/A"
#                             )

#                             result_row.update(
#                                 {
#                                     "Latitude": float(lat_val),
#                                     "Longitude": float(lon_val),
#                                     "ADM4_PCODE": pcode,
#                                     "Barangay": barangay,
#                                     "City/Municipality": city,
#                                     "Province": province,
#                                     "Region": region
#                                 }
#                             )

#                             output_list.append(result_row)

#                             if barangay != "N/A":

#                                 popup_text = (
#                                     f"<b>{barangay}</b><br>"
#                                     f"{city}<br>"
#                                     f"{province}<br>"
#                                     f"{region}<br>"
#                                     f"<b>ADM4_PCODE:</b> {pcode}"
#                                 )

#                                 markers.append(
#                                     (
#                                         float(lat_val),
#                                         float(lon_val),
#                                         popup_text
#                                     )
#                                 )

#                         st.session_state.results_df = pd.DataFrame(
#                             output_list
#                         )

#                         st.session_state.markers_to_plot = markers

#                     if invalid_count > 0:

#                         st.warning(
#                             f"{invalid_count:,} record(s) were excluded "
#                             "because of missing or invalid coordinates."
#                         )


# # ==================================================
# # RETRIEVE SAVED RESULTS
# # ==================================================

# results_df = st.session_state.results_df
# markers_to_plot = st.session_state.markers_to_plot


# # ==================================================
# # MAP AND TABLE LAYOUT
# # ==================================================

# map_col, table_col = st.columns(
#     [2, 2],
#     gap="large"
# )


# # ==================================================
# # TABLE
# # Render table first so selected row controls the map.
# # ==================================================

# with table_col:

#     st.subheader("📋 Tabular Results")

#     if not results_df.empty:

#         row_count = len(results_df)

#         table_height = min(
#             max(
#                 90 + (row_count * 35),
#                 130
#             ),
#             750
#         )

#         table_event = st.dataframe(
#             results_df,
#             use_container_width=True,
#             height=table_height,
#             hide_index=True,
#             on_select="rerun",
#             selection_mode="single-row",
#             key="results_table"
#         )

#         selected_rows = table_event.selection.rows

#         if selected_rows:

#             selected_row_index = selected_rows[0]

#             selected_row = results_df.iloc[
#                 selected_row_index
#             ]

#             selected_lat = selected_row.get(
#                 "Latitude"
#             )

#             selected_lon = selected_row.get(
#                 "Longitude"
#             )

#             if (
#                 pd.notna(selected_lat)
#                 and pd.notna(selected_lon)
#             ):

#                 st.session_state.selected_point = {
#                     "lat": float(selected_lat),
#                     "lon": float(selected_lon),
#                     "label": selected_row.get(
#                         "Barangay",
#                         ""
#                     )
#                 }

#         csv_data = results_df.to_csv(
#             index=False
#         ).encode("utf-8-sig")

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
#             "Input a coordinate or upload a file "
#             "to view tabular results."
#         )


# # ==================================================
# # MAP
# # ==================================================

# with map_col:

#     st.subheader("🗺️ Interactive Map")

#     selected_point = st.session_state.selected_point

#     # Default center of the Philippines.
#     map_center = [
#         12.8797,
#         121.7740
#     ]

#     zoom_start = 6

#     if selected_point is not None:

#         map_center = [
#             selected_point["lat"],
#             selected_point["lon"]
#         ]

#         zoom_start = 15

#     # Create the map without a default tile layer.
#     m = folium.Map(
#         location=map_center,
#         zoom_start=zoom_start,
#         tiles=None,
#         control_scale=True,
#         prefer_canvas=True
#     )

#     # Add the user-selected free basemap.
#     folium.TileLayer(
#         tiles=selected_basemap["tiles"],
#         attr=selected_basemap["attr"],
#         name=basemap_name,
#         max_zoom=selected_basemap["max_zoom"],
#         overlay=False,
#         control=False
#     ).add_to(m)

#     # Add all result markers.
#     for lat, lon, popup_text in markers_to_plot:

#         marker_color = "red"
#         marker_icon = "map-marker"

#         if selected_point is not None:

#             latitude_difference = abs(
#                 float(lat)
#                 - float(selected_point["lat"])
#             )

#             longitude_difference = abs(
#                 float(lon)
#                 - float(selected_point["lon"])
#             )

#             if (
#                 latitude_difference < 0.000001
#                 and longitude_difference < 0.000001
#             ):

#                 marker_color = "blue"
#                 marker_icon = "info-sign"

#         folium.Marker(
#             location=[
#                 float(lat),
#                 float(lon)
#             ],
#             tooltip="Click to view location details",
#             popup=folium.Popup(
#                 popup_text,
#                 max_width=300
#             ),
#             icon=folium.Icon(
#                 color=marker_color,
#                 icon=marker_icon,
#                 prefix="fa"
#             )
#         ).add_to(m)

#     # Automatically fit the map to all markers if no
#     # specific table row is selected.
#     if selected_point is None:

#         if len(markers_to_plot) > 1:

#             bounds = [
#                 [
#                     float(lat),
#                     float(lon)
#                 ]
#                 for lat, lon, _ in markers_to_plot
#             ]

#             m.fit_bounds(
#                 bounds,
#                 padding=[
#                     30,
#                     30
#                 ]
#             )

#         elif len(markers_to_plot) == 1:

#             single_lat = float(
#                 markers_to_plot[0][0]
#             )

#             single_lon = float(
#                 markers_to_plot[0][1]
#             )

#             m.location = [
#                 single_lat,
#                 single_lon
#             ]

#             m.zoom_start = 14

#     st_folium(
#         m,
#         height=850,
#         use_container_width=True,
#         key=f"barangay_map_{basemap_name}"
#     )


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
