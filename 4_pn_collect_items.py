import argparse
import random
import time
import pandas as pd
import json
from web3 import Web3, HTTPProvider
from eth_utils import to_checksum_address
from itertools import cycle
import pn_helper as pn

def parse_arguments():
    parser = argparse.ArgumentParser(description='Script to move items. requires pn_collect_items_config.csv and referenced files')

    # Add the 'automate' argument
    parser.add_argument('--automate', action='store_true', help='Automate the process')

    parser.add_argument("--itemIds", type=str, default=None, help="Specify the itemIds you'd like to move (default: None)") 

    return parser.parse_args()

#batch_transfer(web3, game_items_contract, recipient_address, operator_address, private_key, wallet_address, token_ids, amounts)
def batch_transfer(web3, contract, recipient, operator, private_key, wallet_address, token_ids, amounts):
 
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

        #print(f"\ntokenIds:{token_ids}\nquantity:{amounts}\n")

        # Estimate the gas for this specific transaction
        txn_dict['gas'] = web3.eth.estimate_gas(txn_dict)

        print(f"Gas: {txn_dict['gas']}")

        # Sign the transaction using your private key
        signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)

        # Send the transaction
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print('Transaction hash:', txn_hash.hex())  # This will give you the transaction hash

        # Wait for the transaction to be mined, and get the transaction receipt
        txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

        print(f'{pn.C_GREEN}Done sending{pn.C_END} from: {wallet_address} -to: {recipient}')
        print(f"{pn.C_BLUE}-------------------------------------------------------------------{pn.C_END}")

    except Exception as e:
        print(f"  {pn.C_RED}**Error with transaction: {e}{pn.C_END}")


def main():
    args = parse_arguments()

    sender_range_input = input("Input the wallets you'd like to collect items from from: ")
    walletlist = pn.parse_number_ranges(sender_range_input)
    selected_senders = pn.get_full_wallet_data(walletlist)

    # Get the recipient address from the file (will default with no input if only one recipient in file)
    recipient_range_input = input("Input the wallets you'd like to send items to: ")
    walletlist = pn.parse_number_ranges(recipient_range_input)
    selected_recipients = pn.get_full_wallet_data(walletlist)

    # Load data from the fetch_game_items_data function
    gameItems = pn.fetch_game_items_data()

    # Initialize dictionaries to store item_to_tokenId and soulbound_tokenIds
    item_to_tokenId = {}
    soulbound_tokenIds = []

    # Iterate through the gameItems and check the traits
    for item in gameItems:

        item_name = item["name"].lower()
        token_id = int(item["tokenId"])
        traits = item.get("traits", [])

        # Check for the soulbound trait and add to soulbound_tokenIds if true
        soulbound_trait = any(
            trait.get("metadata", {}).get("name") == "soulbound" and trait.get("value") == "true"
            for trait in traits
        )
        if soulbound_trait:
            soulbound_tokenIds.append(token_id)

        # Store item_name and token_id in item_to_tokenId
        item_to_tokenId[item_name] = token_id

    # Load data from CSV
    df = pd.read_csv(pn.data_path("game_items.csv"))
    # Strip whitespaces from column names
    df.columns = df.columns.str.strip()

    # Initialize web3 and contract
    web3 = pn.Web3Singleton.get_web3_Nova()
    game_items_contract = pn.Web3Singleton.get_GameItems()

    # Set the recipient address(es) LFG    
    recipients = selected_recipients['address'].tolist()

    recipient_cycle = cycle(recipients)

    #grab the arg wlletfiles of senders
    df_senders = selected_senders

    #specify a list of token_ids to not try and send. currently it's just soulbound tokens
    # note:81 is cutlass - skipping this for now
    skip_token_ids = soulbound_tokenIds #[80,100,101,102,209,210,211,212,213,214,215,216,217,218,219,220,221,222]

    # extract out a list of only the token Ids you want to send
    include_only_token_ids = None
    if args.itemIds:
        include_only_token_ids = [int(token_id) for token_id in args.itemIds.split(',')]

    # Iterate over rows in the dataframe
    for index, row in df.iterrows():

        # grab the current wallet in the data to potentially be transferred
        current_wallet = row['wallet'].lower()

        #if the current wallet is not in the list of addresses to move, move on
        filtered_sender_df = df_senders[df_senders['address'].str.lower() == current_wallet]
        if filtered_sender_df.empty:
            continue

        #extract the sender wallet name for output to display to make sure you're sending from where you want to
        sender_wallet_name = filtered_sender_df['identifier'].iloc[0]
        private_key = filtered_sender_df['key'].iloc[0]      
        
        #grab the recipeint for this cycle
        current_recipient = next(recipient_cycle).lower()

        #extract the recipient wallet name for output to display to make sure you know where you are sending to
        filtered_recipient_df = selected_recipients[selected_recipients['address'].str.lower() == current_recipient]        
        recipient_wallet_name = filtered_recipient_df['identifier'].iloc[0]

        recipient_address = to_checksum_address(current_recipient)
        wallet_address = to_checksum_address(current_wallet)  
        operator_address = wallet_address #to_checksum_address(selected_operator.lower())
        #private_key = pn.find_key_for_address(operator_address)

        token_ids = []
        token_name = []
        amounts = []
        
        for item in row.index:
            item_lower = item.lower().strip()  # Convert to lower case and strip whitespace for case-insensitive comparison
            if item_lower in item_to_tokenId and pd.notna(row[item]):
                cellValue = int(row[item])
                if cellValue > 0:
                    token_id = item_to_tokenId[item_lower]
                    if(token_id in skip_token_ids) or (include_only_token_ids is not None and token_id not in include_only_token_ids):
                        print(f"Skipping {cellValue} x {item}")              
                    else:
                        token_ids.append(token_id)
                        amounts.append(cellValue)
                        token_name.append(item)

        if not token_ids or not amounts:
            print(f"No items found for wallet address: {sender_wallet_name} - {wallet_address}")
            continue
    
        if not args.automate :
            skip_transfer = False  # Initialize a flag to determine if the transfer should be skipped

            while True:
                # beginning
                print(f"{pn.C_CYAN}We are about to attempt to send{pn.C_END}:\n")
                print_token_amount_pairs(token_name, amounts)
                print(f"\nfrom: {sender_wallet_name} - {wallet_address}\nto: {recipient_wallet_name} - {recipient_address}\n")
                print(f"{pn.C_YELLOW}Press {pn.C_CYAN}enter{pn.C_END}{pn.C_YELLOW} to proceed{pn.C_END}")
                print(f"   Press {pn.C_CYAN}s{pn.C_END} to skip")
                print(f"   Press {pn.C_CYAN}x{pn.C_END} to exit")
                print(f"   OR modify values with commas separated list (example: {pn.C_CYAN}Wood,3,Iron Ore,5{pn.C_END})")
                user_input = input("   :")
                if user_input.lower() == 's':
                    print("Skipping...")
                    skip_transfer = True
                    break
                if user_input.lower() == 'x':
                    exit() 
                if user_input == "":
                    break   
                else:
                    if "," in user_input:
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
                                    token_name.pop(index_to_replace)
                                    amounts.pop(index_to_replace)
                                    print(f"\n  {pn.C_MAGENTA}x{item1} has been removed from send list{pn.C_END}\n")
                                elif revised_value <= amounts[index_to_replace] :
                                    amounts[index_to_replace] = revised_value
                                    print(f"\n  {pn.C_GREEN}{item1} has been modifed to {item2}{pn.C_GREEN}\n")
                                else:
                                    print(f"\n  {pn.C_RED}{item1} has NOT been modified{pn.C_RED}\n")
                            
                            except ValueError:
                                print(f"\n   {pn.C_RED}{item1} is not found in the list{pn.C_END}\n")
                    else:
                        print(f"\n{pn.C_RED}   Invalid input, try again.{pn.C_END}\n")
                        #go back to beginning with revised amounts

            if not skip_transfer:    
                batch_transfer(web3, game_items_contract, recipient_address, operator_address, private_key, wallet_address, token_ids, amounts)
        else:
            print(f"{pn.C_BLUE}-------------------------------------------------------------------{pn.C_END}")
            print(f"{pn.C_CYAN}Sending{pn.C_END} from: {sender_wallet_name} - {wallet_address}")
            print(f"          to: {recipient_wallet_name} - {recipient_address}\n")
            print_token_amount_pairs(token_name, amounts)
            print("")

            batch_transfer(web3, game_items_contract, recipient_address, operator_address, private_key, wallet_address, token_ids, amounts)
    
            delay_seconds = random.uniform(0.25, 1.25)
            print(f"Waiting for {delay_seconds:.2f} seconds...")            
            time.sleep(delay_seconds)

def print_token_amount_pairs(token_name, amounts):
    if len(token_name) != len(amounts):
        print("Error: Both lists must be of equal length")
        return

    max_token_length = max(len(name) for name in token_name)
    
    print(f"{'Token Name':<{max_token_length + 5}}Amount")
    print("-" * (max_token_length + 5 + 10))
    
    for i in range(len(token_name)):
        print(f"{token_name[i]:<{max_token_length + 5}}{amounts[i]}")

if __name__ == "__main__":
    main()    