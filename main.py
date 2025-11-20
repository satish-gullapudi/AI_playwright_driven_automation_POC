import os
import subprocess
import streamlit as st
import pandas as pd
import inspect
import sys
from pathlib import Path
from Utilities.DBManager import DBManager
# Assuming test modules are accessible via sys.path or are in the current working directory
import ai_tests

# Initiating DB object for fetching tests and writing test results
db = DBManager()
conn, cursor = db.conn, db.cursor

TEST_MODULE = os.path.join(str(Path.cwd()), "ai_tests")


def initialize_tests_from_code(module):
    """
    Populates the 'tests' table with all functions starting with 'test_'
    found in the given module, if they don't already exist.
    """
    test_functions = []
    file_list = os.listdir(module)
    for file in file_list:
        if "test_" in file:
            test_functions.append(file)

    # Insert or ignore found test names into the 'tests' table
    for test_name in test_functions:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO tests (test_name) VALUES (?)
            """, (test_name,))
        except Exception as e:
            print(f"Error initializing test {test_name}: {e}")

    conn.commit()


# Initialize the tests list before the UI loads
initialize_tests_from_code(TEST_MODULE)


def get_tests():
    cursor.execute("SELECT id, test_name FROM tests")
    rows = cursor.fetchall()
    return rows


def update_run_status(test_id, run_status, result_status):
    cursor.execute("""
        UPDATE tests 
        SET run_status = ?, result_status = ?
        WHERE id = ?
    """, (run_status, result_status, test_id))
    conn.commit()


def run_pytest_test(test_name: str):
    """
    Executes a specific pytest test function within a specific file.
    """
    # Get the absolute path to the virtual environment's python.exe
    # VENV_PYTHON_EXE = os.environ.get("VENV_PYTHON_EXE_PATH")
    # if VENV_PYTHON_EXE:
    #     VENV_PYTHON_EXE = VENV_PYTHON_EXE.strip('"')
    VENV_PYTHON_EXE = os.path.join(str(Path.cwd()), ".venv", "Scripts", "python.exe")
    # print(f"Selected virtual environment: {VENV_PYTHON_EXE}")

    if not VENV_PYTHON_EXE or not os.path.exists(VENV_PYTHON_EXE):
        print("ERROR: Could not find virtual environment Python executable.")
        return "Fail"

    try:
        # Command: python -m pytest <file_path>::<test_function_name> --junitxml=report.xml
        command_list = [
            VENV_PYTHON_EXE,
            "-m", "pytest",
            f"{TEST_MODULE}\\{test_name}",  # Target the specific function
            # "--headless"  # Ensure it runs headless unless configured otherwise in conftest.py
        ]

        result = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
        )

        output = result.stdout
        print(f"Pytest STDOUT:\n{output}")
        print(f"Pytest STDERR:\n{result.stderr}")

        # Pass/Fail Logic: Pytest summary output
        if "1 passed in" in output and "0 failed" in output:
            return "Pass"
        elif "1 failed in" in output:
            return "Fail"
        else:
            # Handle errors like setup failure, collection errors, etc.
            return "Error"

    except Exception as e:
        print(f"Critical Exception running Pytest test: {e}")
        return "Error"


# --- Streamlit UI and Logic ---

st.title("🤖 AI-Driven Playwright Pytest Runner Dashboard")


# Cancel and Close Function
def close_app():
    st.success("Closing Streamlit application...")
    os._exit(0)


# Initialize session state for test selections if not present
if 'test_selections' not in st.session_state:
    st.session_state.test_selections = {}

test_options = get_tests()
if not test_options:
    st.warning(f"No tests available.")
else:
    st.subheader(f"Select AI Scenarios from '{TEST_MODULE}'")


    # Select All / Unselect All Functions
    def select_all():
        for test_id, test_name in test_options:
            st.session_state[f"checkbox_{test_id}"] = True


    def unselect_all():
        for test_id, test_name in test_options:
            st.session_state[f"checkbox_{test_id}"] = False


    # Select All / Unselect All Buttons
    col_select_all, col_unselect_all = st.columns(2)
    with col_select_all:
        st.button("Select All", on_click=select_all)
    with col_unselect_all:
        st.button("Unselect All", on_click=unselect_all)

    st.markdown("---")

    selected_tests = []

    # Checkboxes for Test Listing
    for test_id, test_name in test_options:
        if test_id not in st.session_state.test_selections:
            st.session_state.test_selections[test_id] = False

        is_selected = st.checkbox(
            f"**{test_name}**",
            value=st.session_state.test_selections[test_id],
            key=f"checkbox_{test_id}"
        )

        st.session_state.test_selections[test_id] = is_selected

        if is_selected:
            selected_tests.append((test_id, test_name))

    st.markdown("---")

    # Run and Cancel Buttons Side-by-Side
    col_run, col_cancel = st.columns([3, 1])

    with col_run:
        if st.button(f"Run {len(selected_tests)} Selected AI Tests", type="primary"):
            if not selected_tests:
                st.warning("Please select at least one test to run.")
            else:
                st.info("Note: Test execution output will appear in the console where Streamlit is running.")
                with st.spinner("Running selected AI tests using Pytest..."):
                    for test_id, test_name in selected_tests:
                        update_run_status(test_id, "Running", "...")

                        # Execute the Pytest test
                        result = run_pytest_test(test_name)

                        update_run_status(test_id, "Run", result)
                    st.success("AI-driven Pytest execution completed.")

    with col_cancel:
        # Cancel and Close Button
        if st.button("Cancel and Close"):
            close_app()

    # Show updated table
    st.subheader("📋 Current Test Status")
    # Fetch from the 'tests' table, which is updated after each run
    df = pd.read_sql("SELECT id, test_name, run_status, result_status FROM tests", conn)
    st.dataframe(df, width="stretch")