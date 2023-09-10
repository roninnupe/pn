import csv
import requests
from web3 import Web3
import time
import pandas as pd

# Initialize web3
web3 = Web3(Web3.HTTPProvider('https://nova.arbitrum.io/rpc'))
chain_id = 42170

def usd_to_eth(usd_amount):
    # CoinCap API URL for ETH price
    api_url = 'https://api.coincap.io/v2/assets/ethereum'

    try:
        # Make a GET request to the CoinCap API
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception if the request was not successful

        # Parse the JSON response
        data = response.json()

        # Extract the current ETH price in USD
        eth_price_usd = float(data['data']['priceUsd'])

        # Calculate the equivalent amount in ETH
        eth_amount = usd_amount / eth_price_usd

        return eth_amount

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None
    
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
selected_wallet, your_address, private_key = select_row_from_csv('../pn data/addresses.csv')

# Load the CSV file into a DataFrame
file_path = '../pn data/eth_recipient_addresses.csv'
df = pd.read_csv(file_path)

# Extract the 'address' column as a list
recipient_addresses = df['address'].tolist()

# get the number of recipients for display purposes
recipient_count = len(recipient_addresses)

# Amount to send (in Ether)
amount_in_USD = float(input(f"Enter the amount of USD to send to {recipient_count} wallets: $"))
amount_in_eth = usd_to_eth(amount_in_USD)
amount_in_wei = web3.to_wei(amount_in_eth, 'ether')

print(f"About to distribute {amount_in_eth} x {recipient_count} = {amount_in_eth * recipient_count}")
user_input = input("Do you want to proceed? (y/n): ").strip().lower()
if user_input != "y": 
    if user_input != "n": print("Terminating script. You must explicitly enter y to proceed")
    else: print("Okay, no Eth will be sent! Have a great day")
    exit()

# Main loop to send transactions
for recipient in recipient_addresses:
    # Get the current nonce
    nonce = web3.eth.get_transaction_count(your_address, 'latest')

    # Build the transaction
    transaction = {
        'from': your_address,
        'to': recipient,
        'value': amount_in_wei,
        'gasPrice': web3.to_wei('50', 'gwei'),
        'nonce': nonce,
        'chainId': chain_id,
    }

    # Estimate gas
    try:
        estimated_gas = web3.eth.estimate_gas(transaction)
        transaction['gas'] = estimated_gas
    except Exception as e:
        print(f"Error estimating gas: {e}")
        continue

    # Sign the transaction
    signed_transaction = web3.eth.account.sign_transaction(transaction, private_key)

    # Send the transaction
    try:
        transaction_hash = web3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        print(f"Transaction sent successfully! Transaction hash: {web3.to_hex(transaction_hash)}")
    except Exception as e:
        print(f"Transaction failed: {e}")

    # Delay to allow the network to update the nonce
    time.sleep(1)
