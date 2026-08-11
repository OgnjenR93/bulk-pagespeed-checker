import streamlit as st
import requests
import pandas as pd
import time

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

MAX_ATTEMPTS = 3

URL_WORKERS = 2


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
# PSI REQUEST WITH RETRY
# =========================================================

def get_pagespeed_data(url, strategy):
    """
    Runs PageSpeed Insights API.

    Automatically retries:
    - timeouts
    - 429
    - 500
    - 502
    - 503
    - 504
    """

    params = {
        "url": url,
        "strategy": strategy,
        "key": API_KEY,
        "category": "performance"
    }

    retry_status_codes = {
        429,
        500,
        502,
        503,
        504
    }

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        try:

            response = requests.get(
                PAGESPEED_API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            # SUCCESS
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "attempts": attempt,
                    "error": ""
                }

            # RETRYABLE API ERROR
            if (
                response.status_code
                in retry_status_codes
            ):

                last_error = (
                    f"API error "
                    f"{response.status_code}"
                )

                if attempt < MAX_ATTEMPTS:

                    wait_seconds = (
                        2 ** attempt
                    )

                    time.sleep(
                        wait_seconds
                    )

                    continue

            # NON-RETRYABLE API ERROR
            return {
                "success": False,
                "data": None,
                "attempts": attempt,
                "error": (
                    f"API error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )
            }

        except requests.exceptions.Timeout:

            last_error = (
                f"Timeout after "
                f"{REQUEST_TIMEOUT}s"
            )

            if attempt < MAX_ATTEMPTS:

                wait_seconds = (
                    2 ** attempt
                )

                time.sleep(
                    wait_seconds
                )

                continue

        except requests.exceptions.RequestException as e:

            last_error = str(e)

            if attempt < MAX_ATTEMPTS:

                wait_seconds = (
                    2 ** attempt
                )

                time.sleep(
                    wait_seconds
                )

                continue

    return {
        "success": False,
        "data": None,
        "attempts": MAX_ATTEMPTS,
        "error": last_error or "Unknown error"
    }


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

        return round(
            score * 100
        )

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

    # Do not use origin fallback
    # as page-level CWV data
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

def format_value(
    value,
    suffix=""
):

    if value is None:
        return "N/A"

    return f"{value}{suffix}"


# =========================================================
# ANALYZE MOBILE
# =========================================================

def analyze_mobile(url):

    response = get_pagespeed_data(
        url,
        "mobile"
    )

    result = {
        "score": "Error",
        "lcp": "N/A",
        "inp": "N/A",
        "cls": "N/A",
        "cwv_data": "N/A",
        "status": "ERROR",
        "attempts": response[
            "attempts"
        ],
        "error": response[
            "error"
        ]
    }

    if not response[
        "success"
    ]:
        return result

    data = response[
        "data"
    ]

    score = (
        extract_performance_score(
            data
        )
    )

    if score is not None:

        result[
            "score"
        ] = score

    cwv = extract_mobile_cwv(
        data
    )

    result[
        "lcp"
    ] = format_value(
        cwv["LCP"],
        " s"
    )

    result[
        "inp"
    ] = format_value(
        cwv["INP"],
        " ms"
    )

    result[
        "cls"
    ] = format_value(
        cwv["CLS"]
    )

    result[
        "cwv_data"
    ] = cwv[
        "CWV Data"
    ]

    result[
        "status"
    ] = (
        "OK"
        if response["attempts"] == 1
        else "RETRIED"
    )

    result[
        "error"
    ] = ""

    return result


# =========================================================
# ANALYZE DESKTOP
# =========================================================

def analyze_desktop(url):

    response = get_pagespeed_data(
        url,
        "desktop"
    )

    result = {
        "score": "Error",
        "status": "ERROR",
        "attempts": response[
            "attempts"
        ],
        "error": response[
            "error"
        ]
    }

    if not response[
        "success"
    ]:
        return result

    score = (
        extract_performance_score(
            response["data"]
        )
    )

    if score is not None:

        result[
            "score"
        ] = score

    result[
        "status"
    ] = (
        "OK"
        if response["attempts"] == 1
        else "RETRIED"
    )

    result[
        "error"
    ] = ""

    return result


# =========================================================
# ANALYZE ONE URL
# =========================================================

def analyze_single_url(url):

    # Mobile and desktop are still
    # run simultaneously for each URL.
    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        mobile_future = (
            executor.submit(
                analyze_mobile,
                url
            )
        )

        desktop_future = (
            executor.submit(
                analyze_desktop,
                url
            )
        )

        mobile = (
            mobile_future.result()
        )

        desktop = (
            desktop_future.result()
        )

    error_messages = []

    if mobile["error"]:

        error_messages.append(
            "Mobile: "
            + mobile["error"]
        )

    if desktop["error"]:

        error_messages.append(
            "Desktop: "
            + desktop["error"]
        )

    return {
        "URL":
            url,

        "PageSpeed Mobile":
            mobile["score"],

        "PageSpeed Desktop":
            desktop["score"],

        "LCP Mobile":
            mobile["lcp"],

        "INP Mobile":
            mobile["inp"],

        "CLS Mobile":
            mobile["cls"],

        "CWV Data":
            mobile["cwv_data"],

        "Mobile Fetch":
            mobile["status"],

        "Desktop Fetch":
            desktop["status"],

        "Mobile Attempts":
            mobile["attempts"],

        "Desktop Attempts":
            desktop["attempts"],

        "Tested At":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "Error":
            " | ".join(
                error_messages
            )
    }


# =========================================================
# COLORS
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
# COLOR PAGESPEED
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

        numeric = float(
            value
        )

    except Exception:

        return gray_style()

    if numeric >= 90:

        return green_style()

    elif numeric >= 50:

        return orange_style()

    else:

        return red_style()


# =========================================================
# COLOR LCP
# =========================================================

def color_lcp(value):

    if value in [
        "N/A",
        None,
        ""
    ]:

        return gray_style()

    try:

        numeric = float(
            str(value)
            .replace(
                " s",
                ""
            )
            .strip()
        )

    except Exception:

        return gray_style()

    if numeric <= 2.5:

        return green_style()

    elif numeric <= 4.0:

        return orange_style()

    else:

        return red_style()


# =========================================================
# COLOR INP
# =========================================================

def color_inp(value):

    if value in [
        "N/A",
        None,
        ""
    ]:

        return gray_style()

    try:

        numeric = float(
            str(value)
            .replace(
                " ms",
                ""
            )
            .strip()
        )

    except Exception:

        return gray_style()

    if numeric <= 200:

        return green_style()

    elif numeric <= 500:

        return orange_style()

    else:

        return red_style()


# =========================================================
# COLOR CLS
# =========================================================

def color_cls(value):

    if value in [
        "N/A",
        None,
        ""
    ]:

        return gray_style()

    try:

        numeric = float(
            value
        )

    except Exception:

        return gray_style()

    if numeric <= 0.1:

        return green_style()

    elif numeric <= 0.25:

        return orange_style()

    else:

        return red_style()


# =========================================================
# EXCEL EXPORT
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

        workbook = (
            writer.book
        )

        worksheet = (
            writer.sheets[
                "PageSpeed Results"
            ]
        )

        # -------------------------------------------------
        # FORMATS
        # -------------------------------------------------

        header_format = (
            workbook.add_format({
                "bold": True,
                "bg_color": "#D9EAF7",
                "border": 1,
                "align": "center",
                "valign": "vcenter"
            })
        )

        green_format = (
            workbook.add_format({
                "bg_color": GREEN_BG,
                "font_color": GREEN_TEXT,
                "bold": True,
                "border": 1
            })
        )

        orange_format = (
            workbook.add_format({
                "bg_color": ORANGE_BG,
                "font_color": ORANGE_TEXT,
                "bold": True,
                "border": 1
            })
        )

        red_format = (
            workbook.add_format({
                "bg_color": RED_BG,
                "font_color": RED_TEXT,
                "bold": True,
                "border": 1
            })
        )

        gray_format = (
            workbook.add_format({
                "bg_color": GRAY_BG,
                "font_color": GRAY_TEXT,
                "border": 1
            })
        )

        normal_format = (
            workbook.add_format({
                "border": 1
            })
        )

        url_format = (
            workbook.add_format({
                "border": 1,
                "text_wrap": True
            })
        )

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
        # WIDTHS
        # -------------------------------------------------

        worksheet.set_column(
            0,
            0,
            60
        )

        worksheet.set_column(
            1,
            len(df.columns) - 1,
            18
        )

        worksheet.freeze_panes(
            1,
            1
        )

        # -------------------------------------------------
        # DATA
        # -------------------------------------------------

        for row_index, row in df.iterrows():

            excel_row = (
                row_index + 1
            )

            for col_index, column in enumerate(
                df.columns
            ):

                value = row[
                    column
                ]

                cell_format = (
                    normal_format
                )

                if column == "URL":

                    cell_format = (
                        url_format
                    )

                elif column in [
                    "PageSpeed Mobile",
                    "PageSpeed Desktop"
                ]:

                    try:

                        numeric = float(
                            value
                        )

                        if numeric >= 90:

                            cell_format = (
                                green_format
                            )

                        elif numeric >= 50:

                            cell_format = (
                                orange_format
                            )

                        else:

                            cell_format = (
                                red_format
                            )

                    except Exception:

                        cell_format = (
                            gray_format
                        )

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

                            cell_format = (
                                green_format
                            )

                        elif numeric <= 4.0:

                            cell_format = (
                                orange_format
                            )

                        else:

                            cell_format = (
                                red_format
                            )

                    except Exception:

                        cell_format = (
                            gray_format
                        )

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

                            cell_format = (
                                green_format
                            )

                        elif numeric <= 500:

                            cell_format = (
                                orange_format
                            )

                        else:

                            cell_format = (
                                red_format
                            )

                    except Exception:

                        cell_format = (
                            gray_format
                        )

                elif column == "CLS Mobile":

                    try:

                        numeric = float(
                            value
                        )

                        if numeric <= 0.1:

                            cell_format = (
                                green_format
                            )

                        elif numeric <= 0.25:

                            cell_format = (
                                orange_format
                            )

                        else:

                            cell_format = (
                                red_format
                            )

                    except Exception:

                        cell_format = (
                            gray_format
                        )

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

    urls = list(
        dict.fromkeys(
            urls
        )
    )

    if not urls:

        st.warning(
            "Please enter at least one URL."
        )

        st.stop()

    results = []

    progress = st.progress(
        0
    )

    status_text = (
        st.empty()
    )

    total_urls = len(
        urls
    )

    completed = 0

    # =====================================================
    # PARALLEL URLs
    # =====================================================

    with ThreadPoolExecutor(
        max_workers=URL_WORKERS
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

                result = (
                    future.result()
                )

            except Exception as e:

                result = {
                    "URL":
                        url,

                    "PageSpeed Mobile":
                        "Error",

                    "PageSpeed Desktop":
                        "Error",

                    "LCP Mobile":
                        "N/A",

                    "INP Mobile":
                        "N/A",

                    "CLS Mobile":
                        "N/A",

                    "CWV Data":
                        "N/A",

                    "Mobile Fetch":
                        "ERROR",

                    "Desktop Fetch":
                        "ERROR",

                    "Mobile Attempts":
                        0,

                    "Desktop Attempts":
                        0,

                    "Tested At":
                        datetime.now()
                        .strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),

                    "Error":
                        str(e)
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
        in enumerate(
            urls
        )
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
    # EXCEL
    # =====================================================

    excel_file = (
        create_excel_file(
            df
        )
    )

    st.download_button(
        label=(
            "Download Excel with Colors"
        ),
        data=excel_file,
        file_name=(
            "pagespeed_results.xlsx"
        ),
        mime=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    # =====================================================
    # CSV
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
        file_name=(
            "pagespeed_results.csv"
        ),
        mime="text/csv"
    )
