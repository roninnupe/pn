import pandas as pd
import pn_helper as pn
from termcolor import colored

# Get the recipient address from the file (will default with no input if only one recipient in file)
recipient_choice_file = pn.data_path("addresses.csv")
recipient_data = pn.select_wallet(recipient_choice_file)
recipient_addr = recipient_data['address']

# get the collection addresses from the file
collection_addresses_file = pn.data_path("addresses.csv")
df = pd.read_csv(collection_addresses_file)

total_sent_eth = 0
total_gas_cost_eth = 0

input()

for index, row in df.iterrows():
    sender_name = row['wallet']
    sender_address = row['address']
    sender_pk = row['key']
    amount_in_eth = pn.get_nova_eth_balance(sender_address)
    total_sent_eth += amount_in_eth

    # Estimate gas cost; you'll have to adjust this if your send_nova_eth function returns the actual gas cost
    gas_price = pn.Web3Singleton.get_web3_Nova().eth.gas_price
    gas_limit = 40000
    gas_cost_in_eth = (gas_price * gas_limit) / 1e18
    total_gas_cost_eth += gas_cost_in_eth

    if (amount_in_eth > 0.00001):
        if (sender_address == recipient_addr): continue  # Skip sending money to yourself
        print(colored("---------------------------------------------------", 'cyan'))
        print(colored(f"Initiating Transaction", 'cyan'))
        print(colored(f"From Address: {sender_address}", 'white', attrs=['bold']))
        print(colored(f"To Address  : {recipient_addr}", 'white', attrs=['bold']))
        print(colored(f"Amount      : {amount_in_eth:.18f} ETH", 'white', 'on_grey'))
        print(colored(f"Gas Cost    : {gas_cost_in_eth:.18f} ETH", 'white'))
        pn.send_nova_eth(sender_address, recipient_addr, amount_in_eth, sender_pk, gas_limit, True)
        print(colored("---------------------------------------------------", 'cyan'))
        print()  # Empty line for clarity

# Calculate dollar values
total_dollar_value = pn.eth_to_usd(total_sent_eth)
total_gas_cost_dollar_value = pn.eth_to_usd(total_gas_cost_eth)

print("\n" + colored("=== Summary ===", 'yellow'))
print(colored(f"Total ETH Sent: {total_sent_eth:.18f} ETH (${pn.eth_to_usd(total_sent_eth)} USD)", 'green'))
print(colored(f"Total Gas Cost: {total_gas_cost_eth:.18f} ETH (${total_gas_cost_dollar_value} USD)", 'red'))
print(colored(f"Consolidated Value at Recipient: ${total_dollar_value} USD", 'blue'))