import streamlit as st
from utils import project_id, run_query
import pandas as pd
from datetime import datetime
from scipy.stats import percentileofscore
from millify import millify
import numpy as np

st.set_page_config(
    page_title="Performance by Members",
    page_icon="💬",
    initial_sidebar_state="expanded",
)

# BACKEND

def average_non_zero(x):
    non_zero_values = x[x != 0]  # Select non-zero values
    if len(non_zero_values) > 0:
        return np.mean(non_zero_values)  # Calculate the mean of non-zero values
    else:
        return 0  # Return 0 if there are no non-zero values

def get_member_list():
    query = f"""
    select
        member_name,
        member_birth_year,
        member_image_link,
        party,
        earliest_sitting,
        latest_sitting,
        count_sittings_present,
        count_sittings_total
    from `{project_id}.prod_dim.dim_members`
    where member_name != '' and member_name is not null
    """
    return pd.DataFrame(run_query(query))


def get_member_positions():
    query = f"""
    select * from `{project_id}.prod_fact.fact_member_positions`
    """
    return pd.DataFrame(run_query(query))


def get_all_member_speeches():
    query = f"""
    with
        speeches_summary as (
            select
                member_name,
                extract(year from date) as year,
                count(distinct date) as count_sittings_spoken,
                count(distinct topic_id) as count_topics,
                count(*) as count_speeches,
                sum(count_speeches_words) as count_words,
                countif(is_primary_question) as count_pri_questions,
                206.835
                - (1.015 * sum(count_speeches_words) / sum(count_speeches_sentences))
                - (
                    84.6 * sum(count_speeches_syllables) / sum(count_speeches_words)
                ) as readability
            from `{project_id}.prod_mart.mart_speeches`
            where
                member_name != ''
                and not lower(member_name) like any ('%deputy%', '%speaker%', '%chairman%')
            group by all
        ),

        attendance_summary as (
            select
                member_name,
                extract(year from date) as year,
                countif(is_present) as count_sittings_attended
            from `{project_id}.prod_fact.fact_attendance`
            group by all
        )

    select
        s.member_name,
        s.year,
        a.count_sittings_attended,
        s.count_sittings_spoken,
        s.count_topics,
        s.count_speeches,
        s.count_words,
        s.count_pri_questions,
        s.readability
    from speeches_summary as s
    left join attendance_summary as a on s.member_name = a.member_name and s.year = a.year
    """

    return pd.DataFrame(run_query(query))


def get_member_speeches(member_name):
    all_members_speeches_summary = get_all_member_speeches()
    return all_members_speeches_summary[
        all_members_speeches_summary["member_name"] == member_name
    ]


members_df = get_member_list()
member_names = sorted(members_df["member_name"].unique())
member_positions_df = get_member_positions()

## average metrics:
all_members_speech_summary = get_all_member_speeches()
column_names = [
    "count_sittings_attended",
    "count_sittings_spoken",
    "count_topics",
    "count_speeches",
    "count_words",
    "count_pri_questions",
]

## average by member:
agg_by_member_dict = {col: "sum" for col in column_names}

aggregated_by_member = (
    all_members_speech_summary.groupby("member_name").agg(agg_by_member_dict).reset_index()
)
aggregated_by_member.columns = ["member_name"] + column_names

aggregated_by_member["participation_rate"] = (
    aggregated_by_member["count_sittings_spoken"]
    / aggregated_by_member["count_sittings_attended"]
    * 100
)
aggregated_by_member["topics_per_sitting"] = (
    aggregated_by_member["count_topics"] / aggregated_by_member["count_sittings_spoken"]
)
aggregated_by_member["questions_per_sitting"] = (
    aggregated_by_member["count_pri_questions"]
    / aggregated_by_member["count_sittings_spoken"]
)
aggregated_by_member["words_per_sitting"] = (
    aggregated_by_member["count_words"] / aggregated_by_member["count_sittings_spoken"]
)

aggregated_by_member = aggregated_by_member[
    aggregated_by_member["count_sittings_attended"] != 0
]

## average by year:
agg_by_year_dict = {col: average_non_zero for col in column_names}

aggregated_by_year = (
    all_members_speech_summary.groupby("year").agg(agg_by_year_dict).reset_index()
)
aggregated_by_year.columns = ["year"] + [f'avg_{column_name}' for column_name in column_names]
aggregated_by_year['year'] = aggregated_by_year['year'].astype(str).str.replace('[,.]', '', regex=True)

EARLIEST_SITTING = "2012-09-10"

# FRONTEND

select_member = st.sidebar.selectbox(
    label="Which member are you interested in?",
    options=member_names,
    index=None,
    placeholder="Choose member name",
)

st.title("Performance by Members")
st.warning("Under construction.")

if not select_member:
    st.error("Please select a member on the sidebar.")

if select_member:
    member_info, member_picture = st.columns([3, 1])
    member_df = members_df[members_df["member_name"] == select_member]

    with member_info:
        st.header(select_member)

        member_birth_year = member_df["member_birth_year"].iloc[0]
        if member_birth_year:
            member_birth_year_int = int(member_birth_year)
            member_age_int = datetime.now().year - member_birth_year_int
            st.markdown(
                f"""
                        * Last Political Affiliation: {member_df['party'].iloc[0]}
                        * Birth Year: {member_birth_year_int} (_Age: {member_age_int}_)
                        """
            )
        else:
            st.markdown(
                """
                        * Birth Year: _unknown_
                        """
            )

        condition_earliest_sitting_in_dataset = (
            str(member_df["earliest_sitting"].iloc[0]) > EARLIEST_SITTING
        )

        if condition_earliest_sitting_in_dataset:
            member_earliest_sitting = member_df["earliest_sitting"].iloc[0]
        else:
            member_earliest_sitting = (
                str(member_df["earliest_sitting"].iloc[0]) + " _or before_"
            )
        member_latest_sitting = member_df["latest_sitting"].iloc[0]

        if not condition_earliest_sitting_in_dataset:
            st.info(
                f"The earliest sitting is likely before this date, but the earliest date in the dataset is {EARLIEST_SITTING}, and therefore this is the earliest date which is displayed."
            )

        count_sittings_present = member_df["count_sittings_present"].iloc[0]
        count_sittings_total = member_df["count_sittings_total"].iloc[0]

        st.markdown(
            f"""
                    * Earliest Sitting: {member_earliest_sitting}
                    * Latest Sitting: {member_latest_sitting}
                    * Attendance: {count_sittings_present/count_sittings_total*100:.1f}% (_{count_sittings_present} out of {count_sittings_total} sittings_)
                    """
        )

    with member_picture:
        member_image_link = member_df["member_image_link"].iloc[0]
        if member_image_link:
            st.image(image=str(member_image_link), width=150)

    st.divider()
    st.subheader("Speeches")

    speech_summary = get_member_speeches(select_member)
    speech_summary['year'] = speech_summary['year'].astype(str).str.replace('[,.]', '', regex=True)
    speech_summary = speech_summary.merge(aggregated_by_year, how='left', on='year')

    if not condition_earliest_sitting_in_dataset:
        st.warning(
            f"As this member was elected before the earliest sitting ({EARLIEST_SITTING}), the information below reflects information from sittings on {EARLIEST_SITTING} and after."
        )

    not_eligible_to_ask_questions = (
        # is political appointee
        (
            not member_positions_df.loc[
                (member_positions_df["member_name"] == select_member)
                & (member_positions_df["type"] == "appointment")
            ].empty
        )
        and
        # is not mayor
        (
            member_positions_df.loc[
                (member_positions_df["member_name"] == select_member)
                & member_positions_df["member_position"].str.contains(
                    "mayor", case=False
                )
            ].empty
        )
    )

    if not_eligible_to_ask_questions:
        st.success(
            f"As this member has a political appointment (e.g. Minister, Parliamentary Secretary, Minister of State), they will not ask questions during parliamentary proceedings. Instead, they answer questions. If there are values for questions asked, this could either be before the member became a political appointee or a bug."
        )

    metric1, metric2, metric3, metric4, metric5 = st.columns(5)
    with metric1:
        st.metric(
            label="Sittings Attended",
            value=f"{speech_summary['count_sittings_attended'].sum():,.0f}",
        )
        st.metric(
            label="Sittings Spoken",
            value=f"{speech_summary['count_sittings_spoken'].sum():,.0f}",
        )
    with metric2:
        st.metric(label="Topics", value=f"{speech_summary['count_topics'].sum():,.0f}")
        member_participation_rate = speech_summary['count_sittings_spoken'].sum()/speech_summary['count_sittings_attended'].sum()*100
        st.metric(
            label="Participation (%)",
            value=f"{member_participation_rate:.1f}%",
            help="Sittings Spoken in divided by Sittings Attended",
        )
        st.caption(f"Percentile: {percentileofscore(aggregated_by_member['participation_rate'], member_participation_rate):.1f}")
        st.caption(f"Average: {aggregated_by_member['participation_rate'].mean():.1f}%")
    with metric3:
        st.metric(
            label="Speeches Made", value=f"{speech_summary['count_speeches'].sum():,.0f}"
        )
        member_topics_per_sitting = speech_summary['count_topics'].sum()/speech_summary['count_sittings_spoken'].sum()
        st.metric(
            label="Topics/Sitting",
            value=f"{member_topics_per_sitting:,.2f}",
        )
        st.caption(f"Percentile: {percentileofscore(aggregated_by_member['topics_per_sitting'], member_topics_per_sitting):.1f}")
        st.caption(f"Average: {aggregated_by_member['topics_per_sitting'].mean():,.2f}")
    with metric4:
        st.metric(
            label="Qns Asked", value=f"{speech_summary['count_pri_questions'].sum():,.0f}"
        )
        member_questions_per_sitting = speech_summary['count_pri_questions'].sum()/speech_summary['count_sittings_spoken'].sum()
        st.metric(
            label="Qns/Sitting",
            value=f"{member_questions_per_sitting:,.2f}",
        )
        if not_eligible_to_ask_questions:
            st.caption("N/A")
        else:
            st.caption(f"Percentile: {percentileofscore(aggregated_by_member['questions_per_sitting'], member_questions_per_sitting):.1f}")
            st.caption(
                f"Average: {aggregated_by_member[aggregated_by_member['questions_per_sitting'] != 0]['questions_per_sitting'].mean():,.2f}"
            )
    with metric5:
        st.metric(
            label="Words Spoken", value=f"{millify(speech_summary['count_words'].sum(), precision=1)}"
        )
        member_words_per_sitting = speech_summary['count_words'].sum()/speech_summary['count_sittings_spoken'].sum()
        st.metric(
            label="Words/Sitting",
            value=f"{millify(member_words_per_sitting, precision=1)}",
        )
        st.caption(f"Percentile: {percentileofscore(aggregated_by_member['words_per_sitting'], member_words_per_sitting):.1f}")
        st.caption(f"Average: {millify(aggregated_by_member['words_per_sitting'].mean(), precision=1)}")

    st.divider()
    st.write("Over the years:")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.line_chart(data=speech_summary, x="year", y=["count_topics", "avg_count_topics"], height=200)
        st.line_chart(data=speech_summary, x="year", y=["count_pri_questions", "avg_count_pri_questions"], height=200)
    with col2:
        st.line_chart(data=speech_summary, x="year", y=["count_speeches", "avg_count_speeches"], height=200)
        st.line_chart(data=speech_summary, x="year", y=["count_words", "avg_count_words"], height=200)
    st.line_chart(data=speech_summary, x="year", y="readability", height=200)

    st.divider()
    st.subheader("Positions")
    positions_df = member_positions_df[
        member_positions_df["member_name"] == select_member
    ]
    columns_to_display = [
        "member_position",
        "effective_from_date",
        "effective_to_date",
        "is_latest_position",
    ]

    constituencies_df = positions_df[positions_df["type"] == "constituency"][
        columns_to_display
    ]
    if not constituencies_df.empty:
        st.write("Constituencies")
        st.dataframe(constituencies_df, use_container_width=True, hide_index=True)

    appointments_df = positions_df[positions_df["type"] == "appointment"][
        columns_to_display
    ]
    if not appointments_df.empty:
        st.write("Political Appointments")
        st.dataframe(appointments_df, use_container_width=True, hide_index=True)
