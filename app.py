import streamlit as st
import requests
import pandas as pd

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Bulk PageSpeed Checker",
    page_icon="⚡",
    layout="wide"
)

st.title("Bulk PageSpeed Checker")

st.write(
    "Bulk PageSpeed and mobile Core Web Vitals analysis."
)


# =========================================================
# SETTINGS
# =========================================================

PAGESPEED_API_URL = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
)

REQUEST_TIMEOUT = 120


# =========================================================
# API KEY
# =========================================================

try:
    API_KEY = st.secrets["PAGESPEED_API_KEY"]

except Exception:
    st.error(
        "PAGESPEED_API_KEY is missing from Streamlit Secrets."
    )
    st.stop()


# =========================================================
# PSI REQUEST
# =========================================================

def get_pagespeed_data(url, strategy):

    params = {
        "url": url,
        "strategy": strategy,
        "key": API_KEY,
        "category": "performance"
    }

    response = requests.get(
        PAGESPEED_API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        raise Exception(
            f"API error {response.status_code}: {response.text}"
        )

    return response.json()


# =========================================================
# PERFORMANCE SCORE
# =========================================================

def extract_performance_score(data):

    try:

        score = (
            data["lighthouseResult"]
            ["categories"]
            ["performance"]
            ["score"]
        )

        if score is None:
            return None

        return round(score * 100)

    except Exception:
        return None


# =========================================================
# MOBILE CORE WEB VITALS
# =========================================================

def extract_mobile_cwv(data):

    loading_experience = data.get(
        "loadingExperience",
        {}
    )

    # Do not use origin fallback as page-level data
    if loading_experience.get(
        "origin_fallback",
        False
    ):

        return {
            "LCP": None,
            "INP": None,
            "CLS": None,
            "CWV Data": "N/A"
        }

    metrics = loading_experience.get(
        "metrics",
        {}
    )

    # -----------------------------------------------------
    # LCP
    # -----------------------------------------------------

    lcp_metric = metrics.get(
        "LARGEST_CONTENTFUL_PAINT_MS"
    )

    if lcp_metric:

        lcp_ms = lcp_metric.get(
            "percentile"
        )

        if lcp_ms is not None:
            lcp = round(
                lcp_ms / 1000,
                2
            )
        else:
            lcp = None

    else:
        lcp = None

    # -----------------------------------------------------
    # INP
    # -----------------------------------------------------

    inp_metric = metrics.get(
        "INTERACTION_TO_NEXT_PAINT"
    )

    if inp_metric:
        inp = inp_metric.get(
            "percentile"
        )
    else:
        inp = None

    # -----------------------------------------------------
    # CLS
    # -----------------------------------------------------

    cls_metric = metrics.get(
        "CUMULATIVE_LAYOUT_SHIFT_SCORE"
    )

    if cls_metric:

        cls_raw = cls_metric.get(
            "percentile"
        )

        if cls_raw is not None:
            cls = round(
                cls_raw / 100,
                3
            )
        else:
            cls = None

    else:
        cls = None

    if (
        lcp is None
        and inp is None
        and cls is None
    ):
        cwv_data = "N/A"
    else:
        cwv_data = "URL"

    return {
        "LCP": lcp,
        "INP": inp,
        "CLS": cls,
        "CWV Data": cwv_data
    }


# =========================================================
# FORMAT VALUES
# =========================================================

def format_value(value, suffix=""):

    if value is None:
        return "N/A"

    return f"{value}{suffix}"


# =========================================================
# ANALYZE ONE URL
# =========================================================

def analyze_single_url(url):

    result = {
        "URL": url,
        "PageSpeed Mobile": "Error",
        "PageSpeed Desktop": "Error",
        "LCP Mobile": "N/A",
        "INP Mobile": "N/A",
        "CLS Mobile": "N/A",
        "CWV Data": "N/A",
        "Tested At": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "Error": ""
    }

    try:

        # Mobile + desktop are run simultaneously
        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            mobile_future = executor.submit(
                get_pagespeed_data,
                url,
                "mobile"
            )

            desktop_future = executor.submit(
                get_pagespeed_data,
                url,
                "desktop"
            )

            mobile_data = mobile_future.result()
            desktop_data = desktop_future.result()

        # Mobile Lighthouse
        mobile_score = extract_performance_score(
            mobile_data
        )

        if mobile_score is not None:
            result[
                "PageSpeed Mobile"
            ] = mobile_score

        # Desktop Lighthouse
        desktop_score = extract_performance_score(
            desktop_data
        )

        if desktop_score is not None:
            result[
                "PageSpeed Desktop"
            ] = desktop_score

        # Mobile CWV
        cwv = extract_mobile_cwv(
            mobile_data
        )

        result["LCP Mobile"] = format_value(
            cwv["LCP"],
            " s"
        )

        result["INP Mobile"] = format_value(
            cwv["INP"],
            " ms"
        )

        result["CLS Mobile"] = format_value(
            cwv["CLS"]
        )

        result["CWV Data"] = cwv[
            "CWV Data"
        ]

    except Exception as e:

        result["Error"] = str(e)

    return result


# =========================================================
# STREAMLIT CELL COLORS
# =========================================================

GREEN_BG = "#d9ead3"
GREEN_TEXT = "#274e13"

ORANGE_BG = "#fce5cd"
ORANGE_TEXT = "#783f04"

RED_BG = "#f4cccc"
RED_TEXT = "#990000"

GRAY_BG = "#eeeeee"
GRAY_TEXT = "#666666"


def green_style():

    return (
        f"background-color: {GREEN_BG}; "
        f"color: {GREEN_TEXT}; "
        "font-weight: 600;"
    )


def orange_style():

    return (
        f"background-color: {ORANGE_BG}; "
        f"color: {ORANGE_TEXT}; "
        "font-weight: 600;"
    )


def red_style():

    return (
        f"background-color: {RED_BG}; "
        f"color: {RED_TEXT}; "
        "font-weight: 600;"
    )


def gray_style():

    return (
        f"background-color: {GRAY_BG}; "
        f"color: {GRAY_TEXT};"
    )


# =========================================================
# PAGESPEED COLOR
# =========================================================

def color_pagespeed(value):

    if value in [
        "Error",
        "N/A",
        None,
        ""
    ]:
        return gray_style()

    try:
        value = float(value)

    except Exception:
        return gray_style()

    # Google Lighthouse:
    # 90–100 = Good
    # 50–89 = Needs Improvement
    # 0–49 = Poor

    if value >= 90:
        return green_style()

    elif value >= 50:
        return orange_style()

    else:
        return red_style()


# =========================================================
# LCP COLOR
# =========================================================

def color_lcp(value):

    if value in [
        "N/A",
        None,
        ""
    ]:
        return gray_style()

    try:

        value = float(
            str(value)
            .replace(" s", "")
            .strip()
        )

    except Exception:
        return gray_style()

    if value <= 2.5:
        return green_style()

    elif value <= 4.0:
        return orange_style()

    else:
        return red_style()


# =========================================================
# INP COLOR
# =========================================================

def color_inp(value):

    if value in [
        "N/A",
        None,
        ""
    ]:
        return gray_style()

    try:

        value = float(
            str(value)
            .replace(" ms", "")
            .strip()
        )

    except Exception:
        return gray_style()

    if value <= 200:
        return green_style()

    elif value <= 500:
        return orange_style()

    else:
        return red_style()


# =========================================================
# CLS COLOR
# =========================================================

def color_cls(value):

    if value in [
        "N/A",
        None,
        ""
    ]:
        return gray_style()

    try:
        value = float(value)

    except Exception:
        return gray_style()

    if value <= 0.1:
        return green_style()

    elif value <= 0.25:
        return orange_style()

    else:
        return red_style()


# =========================================================
# EXCEL EXPORT WITH COLORS
# =========================================================

def create_excel_file(df):

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="PageSpeed Results",
            index=False
        )

        workbook = writer.book

        worksheet = writer.sheets[
            "PageSpeed Results"
        ]

        # -------------------------------------------------
        # FORMATS
        # -------------------------------------------------

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        green_format = workbook.add_format({
            "bg_color": GREEN_BG,
            "font_color": GREEN_TEXT,
            "bold": True,
            "border": 1
        })

        orange_format = workbook.add_format({
            "bg_color": ORANGE_BG,
            "font_color": ORANGE_TEXT,
            "bold": True,
            "border": 1
        })

        red_format = workbook.add_format({
            "bg_color": RED_BG,
            "font_color": RED_TEXT,
            "bold": True,
            "border": 1
        })

        gray_format = workbook.add_format({
            "bg_color": GRAY_BG,
            "font_color": GRAY_TEXT,
            "border": 1
        })

        normal_format = workbook.add_format({
            "border": 1
        })

        url_format = workbook.add_format({
            "border": 1,
            "text_wrap": True
        })

        # -------------------------------------------------
        # HEADERS
        # -------------------------------------------------

        for col_num, column in enumerate(
            df.columns
        ):

            worksheet.write(
                0,
                col_num,
                column,
                header_format
            )

        # -------------------------------------------------
        # COLUMN WIDTHS
        # -------------------------------------------------

        worksheet.set_column(
            "A:A",
            60
        )

        worksheet.set_column(
            "B:C",
            20
        )

        worksheet.set_column(
            "D:F",
            16
        )

        worksheet.set_column(
            "G:G",
            12
        )

        worksheet.set_column(
            "H:H",
            22
        )

        worksheet.set_column(
            "I:I",
            50
        )

        worksheet.freeze_panes(
            1,
            1
        )

        # -------------------------------------------------
        # DATA CELLS
        # -------------------------------------------------

        for row_index, row in df.iterrows():

            excel_row = row_index + 1

            for col_index, column in enumerate(
                df.columns
            ):

                value = row[column]

                cell_format = normal_format

                # -----------------------------------------
                # URL
                # -----------------------------------------

                if column == "URL":

                    cell_format = url_format

                # -----------------------------------------
                # PAGESPEED
                # -----------------------------------------

                elif column in [
                    "PageSpeed Mobile",
                    "PageSpeed Desktop"
                ]:

                    try:

                        numeric = float(value)

                        if numeric >= 90:
                            cell_format = green_format

                        elif numeric >= 50:
                            cell_format = orange_format

                        else:
                            cell_format = red_format

                    except Exception:
                        cell_format = gray_format

                # -----------------------------------------
                # LCP
                # -----------------------------------------

                elif column == "LCP Mobile":

                    try:

                        numeric = float(
                            str(value)
                            .replace(
                                " s",
                                ""
                            )
                        )

                        if numeric <= 2.5:
                            cell_format = green_format

                        elif numeric <= 4.0:
                            cell_format = orange_format

                        else:
                            cell_format = red_format

                    except Exception:
                        cell_format = gray_format

                # -----------------------------------------
                # INP
                # -----------------------------------------

                elif column == "INP Mobile":

                    try:

                        numeric = float(
                            str(value)
                            .replace(
                                " ms",
                                ""
                            )
                        )

                        if numeric <= 200:
                            cell_format = green_format

                        elif numeric <= 500:
                            cell_format = orange_format

                        else:
                            cell_format = red_format

                    except Exception:
                        cell_format = gray_format

                # -----------------------------------------
                # CLS
                # -----------------------------------------

                elif column == "CLS Mobile":

                    try:

                        numeric = float(
                            value
                        )

                        if numeric <= 0.1:
                            cell_format = green_format

                        elif numeric <= 0.25:
                            cell_format = orange_format

                        else:
                            cell_format = red_format

                    except Exception:
                        cell_format = gray_format

                worksheet.write(
                    excel_row,
                    col_index,
                    value,
                    cell_format
                )

    output.seek(0)

    return output.getvalue()


# =========================================================
# INPUT
# =========================================================

urls_input = st.text_area(
    "URLs — one URL per line",
    placeholder=(
        "https://ananas.rs/\n"
        "https://ananas.rs/kategorije/bela-tehnika\n"
        "https://ananas.rs/kategorije/bela-tehnika/klima-uredjaji"
    ),
    height=260
)


# =========================================================
# ANALYZE
# =========================================================

if st.button(
    "Analyze URLs",
    type="primary"
):

    urls = [
        url.strip()
        for url in urls_input.splitlines()
        if url.strip()
    ]

    # Remove exact duplicates
    # but keep original order
    urls = list(
        dict.fromkeys(urls)
    )

    if not urls:

        st.warning(
            "Please enter at least one URL."
        )

        st.stop()

    results = []

    progress = st.progress(0)

    status_text = st.empty()

    total_urls = len(urls)

    completed = 0

    # =====================================================
    # PARALLEL URL ANALYSIS
    # =====================================================

    with ThreadPoolExecutor(
        max_workers=3
    ) as executor:

        futures = {
            executor.submit(
                analyze_single_url,
                url
            ): url

            for url in urls
        }

        for future in as_completed(
            futures
        ):

            url = futures[
                future
            ]

            try:

                result = future.result()

            except Exception as e:

                result = {
                    "URL": url,
                    "PageSpeed Mobile": "Error",
                    "PageSpeed Desktop": "Error",
                    "LCP Mobile": "N/A",
                    "INP Mobile": "N/A",
                    "CLS Mobile": "N/A",
                    "CWV Data": "N/A",
                    "Tested At": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "Error": str(e)
                }

            results.append(
                result
            )

            completed += 1

            progress.progress(
                completed
                / total_urls
            )

            status_text.write(
                f"Completed "
                f"{completed} / "
                f"{total_urls} URLs"
            )

    status_text.empty()

    # =====================================================
    # RESTORE ORIGINAL ORDER
    # =====================================================

    order_map = {
        url: index
        for index, url
        in enumerate(urls)
    }

    results.sort(
        key=lambda item:
        order_map[
            item["URL"]
        ]
    )

    # =====================================================
    # DATAFRAME
    # =====================================================

    df = pd.DataFrame(
        results
    )

    # =====================================================
    # COLORED TABLE
    # =====================================================

    styled_df = (
        df.style
        .map(
            color_pagespeed,
            subset=[
                "PageSpeed Mobile",
                "PageSpeed Desktop"
            ]
        )
        .map(
            color_lcp,
            subset=[
                "LCP Mobile"
            ]
        )
        .map(
            color_inp,
            subset=[
                "INP Mobile"
            ]
        )
        .map(
            color_cls,
            subset=[
                "CLS Mobile"
            ]
        )
    )

    st.subheader(
        "Results"
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=650
    )

    # =====================================================
    # LEGEND
    # =====================================================

    st.caption(
        "PageSpeed: Green 90–100 · Orange 50–89 · Red 0–49 | "
        "LCP: Green ≤2.5s · Orange ≤4s · Red >4s | "
        "INP: Green ≤200ms · Orange ≤500ms · Red >500ms | "
        "CLS: Green ≤0.1 · Orange ≤0.25 · Red >0.25"
    )

    # =====================================================
    # EXCEL DOWNLOAD WITH COLORS
    # =====================================================

    excel_file = create_excel_file(
        df
    )

    st.download_button(
        label="Download Excel with Colors",
        data=excel_file,
        file_name="pagespeed_results.xlsx",
        mime=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    # =====================================================
    # CSV DOWNLOAD
    # =====================================================

    csv = (
        df.to_csv(
            index=False
        )
        .encode(
            "utf-8-sig"
        )
    )

    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="pagespeed_results.csv",
        mime="text/csv"
    )
