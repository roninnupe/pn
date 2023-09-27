import time
import pandas as pd
import pn_helper as pn
import pandas as pd
from termcolor import colored

GAS_LIMIT = 50000

# Get the sender address from the file (will default with no input if only one sender in file)
sender_choice_file = pn.data_path("addresses_with_pk_3.csv")
sender_data = pn.select_wallet(sender_choice_file)
sender_addr = sender_data['address']
sender_key = sender_data['key']

# Load up the recipient addresses
file_path = pn.data_path("addresses_with_pk_3.csv")
df = pd.read_csv(file_path)
recipient_addresses = df['address'].tolist()
recipient_count = len(recipient_addresses)

# Get sender eth_balance and USD estimate of the wallet sending
sender_eth_balance = pn.get_nova_eth_balance(sender_addr)
sender_nova_usd_estimate = pn.eth_to_usd(sender_eth_balance)

# Amount to send (in Ether)
print(f"You have {sender_eth_balance} eth (~${sender_nova_usd_estimate} USD)")
user_input = input(f"\tenter the amount of USD (or EQUAL) to send to {recipient_count} wallets: $")
if user_input.upper() == "EQUAL" :
    amount_in_eth = (sender_eth_balance / (recipient_count + 1 ))
    amount_in_USD = pn.eth_to_usd(amount_in_eth)
    subtract_gas = True
else:
    amount_in_USD = float(user_input)
    amount_in_eth = pn.usd_to_eth(amount_in_USD)
    subtract_gas = False

print(f"About to distribute {amount_in_eth} (${amount_in_USD}) x {recipient_count} = {amount_in_eth * recipient_count} with a Gas Limit of {GAS_LIMIT}")
user_input = input("Do you want to proceed? (y/n): ").strip().lower()
if user_input != "y": 
    if user_input != "n": print("Terminating script. You must explicitly enter y to proceed")
    else: print("Okay, no Eth will be sent! Have a great day")
    exit()

total_sent_eth = 0
total_gas_cost_eth = 0

# Main loop to send transactions
for recipient in recipient_addresses:
    # Estimate gas cost; you'll have to adjust this if your send_nova_eth function returns the actual gas cost
    gas_price = pn.Web3Singleton.get_web3_Nova().eth.gas_price
    gas_cost_in_eth = (gas_price * GAS_LIMIT) / 1e18
    total_gas_cost_eth += gas_cost_in_eth

    pn.send_nova_eth(sender_addr, recipient, amount_in_eth, sender_key, GAS_LIMIT, subtract_gas)
    total_sent_eth += amount_in_eth

    # Delay to allow the network to update the nonce
    time.sleep(1)

# Convert totals to readable formats
total_sent_eth = total_sent_eth
total_dollar_value_sent = pn.eth_to_usd(float(total_sent_eth))
total_dollar_value_gas = pn.eth_to_usd(float(total_gas_cost_eth))

# Summary
print(colored("\nSummary:", 'yellow', attrs=['bold']))
print(colored("---------------------------------------------------", 'yellow'))
print(colored(f"Total ETH Sent: {total_sent_eth:.18f} ETH (${total_dollar_value_sent} USD)", 'green', attrs=['bold']))
print(colored(f"Total Gas Cost: {total_gas_cost_eth:.18f} ETH (${total_dollar_value_gas} USD)", 'red'))
print(colored("---------------------------------------------------", 'yellow'))