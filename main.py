import sys
import json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.colors
import os

st.set_page_config(page_title="Finance App",page_icon="💰", layout="wide")

category_file = "categories.json"

if "expense_categories" not in st.session_state:
    st.session_state.expense_categories = ["Uncategorized"]

if "income_categories" not in st.session_state:
    st.session_state.income_categories = ["Uncategorized"]

if "expense_keywords" not in st.session_state:
    st.session_state.expense_keywords = {}

if "income_keywords" not in st.session_state:
    st.session_state.income_keywords = {}

if "credits_df" not in st.session_state:
    st.session_state.credits_df = pd.DataFrame()

if "debits_df" not in st.session_state:
    st.session_state.debits_df = pd.DataFrame()

if os.path.exists("category_file"):
    with open("category_file", "r") as f:
        loaded_data = json.load(f)
        st.session_state.expense_categories = loaded_data.get("expenses", ["Uncategorized"])
        st.session_state.income_categories = loaded_data.get("income", ["Uncategorized"])
        st.session_state.expense_keywords = loaded_data.get("expense_keywords", {})
        st.session_state.income_keywords = loaded_data.get("income_keywords", {})


def save_categories():
    categories_to_save = {
        "expenses": list(set(st.session_state.expense_categories)),
        "income": list(set(st.session_state.income_categories)),
        "expense_keywords": st.session_state.expense_keywords,
        "income_keywords": st.session_state.income_keywords,
    }
    with open("category_file", "w") as f:
        json.dump(categories_to_save, f)


def categorize_transactions(df, is_streamlit=True):
    df["Category"] = "Uncategorized"
    category_type = "expenses" if not df.empty and df["Amount"].iloc[0] < 0 else "income"

    if category_type == "expenses":
        keywords_dict = st.session_state.expense_keywords if is_streamlit else {}
        categories = st.session_state.expense_categories if is_streamlit else ["Uncategorized"]
    else:
        keywords_dict = st.session_state.income_keywords if is_streamlit else {}
        categories = st.session_state.income_categories if is_streamlit else ["Uncategorized"]

    for idx, row in df.iterrows():
        description = row["Description"].lower().strip()
        for category in categories:
            if category == "Uncategorized":
                continue
            keywords = [kw.lower().strip() for kw in keywords_dict.get(category, [])]
            if description in keywords:
                df.at[idx, "Category"] = category
                break
    return df


def load_transcations(file, is_streamlit=True):
    try:
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        df["Amount"] = df["Amount"].str.replace(",", "").astype(float)
        df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y %H:%M")

        debits_df = df[df["Amount"] < 0].copy()
        credits_df = df[df["Amount"] > 0].copy()
        if is_streamlit:
            st.session_state.debits_df = categorize_transactions(debits_df.copy(),is_streamlit)
            st.session_state.credits_df = categorize_transactions(credits_df.copy(),is_streamlit)
        return  {"debits":debits_df,"credits":credits_df}
    except Exception as e:
        if is_streamlit:
           st.error(f"Error processing file: {str(e)}")
        return None


def add_keyword_to_category(category, keyword, category_type="expenses", is_streamlit=True):
    keyword = keyword.strip()
    if category:
        if category_type == "expenses":
            if is_streamlit:
                if category not in st.session_state.expense_keywords:
                    st.session_state.expense_keywords[category] = []
                if keyword not in st.session_state.expense_keywords[category]:
                    st.session_state.expense_keywords[category].append(keyword)
                    save_categories()
                    return True
        elif category_type == "income":
            if is_streamlit:
                if category not in st.session_state.income_keywords:
                    st.session_state.income_keywords[category] = []
                if keyword not in st.session_state.income_keywords[category]:
                    st.session_state.income_keywords[category].append(keyword)
                    save_categories()
                    return True
    return False


def add_new_category(new_category, category_type="expenses", is_streamlit=True):
    new_category = new_category.strip()
    if new_category:
        if category_type == "expenses" and (not new_category in st.session_state.expense_categories if is_streamlit else []):
            if is_streamlit:
                st.session_state.expense_categories.append(new_category)
                save_categories()
            return True
        elif category_type == "income" and (not new_category in st.session_state.income_categories if is_streamlit else []):
            if is_streamlit:
                st.session_state.income_categories.append(new_category)
                save_categories()
            return True
    return False

def process_data_for_node(file_path):
    """
    Processes the transaction data and returns a JSON serializable result.
    This function is specifically designed to be called from Node.js.
    """
    result = {}
    loaded_data = load_transcations(file_path,is_streamlit=False)
    if loaded_data:
        debits_df = loaded_data["debits"]
        credits_df = loaded_data["credits"]
        
        debits_df = categorize_transactions(debits_df,is_streamlit=False)
        credits_df = categorize_transactions(credits_df,is_streamlit=False)
        
        result["debits_summary"] = debits_df.groupby("Category")["Amount"].sum().abs().to_dict()
        result["credits_summary"] = credits_df.groupby("Category")["Amount"].sum().to_dict()
        result["status"] = "success"
    else:
        result["status"] = "error"
        result["message"] = "Failed to process transaction data."
    return result


def main():
    st.title("Finance Dashboard")
    uploaded_file = st.file_uploader("Upload your Transcation CSV", type=["csv"])

    # Categorize the income and expenses
    if uploaded_file is not None:
        if load_transcations(uploaded_file):
            tab1, tab2 = st.tabs(["Expenses(Debits)", "Income (Credits)"])
            with tab1:
                new_expense_category = st.text_input("New Expense Category Name")
                add_expense_category_button = st.button("Add Expense Category")

                if add_expense_category_button and new_expense_category:
                    if add_new_category(new_expense_category, "expenses"):
                        st.rerun()

                st.subheader("Your Expenses")
                display_debits_df = st.session_state.debits_df[["Date", "Description", "Amount", "Balance", "Category"]].copy()
                display_debits_df["Amount"] = display_debits_df["Amount"].abs()

                edited_debits_df = st.data_editor(
                    display_debits_df,
                    column_config={
                        "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                        "Amount": st.column_config.NumberColumn("Amount", format="%.2f INR"),
                        "Category": st.column_config.SelectboxColumn("Category", options=st.session_state.expense_categories),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="debits_category_editor",
                )

                save_debits_button = st.button("Apply Expense Category Changes", type="primary")
                if save_debits_button:
                    updated_categories_from_editor = edited_debits_df["Category"].unique().tolist()
                    # Update the session state directly
                    st.session_state.expense_categories = sorted(list(set(st.session_state.expense_categories + updated_categories_from_editor)))
                    save_categories()  # Save the updated state to the JSON

                    # Optionally, you can use st.success to give visual feedback
                    st.success("Expense categories updated!")
                    # You might not need an immediate rerun if the state is updated
                    # st.rerun()

                    for idx, row in edited_debits_df.iterrows():
                        new_category = row["Category"]
                        if row["Category"] != st.session_state.debits_df.at[idx, "Category"]:
                            description = row["Description"]
                            add_keyword_to_category(new_category, description, "expenses")

                st.subheader('Expense Summary')
                category_totals = st.session_state.debits_df.groupby("Category")["Amount"].sum().reset_index()
                category_totals["Amount"] = category_totals["Amount"].abs()
                st.dataframe(
                    category_totals,
                    column_config={"Amount": st.column_config.NumberColumn("Amount", format="%.2f INR")},
                    use_container_width=True,
                    hide_index=True,
                )

                st.subheader('Expense Distribution (Bar Chart)')
                fig_bar_expenses = px.bar(
                    category_totals,
                    x="Category",
                    y="Amount",
                    title="Expenses by Category",
                    labels={"Amount": "Total Expense (INR)", "Category": "Expense Category"},
                    color="Amount",
                    color_continuous_scale=plotly.colors.sequential.Plasma,
                    template="plotly_dark",
                    hover_data=["Amount"],
                )
                fig_bar_expenses.update_layout(
                    xaxis_title="Expense Category",
                    yaxis_title="Total Expense (INR)",
                    uniformtext_minsize=8,
                    uniformtext_mode='hide',
                )
                st.plotly_chart(fig_bar_expenses, use_container_width=True)

            with tab2:
                new_income_category = st.text_input("New Income Category Name")
                add_income_category_button = st.button("Add Income Category")

                if add_income_category_button and new_income_category:
                    if add_new_category(new_income_category, "income"):
                        st.rerun()

                st.subheader("Payments Summary")
                total_payments = st.session_state.credits_df["Amount"].sum()
                st.metric("Total Payments", f"{total_payments:,.2f} INR")

                # Create a data editor for income transactions
                display_credits_df = st.session_state.credits_df[["Date", "Description", "Amount", "Balance", "Category"]].copy()

                edited_credits_df = st.data_editor(
                    display_credits_df,
                    column_config={
                        "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                        "Amount": st.column_config.NumberColumn("Amount", format="%.2f INR"),
                        "Category": st.column_config.SelectboxColumn("Category", options=st.session_state.income_categories),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="credits_category_editor",
                )

                save_credits_button = st.button("Apply Income Category Changes", type="primary")
                if save_credits_button:
                    updated_income_categories = edited_credits_df["Category"].unique().tolist()
                    # Update the session state directly
                    st.session_state.income_categories = sorted(list(set(st.session_state.income_categories + updated_income_categories)))
                    save_categories()  # Save the updated state to the JSON

                    # Optionally, you can use st.success to give visual feedback
                    st.success("Income categories updated!")
                    # You might not need an immediate rerun if the state is updated
                    # st.rerun()

                for idx, row in edited_credits_df.iterrows():
                    new_category = row["Category"]
                    if row["Category"] != st.session_state.credits_df.at[idx, "Category"]:
                        description = row["Description"]
                        add_keyword_to_category(new_category, description, "income")

                # --- Income Pie Chart ---
                st.subheader('Income Distribution (Pie Chart)')
                income_category_totals = st.session_state.credits_df.groupby("Category")["Amount"].sum().reset_index()
                income_category_totals = income_category_totals.sort_values("Amount", ascending=False)

                if not income_category_totals.empty:
                    fig_pie_income = px.pie(
                        income_category_totals,
                        values="Amount",
                        names="Category",
                        title="Income by Category",
                        hole=0.3,
                        color="Category",
                        hover_data=["Amount"],
                        labels={"Amount": "Total (INR)", "Category": "Income Source"},
                        template="plotly_dark",
                    )
                    fig_pie_income.update_traces(
                        textinfo='percent+label',
                        textfont_size=12,
                        marker=dict(line=dict(color='white', width=1)),
                    )
                    st.plotly_chart(fig_pie_income, use_container_width=True)
                else:
                    st.info("No income transactions to display in the pie chart.")

main()