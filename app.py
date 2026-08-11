import streamlit as st
import requests
import pandas as pd

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


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

MAX_WORKERS = 6


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
    """
    Run PageSpeed Insights analysis for:
    - mobile
    - desktop
    """

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
    """
    Lighthouse score is returned as 0-1.
    Convert to 0-100.
    """

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
# MOBILE CWV
# =========================================================

def extract_mobile_cwv(data):
    """
    Extract URL-level CrUX data from mobile PSI result.

    Does NOT use origin fallback as URL-level data.
    """

    loading_experience = data.get(
        "loadingExperience",
        {}
    )

    # Google may fall back to origin data.
    # We do not treat that as page-level CWV.
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
    """
    Runs mobile + desktop PSI in parallel
    for one URL.
    """

    result = {
        "URL": url,
        "PageSpeed Mobile": "Error",
        "PageSpeed Desktop": "Error",
        "LCP": "N/A",
        "INP": "N/A",
        "CLS": "N/A",
        "CWV Data": "N/A",
        "Tested At": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "Error": ""
    }

    try:

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

        # -------------------------------------------------
        # MOBILE SCORE
        # -------------------------------------------------

        mobile_score = (
            extract_performance_score(
                mobile_data
            )
        )

        if mobile_score is not None:

            result[
                "PageSpeed Mobile"
            ] = mobile_score

        # -------------------------------------------------
        # DESKTOP SCORE
        # -------------------------------------------------

        desktop_score = (
            extract_performance_score(
                desktop_data
            )
        )

        if desktop_score is not None:

            result[
                "PageSpeed Desktop"
            ] = desktop_score

        # -------------------------------------------------
        # MOBILE CWV
        # -------------------------------------------------

        cwv = extract_mobile_cwv(
            mobile_data
        )

        result["LCP"] = format_value(
            cwv["LCP"],
            " s"
        )

        result["INP"] = format_value(
            cwv["INP"],
            " ms"
        )

        result["CLS"] = format_value(
            cwv["CLS"]
        )

        result[
            "CWV Data"
        ] = cwv["CWV Data"]

    except Exception as e:

        result["Error"] = str(e)

    return result


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
    # but preserve original order
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

    total_urls = len(
        urls
    )

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
                    "LCP": "N/A",
                    "INP": "N/A",
                    "CLS": "N/A",
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
    # RESULTS
    # =====================================================

    df = pd.DataFrame(
        results
    )

    st.subheader(
        "Results"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=650
    )

    # =====================================================
    # DOWNLOAD
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
