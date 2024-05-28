import streamlit as st
import plotly.express as px

from agg_data import get_member_list, get_all_member_speeches
from members import aggregate_member_metrics
from utils import (
    calculate_readability,
    process_metric_columns,
    EARLIEST_SITTING,
    PARTY_COLOURS,
    PARTY_SHAPES,
)

# BACKEND

members_df = get_member_list()
member_names = sorted(members_df["member_name"].unique())

all_members_speech_summary = get_all_member_speeches()

aggregated_by_member_parliament = aggregate_member_metrics(
    all_members_speech_summary,
    calculate_readability,
    group_by_fields=[
        "member_name",
        "member_party",
        "member_constituency",
        "parliament",
    ],
)

# SELECTIONS

parliaments = {"13th Parliament": [13], "14th Parliament": [14], "All": [12, 13, 14]}

select_parliament = st.selectbox("Select Parliament", parliaments)

# FRONTEND

st.markdown(
    """
    <style>
    .custom-title {
        font-size: 24px;
        font-family: 'Arial', sans-serif;
        color: #333333;
    }
    </style>
    """, 
    unsafe_allow_html=True
)

# Using the custom CSS class
st.markdown('<h1 class="custom-title">Participation and Attendance</h1>', unsafe_allow_html=True)

tabs = [
    "Participation",
    "Questions Asked",
    "Sitting Contributions",
    "Readability",
]

participation_cols = {
        "member_name": "Member Name",
        "participation_rate": "Participation (%)",
        "attendance": "Attendance (%)",
        "count_sittings_spoken": "# Spoken",
        "count_sittings_attended": "# Attended",
        "count_sittings_total": "# Total",
        "member_party": "Party",
        "member_constituency": "Constituency",
    }

processed = aggregate_member_metrics(
    aggregated_by_member_parliament[
        aggregated_by_member_parliament["parliament"].isin(
            parliaments[select_parliament]
        )
    ],
    calculate_readability,
    group_by_fields=["member_name", "member_party", "member_constituency"],
)

processed = processed[participation_cols.keys()]

processed["# Rank"] = processed["participation_rate"].rank(
    ascending=False, method="min"
)

columns_to_round = ['attendance', 'participation_rate']

processed[columns_to_round] = processed[columns_to_round].apply(lambda x: x.round(1))

processed.rename(columns=participation_cols, inplace=True)

fig = px.scatter(processed, x="Attendance (%)", y="Participation (%)",
                 color="Party", 
                 hover_data={"Member Name": True, 
                             "Attendance (%)": True, 
                             "Participation (%)": True,
                             "Party": False},
                 title=select_parliament)

# Customize hover template
fig.update_traces(
    hovertemplate='<b>%{customdata[0]}</b><br>' +
                  'Attendance: %{x}%<br>' +
                  'Participation: %{y}%<br>'
)

st.plotly_chart(fig)