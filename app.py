import streamlit as st
import requests
import pandas as pd
from datetime import datetime


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
# HELPERS
# =========================================================

def get_pagespeed_data(url, strategy):
    """
    Runs PageSpeed Insights for one URL and one strategy.

    strategy:
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


def extract_performance_score(data):
    """
    Lighthouse Performance score.

    API returns 0-1.
    We convert it to 0-100.
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


def extract_mobile_cwv(data):
    """
    Extract URL-level mobile field data.

    We intentionally do NOT use origin fallback.
    """

    loading_experience = data.get(
        "loadingExperience",
        {}
    )

    # If PSI explicitly says it used origin fallback,
    # do not present those numbers as URL-level CWV.
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

    # ---------------------------------------------
    # LCP
    # ---------------------------------------------

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

    # ---------------------------------------------
    # INP
    # ---------------------------------------------

    inp_metric = metrics.get(
        "INTERACTION_TO_NEXT_PAINT"
    )

    if inp_metric:
        inp = inp_metric.get(
            "percentile"
        )
    else:
        inp = None

    # ---------------------------------------------
    # CLS
    # ---------------------------------------------

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


def format_value(value, suffix=""):
    if value is None:
        return "N/A"

    return f"{value}{suffix}"


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

    # Remove exact duplicates but keep order
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

    for index, url in enumerate(urls):

        status_text.write(
            f"Analyzing {index + 1} / {total_urls}: {url}"
        )

        row = {
            "URL": url,
            "PageSpeed Mobile": "Error",
            "PageSpeed Desktop": "Error",
            "LCP": "N/A",
            "INP": "N/A",
            "CLS": "N/A",
            "CWV Data": "N/A",
            "Tested At": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

        try:

            # ---------------------------------------------
            # MOBILE
            # ---------------------------------------------

            mobile_data = get_pagespeed_data(
                url,
                "mobile"
            )

            mobile_score = (
                extract_performance_score(
                    mobile_data
                )
            )

            if mobile_score is not None:
                row[
                    "PageSpeed Mobile"
                ] = mobile_score

            # ---------------------------------------------
            # MOBILE CWV
            # ---------------------------------------------

            cwv = extract_mobile_cwv(
                mobile_data
            )

            row["LCP"] = format_value(
                cwv["LCP"],
                " s"
            )

            row["INP"] = format_value(
                cwv["INP"],
                " ms"
            )

            row["CLS"] = format_value(
                cwv["CLS"]
            )

            row[
                "CWV Data"
            ] = cwv["CWV Data"]

            # ---------------------------------------------
            # DESKTOP
            # ---------------------------------------------

            desktop_data = get_pagespeed_data(
                url,
                "desktop"
            )

            desktop_score = (
                extract_performance_score(
                    desktop_data
                )
            )

            if desktop_score is not None:
                row[
                    "PageSpeed Desktop"
                ] = desktop_score

        except Exception as e:

            row["Error"] = str(e)

        results.append(
            row
        )

        progress.progress(
            (index + 1)
            / total_urls
        )

    status_text.empty()

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
