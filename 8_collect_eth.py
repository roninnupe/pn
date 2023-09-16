import csv
import requests
import time
import pandas as pd
import pn_helper as pn
import pandas as pd

def select_row_from_df(df):
    try:
        # Display the available wallets
        print("Available wallets:")
        print(df[['wallet', 'address']].to_string(index=False))

        # Ask the user to enter the wallet value
        selected_wallet = int(input("Enter wallet #: "))

        # Check if the input wallet value is in the DataFrame
        if selected_wallet in df['wallet'].tolist():
            # Find the corresponding row for the selected wallet
            selected_row = df[df['wallet'] == selected_wallet].iloc[0]

            # Retrieve the information from the selected row
            selected_wallet = selected_row['wallet']
            selected_address = selected_row['address']
            selected_key = selected_row['key']

            print(f"Selected Wallet: {selected_wallet}")
            print(f"Selected Address: {selected_address}")

            # Return the selected information
            return selected_wallet, selected_address, selected_key
        else:
            return None  # Wallet not found in the DataFrame
    except FileNotFoundError:
        return None  # File not found

print("\nPlease select the wallet you wish to collect all eth to:\n")

df = pd.read_csv(pn.data_path("addresses.csv"))

# Get input from user on the wallet we want to send money to
selected_wallet, recipient, pk = select_row_from_df(df)

for index, row in df.iterrows():
    wallet_name = row['wallet']
    address = row['address']
    key = row['key']
    amount_in_eth = pn.get_nova_eth_balance(address)

    if(amount_in_eth > 0.00001):
        if(address == recipient): continue #Skip sending money to yourself
        print(f"Sending {amount_in_eth} from {wallet_name} - {address} to {selected_wallet} - {recipient}")
        pn.send_nova_eth(address, recipient, amount_in_eth, key, True)
