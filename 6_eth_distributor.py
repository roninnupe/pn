import csv
import requests
import time
import pandas as pd
import pn_helper as pn
import pandas as pd

def select_row_from_csv(csv_file):
    try:
        # Load the CSV file into a DataFrame
        df = pd.read_csv(csv_file)

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

print("\nPlease select the wallet you wish to distribute Eth from:\n")

# Get input from user on the wallet we want to send money from
selected_wallet, your_address, private_key = select_row_from_csv(pn.data_path("addresses.csv"))

# Load the CSV file into a DataFrame
file_path = pn.data_path("eth_recipient_addresses.csv")
df = pd.read_csv(file_path)

# Extract the 'address' column as a list
recipient_addresses = df['address'].tolist()

# Get your eth_balance and USD estimate of the wallet sending
your_eth_balance = pn.get_nova_eth_balance(your_address)
your_nova_usd_estimate = pn.eth_to_usd(your_eth_balance)

# get the number of recipients for display purposes
recipient_count = len(recipient_addresses)

# Amount to send (in Ether)
print(f"You have {your_eth_balance} eth (~${your_nova_usd_estimate} USD)")
user_input = input(f"\tenter the amount of USD (or EQUAL) to send to {recipient_count} wallets: $")
if user_input.upper() == "EQUAL" :
    amount_in_eth = (your_eth_balance / (recipient_count + 1 ))
    amount_in_USD = pn.eth_to_usd(amount_in_eth)
    subtract_gas = True
else:
    amount_in_USD = float(user_input)
    amount_in_eth = pn.usd_to_eth(amount_in_USD)
    subtract_gas = False

print(f"About to distribute {amount_in_eth} (${amount_in_USD}) x {recipient_count} = {amount_in_eth * recipient_count}")
user_input = input("Do you want to proceed? (y/n): ").strip().lower()
if user_input != "y": 
    if user_input != "n": print("Terminating script. You must explicitly enter y to proceed")
    else: print("Okay, no Eth will be sent! Have a great day")
    exit()

# Main loop to send transactions
for recipient in recipient_addresses:
    # Send the eth
    pn.send_nova_eth(your_address, recipient, amount_in_eth, private_key, subtract_gas)
    # Delay to allow the network to update the nonce
    time.sleep(1)
