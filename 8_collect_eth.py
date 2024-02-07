import pandas as pd
import pn_helper as pn
from termcolor import colored

GAS_LIMIT = 50000

sender_range_input = input("Input the wallets you'd like to collect eth from from: ")
walletlist = pn.parse_number_ranges(sender_range_input)
sender_data = pn.get_full_wallet_data(walletlist)

# Get the recipient address from the file (will default with no input if only one recipient in file)
recipient_range_input = input("Input the wallet you'd like to collect eth to: ")
walletlist = pn.parse_number_ranges(recipient_range_input)
recipient_data = pn.get_full_wallet_data(walletlist)

if not recipient_data.empty:
    recipient_addr = recipient_data.iloc[0]['address']
    identifier = recipient_data.iloc[0]['identifier']
else:
    # Handle the case when sender_data is empty (no rows found)
    print("No data found for the specified range.")

print(f"About to collect eth from wallets {sender_range_input} and send to {identifier} - {recipient_addr}")
user_input = input("Do you want to proceed? (y/n): ").strip().lower()
if user_input != "y": 
    if user_input != "n": print("Terminating script. You must explicitly enter y to proceed")
    else: print("Okay, no Eth will be collected! Have a great day")
    exit()

total_sent_eth = 0
total_gas_cost_eth = 0

for index, row in sender_data.iterrows():
    sender_name = row['identifier']
    sender_address = row['address']
    sender_pk = row['key']
    amount_in_eth, weth = pn.get_nova_eth_balance(sender_address)
    total_sent_eth += amount_in_eth

    # Estimate gas cost; you'll have to adjust this if your send_nova_eth function returns the actual gas cost
    gas_price = pn.Web3Singleton.get_web3_Nova().eth.gas_price
    gas_cost_in_eth = (gas_price * GAS_LIMIT) / 1e18
    total_gas_cost_eth += gas_cost_in_eth

    if (amount_in_eth > 0.00001):
        if (sender_address == recipient_addr): continue  # Skip sending money to yourself
        print(colored("---------------------------------------------------", 'cyan'))
        print(colored(f"Initiating Transaction", 'cyan'))
        print(colored(f"From Address: {sender_address}", 'white', attrs=['bold']))
        print(colored(f"To Address  : {recipient_addr}", 'white', attrs=['bold']))
        print(colored(f"Amount      : {amount_in_eth:.18f} ETH", 'white', 'on_grey'))
        print(colored(f"Gas Cost    : {gas_cost_in_eth:.18f} ETH", 'white'))
        pn.send_nova_eth(sender_address, recipient_addr, amount_in_eth, sender_pk, GAS_LIMIT, True)
        print(colored("---------------------------------------------------", 'cyan'))
        print()  # Empty line for clarity

# Calculate dollar values
total_dollar_value = pn.eth_to_usd(total_sent_eth)
total_gas_cost_dollar_value = pn.eth_to_usd(total_gas_cost_eth)

print("\n" + colored("=== Summary ===", 'yellow'))
print(colored(f"Total ETH Sent: {total_sent_eth:.18f} ETH (${pn.eth_to_usd(total_sent_eth)} USD)", 'green'))
print(colored(f"Total Gas Cost: {total_gas_cost_eth:.18f} ETH (${total_gas_cost_dollar_value} USD)", 'red'))
print(colored(f"Consolidated Value at Recipient: ${total_dollar_value} USD", 'blue'))