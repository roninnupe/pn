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

    return parser.parse_args()

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

def get_name_by_token_id(token_id, game_items):
    # Iterate through gameItems to find the item with the given tokenId
    for item in game_items:
        if int(item["tokenId"]) == token_id:
            return item["name"]
    # Return None if tokenId is not found
    return None

def parse_input(input_str, gameItems, item_to_tokenId):
    while True:
        user_input = input(input_str)
        parts = user_input.split(',')
        item_ids = []
        item_quantities = []
        item_names = []

        valid_input = True

        for part in parts:
            item_info = part.split(':')
            if len(item_info) == 2:
                item_id, quantity = item_info
                item_id = item_id.strip()
                quantity = quantity.strip()
                if item_id.isdigit():
                    # If item_id is a digit, treat it as a tokenId
                    item_ids.append(int(item_id))
                    item_names.append(get_name_by_token_id(int(item_id), gameItems))
                else:
                    # If item_id is not a digit, treat it as an item name and look up the tokenId
                    item_name = item_id.lower()
                    if item_name in item_to_tokenId:
                        item_ids.append(item_to_tokenId[item_name])
                        item_names.append(item_name)
                    else:
                        valid_input = False
                        break
                item_quantities.append(int(quantity))
            else:
                valid_input = False
                break

        if valid_input:
            return item_ids, item_quantities, item_names
        else:
            print("Invalid input format. Please enter in the format itemId:quantity,itemId:quantity, or itemId.")


def main():
    args = parse_arguments()

    sender_range_input = input("Input the wallet you'd like to send items from from: ")
    walletlist = pn.parse_number_ranges(sender_range_input)
    selected_senders = pn.get_full_wallet_data(walletlist)

    if not selected_senders.empty:
        sender_addr = to_checksum_address(selected_senders.iloc[0]['address'])
        identifier = selected_senders.iloc[0]['identifier']
        private_key =  selected_senders.iloc[0]['key']   

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

    # Example usage:
    item_ids, item_quantities, item_names = parse_input("Enter a comma-separated list of itemId:quantity,itemId:quantity: ", gameItems, item_to_tokenId)
    print("Item IDs:", item_ids)
    print("Item Quantities:", item_quantities)
    print("Item Names:", item_names)


    # Initialize web3 and contract
    web3 = pn.Web3Singleton.get_web3_Nova()
    game_items_contract = pn.Web3Singleton.get_GameItems()

    #specify a list of token_ids to not try and send. currently it's just soulbound tokens
    # note:81 is cutlass - skipping this for now
    skip_token_ids = soulbound_tokenIds #[80,100,101,102,209,210,211,212,213,214,215,216,217,218,219,220,221,222]

    for index, row in selected_recipients.iterrows():

        recipient_address = to_checksum_address(row['address'])

        print(f"Sending from {identifier} to {row['identifier']}")
        print_token_amount_pairs(item_names, item_quantities)

        batch_transfer(web3, game_items_contract, recipient_address, sender_addr, private_key, sender_addr, item_ids, item_quantities)
        time.sleep(1)

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