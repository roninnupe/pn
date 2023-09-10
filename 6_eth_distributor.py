import csv
from web3 import Web3
import time

# Initialize web3
web3 = Web3(Web3.HTTPProvider('https://nova.arbitrum.io/rpc'))

# Your account details
your_address = ''
private_key = ''
chain_id = 42170

# Amount to send (in Ether)
amount_in_eth = float(input("Enter the amount of Ether to send: "))
amount_in_wei = web3.to_wei(amount_in_eth, 'ether')

# Read recipient addresses from CSV
recipient_addresses = []
with open('recipient_addresses.csv', 'r') as file:
    csv_reader = csv.reader(file)
    next(csv_reader)  # Skip header
    for row in csv_reader:
        recipient_addresses.append(row[0])

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
