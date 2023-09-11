from itertools import cycle
import random
import argparse
import time
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address

def parse_arguments():
    parser = argparse.ArgumentParser(description='Move PGLD from a list of wallets found in the sender_csv to the receiver_address. Optionally specify an operator which is a wallet authorized to move the gold, otherwise it will assume the reciever_address is the operator. You may also specify a range (leaveBehindMin and leaveBehindMax) to leave behind a random amount of gold between those two values.')

    # Optional argument: min_move (default: 1000)
    parser.add_argument('--min_move', type=int, default=1000, help='Minimum PGLD move amount. will not move if the value to move is less than this (default: 1000)')

    # Optional argument: leave_behind_mib (default: 2500)
    parser.add_argument('--leave_behind_min', type=int, default=2500, help='Minimum amount of gold to leave behind (optional, default: 2500)')

    # Optional argument: leave_behind_max (default: 3000)
    parser.add_argument('--leave_behind_max', type=int, default=3000, help='Maximum amount of gold to leave behind (optional, default: 3000)')

    # Add the 'automate' argument
    parser.add_argument('--automate', action='store_true', help='Automate the process')

    return parser.parse_args()

def make_query(address):
    return f"""
    {{
      accounts(where: {{address: "{address}"}}){{
        address
        currencies{{
            amount
        }}
      }}
    }}
    """

def main():
    args = parse_arguments()

    df_config = pd.read_csv(pn.data_path("pn_collect_item_config.csv"))
    pn.load_address_key_mapping(pn.data_path("addresses.csv"))

    print("Available operators:")
    for index, row in df_config.iterrows():
        print(f"{index + 1}. {row['name']} - {row['operator_address']}")   
    
    # Get user input for the bounty they are interested in
    selected_index = int(input("Please enter the number corresponding to the bounty you're interested in: ")) - 1

    # Validate user input
    if selected_index < 0 or selected_index >= len(df_config):
        print("Invalid selection. Exiting.")
        exit()    

     # Find the corresponding hex value for the selected bounty_name
    selected_operator = df_config.iloc[selected_index]['operator_address']
    selected_recipients = pn.data_path(df_config.iloc[selected_index]['recipient_file'])     
    selected_senders = pn.data_path(df_config.iloc[selected_index]['sender_file'])         

    leave_behind_min = args.leave_behind_min
    leave_behind_max = args.leave_behind_max

    #PGLD is shown in a long uint256 form and we use this to manuever between human readable display form and code form
    X_PGLD_LONG = 10**18
    min_move = args.min_move * X_PGLD_LONG

    # Now you can use these variables in your script as needed.
    print("Operator Address:", selected_operator)   
    print("Receiver CSV File:", selected_recipients)
    print("Sender CSV File:", selected_senders)
    print("Leave Behind Min:", leave_behind_min)
    print("Leave Behind Max:", leave_behind_max)
    print("Min Move Amount:", args.min_move)
    print("----------------------------------------------------------------------------------------------------------------------------------------")
    
    #grab the arg wlletfiles of senders
    df_senders = pd.read_csv(selected_senders)

     # Set the recipient address(es)    
    df_recipients = pd.read_csv(selected_recipients)
    recipients = df_recipients['address'].tolist()

    recipient_cycle = cycle(recipients)   

    # Initialize web3 stuff
    url = pn.URL_PIRATE_NATION_GRAPH_API   
    web3 = pn.web3_Nova
    contract = pn.contract_PGLDToken


    for index, row in df_senders.iterrows():

        # grab the current wallet in the data to potentially be transferred
        wallet_name = row['wallet_name']
        address = row['address'].lower()

        query = make_query(address)
        json_data = pn.get_data(query)
        
        for account in json_data['data']['accounts']:      
            
            print(json_data)
            # Set PGLD value
            pgld = 0

            if 'currencies' in account and len(account['currencies']) > 0:
                pgld = int(account['currencies'][0]['amount'])
                print(f"{wallet_name} - We found {pgld / X_PGLD_LONG} gold.")

                #generate a random amount of gold to leave behind and adjust pgld to move
                if leave_behind_max > 0:
                    leave_behind = random.randint(leave_behind_min, leave_behind_max) * X_PGLD_LONG
                    pgld = pgld - leave_behind
                    print(f"We plan to try to leave behind at least {leave_behind / X_PGLD_LONG} gold.")

                #we must have a positve value for PGLD to try to leaveBehind
                if pgld >= min_move:

                    #grab the recipeint for this cycle
                    current_recipient = next(recipient_cycle)

                    print(f"We plan to move {pgld / X_PGLD_LONG} gold to: {current_recipient}")
                    if args.automate:
                        transfer_PGLD(web3, contract, current_recipient, selected_operator, address, pgld)
                        random_delay = random.uniform(4.5, 32.5)
                        print(f"\n\n...sleeping for {random_delay} seconds...\n\n")
                        time.sleep(random_delay)

                    else:
                        user_input = input("Do you want to proceed? (y/n): ")
                        if user_input.lower() == 'n':
                            print("Skipping...")
                        else:
                            transfer_PGLD(web3, contract, current_recipient, selected_operator, address, pgld)                
                else:
                    print("No gold to move")
                    print("----------------------------------------------------------------------------------------------------------------------------------------")                    

def transfer_PGLD(web3, contract, recipient, operator, sender, pgld_amount):

    operator_address = to_checksum_address(operator.lower())
    wallet_address = to_checksum_address(sender.lower())
    recipient_address = to_checksum_address(recipient.lower())

    # Build a transaction dictionary
    txn_dict = {
        'from': operator_address,
        'to': contract.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(operator_address),
        'gasPrice': web3.eth.gas_price,
        'data': contract.encodeABI(fn_name='transferFrom', args=[wallet_address, recipient_address, pgld_amount])
        } 
                    
    # Estimate the gas for this specific transaction
    txn_dict['gas'] = web3.eth.estimate_gas(txn_dict)
                    
    # Sign the transaction using your private key
    private_key = pn.find_key_for_address(operator)
    signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)
                    
    # Send the transaction
    txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print('Transaction hash:', txn_hash.hex())  # This will give you the transaction hash
                    
    # Wait for the transaction to be mined, and get the transaction receipt
    txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)
                    
    print(f"Transfer completed from {sender} to {recipient}")
    print("----------------------------------------------------------------------------------------------------------------------------------------")            

if __name__ == "__main__":
    main()    
