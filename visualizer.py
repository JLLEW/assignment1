import argparse
import tkinter as tk
from tkinter import ttk
import pandas as pd


class OptionChainVisualizer:
    def __init__(self, root, csv_file):
        """
        Initialize the Option Chain Visualizer.

        Args:
            root (tk.Tk): The root Tkinter window.
            csv_file (str): Path to the CSV file containing the option chain data.
        """
        self.root = root
        self.csv_file = csv_file
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        # Load the data and create tabs
        self.load_data()

    def load_data(self):
        """
        Load the CSV file and create tabs for each iteration.
        """
        try:
            # Read the CSV file
            df = pd.read_csv(self.csv_file)

            # Group data by timestamp (each iteration is a separate timestamp)
            grouped = df.groupby("timestamp")

            for timestamp, group in grouped:
                self.create_tab(timestamp, group)
        except Exception as e:
            print(f"Error loading data: {e}")

    def create_tab(self, timestamp, group):
        """
        Create a tab for a specific iteration.

        Args:
            timestamp (str): The timestamp for the iteration.
            group (pd.DataFrame): The DataFrame containing the data for the iteration.
        """
        # Create a new frame for the tab
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=timestamp)

        # Create a Treeview widget to display the option chain
        tree = ttk.Treeview(frame, columns=("Call Predicted", "Call Actual", "Strike", "Put Predicted", "Put Actual"), show="headings")
        tree.pack(fill="both", expand=True)

        # Define column headings
        tree.heading("Call Predicted", text="Call Predicted")
        tree.heading("Call Actual", text="Call Actual")
        tree.heading("Strike", text="Strike")
        tree.heading("Put Predicted", text="Put Predicted")
        tree.heading("Put Actual", text="Put Actual")

        # Set column widths
        tree.column("Call Predicted", width=120, anchor="center")
        tree.column("Call Actual", width=120, anchor="center")
        tree.column("Strike", width=80, anchor="center")
        tree.column("Put Predicted", width=120, anchor="center")
        tree.column("Put Actual", width=120, anchor="center")

        # Populate the Treeview with data
        strikes = group["strike_price"].unique()
        for strike in strikes:
            call_predicted = group.loc[(group["strike_price"] == strike) & (group["option_type"] == "call"), "computed_mark_price"].values
            call_actual = group.loc[(group["strike_price"] == strike) & (group["option_type"] == "call"), "deribit_mark_price"].values
            put_predicted = group.loc[(group["strike_price"] == strike) & (group["option_type"] == "put"), "computed_mark_price"].values
            put_actual = group.loc[(group["strike_price"] == strike) & (group["option_type"] == "put"), "deribit_mark_price"].values

            # Handle missing values
            call_predicted = call_predicted[0] if len(call_predicted) > 0 and not pd.isna(call_predicted[0]) else "-"
            call_actual = call_actual[0] if len(call_actual) > 0 and not pd.isna(call_actual[0]) else "-"
            put_predicted = put_predicted[0] if len(put_predicted) > 0 and not pd.isna(put_predicted[0]) else "-"
            put_actual = put_actual[0] if len(put_actual) > 0 and not pd.isna(put_actual[0]) else "-"

            # Insert data into the Treeview
            tree.insert("", "end", values=(call_predicted, call_actual, strike, put_predicted, put_actual))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the option pricing main loop.")
    parser.add_argument("--input-file", type=str, default="output.csv")

    args = parser.parse_args()
    # Path to the CSV file
    csv_file = args.input_file

    # Create the Tkinter root window
    root = tk.Tk()
    root.title("Option Chain Visualizer")
    root.geometry("800x600")

    # Initialize and run the visualizer
    visualizer = OptionChainVisualizer(root, csv_file)
    root.mainloop()