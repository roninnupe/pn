import argparse
import random
import time
import pandas as pd
import json
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
from itertools import cycle

def read_addresses(file_path):
    with open(file_path, 'r') as f:
        return [line.strip().lower() for line in f]

def parse_arguments():
    parser = argparse.ArgumentParser(description='Script to move items. requires pn_collect_items_config.csv and referenced files')

    # Add the 'automate' argument
    parser.add_argument('--automate', action='store_true', help='Automate the process')

    return parser.parse_args()

def getItemABI():
    abi = [{
    "inputs": [
        {"internalType":"address","name":"from","type":"address"},
        {"internalType":"address","name":"to","type":"address"},
        {"internalType":"uint256[]","name":"ids","type":"uint256[]"},
        {"internalType":"uint256[]","name":"amounts","type":"uint256[]"},
        {"internalType":"bytes","name":"data","type":"bytes"}
    ],
    "name": "safeBatchTransferFrom",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
    }]
    
    return abi

def find_key_for_address(csv_file, target_address):
    df = pd.read_csv(csv_file)
    df['address_lower'] = df['address'].str.lower()  # Create a lowercase version of the 'address' column
    filtered_df = df[df['address_lower'] == target_address.lower()]
    
    if not filtered_df.empty:
        return filtered_df['key'].iloc[0]
    return None

def batch_transfer(web3, contract, recipient, operator, wallet_address, token_ids, amounts):
 
    try:
        # Build a transaction dictionary
        txn_dict = {
            'from': operator,
            'to': contract.address,
            'value': 0,
            'nonce': web3.eth.get_transaction_count(operator),
            'gasPrice': web3.eth.gas_price,
            'data': contract.encodeABI(fn_name='safeBatchTransferFrom', args=[wallet_address, recipient, token_ids, amounts, b''])
            }

        print(f"{token_ids}\n\n{amounts}\n\n")
        print(txn_dict)

        

        # Estimate the gas for this specific transaction
        txn_dict['gas'] = web3.eth.estimate_gas(txn_dict)

        print(f"Gas: {txn_dict['gas']}")

        # Sign the transaction using your private key
        private_key = find_key_for_address("addresses.csv", operator)
        signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)

        # Send the transaction
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print('Transaction hash:', txn_hash.hex())  # This will give you the transaction hash

        # Wait for the transaction to be mined, and get the transaction receipt
        txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

        print(f'Done sending from: {wallet_address} -to: {recipient}')
        print("--------------------------------")

    except Exception as e:
        print("  **Error with transaction:", e)


def main():
    args = parse_arguments()

    df_config = pd.read_csv('pn_collect_item_config.csv')
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
    selected_recipients = df_config.iloc[selected_index]['recipient_file']     
    selected_senders = df_config.iloc[selected_index]['sender_file']            

    # Load data from JSON
    with open('data_tokenId_items.json', 'r') as f:
        data = json.load(f)
        gameItems = data["data"]["gameItems"]
        # Convert list of dictionaries to a dictionary
        item_to_tokenId = {item["name"].lower(): int(item["tokenId"]) for item in gameItems}

    # Load data from CSV
    df = pd.read_csv('game_items.csv')
    # Strip whitespaces from column names
    df.columns = df.columns.str.strip()

    # Initialize web3. Replace the rpc_url with your own
    web3 = Web3(HTTPProvider('https://nova.arbitrum.io/rpc'))

    # Define the contract ABI for safeBatchTransferFrom method
    abi = getItemABI() 

    # Define contract address and contract
    contract_address = '0x3B4cdb27641bc76214a0cB6cae3560a468D9aD4A'
    contract = web3.eth.contract(address=contract_address, abi=abi)

    # Set the recipient address(es)    
    df_recipients = pd.read_csv(selected_recipients)
    recipients = df_recipients['address'].tolist()

    recipient_cycle = cycle(recipients)

    #grab the arg wlletfiles of senders
    df_senders = pd.read_csv(selected_senders)

    #specify a list of token_ids to not try and send. currently it's just soulbound tokens
    # note:81 is cutlass - skipping this for now
    skip_token_ids = [80,81,100,101,102]

    # Iterate over rows in the dataframe
    for index, row in df.iterrows():

        # grab the current wallet in the data to potentially be transferred
        current_wallet = row['wallet'].lower()

        #if the current wallet is not in the list of addresses to move, move on
        filtered_sender_df = df_senders[df_senders['address'].str.lower() == current_wallet]
        if filtered_sender_df.empty:
            continue

        #extract the sender wallet name for output to display to make sure you're sending from where you want to
        sender_wallet_name = filtered_sender_df['wallet_name'].iloc[0]
        
        #grab the recipeint for this cycle
        current_recipient = next(recipient_cycle).lower()

        #extract the recipient wallet name for output to display to make sure you know where you are sending to
        filtered_recipient_df = df_recipients[df_recipients['address'].str.lower() == current_recipient]        
        recipient_wallet_name = filtered_recipient_df['wallet_name'].iloc[0]

        recipient_address = to_checksum_address(current_recipient)
        wallet_address = to_checksum_address(current_wallet)  
        operator_address = to_checksum_address(selected_operator.lower())

        token_ids = []
        token_display = []
        amounts = []
        
        for item in row.index:
            item_lower = item.lower().strip()  # Convert to lower case and strip whitespace for case-insensitive comparison
            if item_lower in item_to_tokenId and pd.notna(row[item]):
                cellValue = int(row[item])
                if cellValue > 0:
                    token_id = item_to_tokenId[item_lower]
                    if(token_id in skip_token_ids) :
                        print(f"Skipping {cellValue} x {item}")
                    else:
                        token_ids.append(token_id)
                        amounts.append(cellValue)
                        token_display.append(item)
                        token_display.append(cellValue)
        if not token_ids or not amounts:
            print(f"No items found for wallet address: {sender_wallet_name} - {wallet_address}")
            continue
    
        if not args.automate :

            print(f"We are about to attempt to send items:\n\n{token_display}\n\n\tfrom: {sender_wallet_name} - {wallet_address}\n\n\tto: {recipient_wallet_name} - {recipient_address}\n\n")
            user_input = input("Do you want to proceed? (y/n -or optionally modify values with comma separated list):")
            if user_input.lower() == 'n':
                print("Skipping...")    
            else:
                if "," in user_input:
                    print(user_input)
                    parsed_user_input = user_input.split(',')
                    for i in range(0, len(parsed_user_input), 2):
                        item1 = parsed_user_input[i]
                        item2 = parsed_user_input[i+1] if i+1 < len(parsed_user_input) else None                        
                        try:
                            token_id = item_to_tokenId[item1.lower()]
                            revised_value = int(item2)
                            index_to_replace = token_ids.index(token_id)
                            if revised_value == 0:
                                token_ids.pop(index_to_replace)
                                amounts.pop(index_to_replace)
                                print(f"{item1} has been removed from send list")
                            elif revised_value <= amounts[index_to_replace] :
                                amounts[index_to_replace] = revised_value
                                print(f"{item1} has been modifed to {item2}")
                            else:
                                 print(f"{item1} has NOT been modified")
                            
                        except ValueError:
                            print(f"{item1} is not found in the list")
                    print("Press Enter to Continue...")
                    input()
                
                batch_transfer(web3, contract, recipient_address, operator_address, wallet_address, token_ids, amounts)
        else:
            batch_transfer(web3, contract, recipient_address, operator_address, wallet_address, token_ids, amounts)
    
            delay_seconds = random.uniform(15.0, 35.0)
            print(f"Waiting for {delay_seconds:.2f} seconds...")            
            time.sleep(delay_seconds)


if __name__ == "__main__":
    main()    