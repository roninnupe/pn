import argparse
import re
import traceback
import time
import pandas as pd
from web3 import Web3
from eth_utils import to_checksum_address
import pn_helper as pn

def parse_arguments():
    parser = argparse.ArgumentParser(description='Script to move items')

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

        txn_receipt = pn.send_web3_transaction(web3, private_key, txn_dict, max_transaction_cost_usd=0.06, retries=0)

        if txn_receipt is not None:
            status_message = pn.get_status_message(txn_receipt)
            txn_hex = txn_receipt.transactionHash.hex()
            print(f'{status_message}: {txn_hex}')
            print(f'{pn.C_GREEN}Done sending{pn.C_END} from: {wallet_address} -to: {recipient}')
            print(f"{pn.C_BLUE}-------------------------------------------------------------------{pn.C_END}")

        else:
            # Handle the case where txn_receipt is None
            print("Transaction failed or was not sent")

    except ValueError as ve:
        # Handle ValueError specifically without printing traceback
        print(f"  {pn.C_RED}**Error with transaction: {ve}{pn.C_END}")
        
    except Exception as e:
        traceback.print_exc()  # This prints the traceback
        print(f"  {pn.C_RED}**Error with transaction: {type(e).__name__} {e}{pn.C_END}")


def get_name_by_token_id(token_id, game_items):
    # Iterate through game_items to find the item with the given tokenId
    for element in game_items:
        world_entity = element.get("worldEntity", {})
        game_item = world_entity.get("gameItem", {})
        if int(game_item.get("tokenId", 0)) == token_id:
            return world_entity.get("name")  # Return the name from worldEntity
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

    sender_range_input = input("Input the wallet you'd like to send items from: ")
    walletlist = pn.parse_number_ranges(sender_range_input)
    selected_senders = pn.get_full_wallet_data(walletlist)

    if not selected_senders.empty:
        sender_addr = pn.to_web3_address(selected_senders.iloc[0]['address'])
        identifier = selected_senders.iloc[0]['identifier']
        private_key = selected_senders.iloc[0]['key']

    # Get the recipient address from the input
    destination_input = input("Input the wallets (or address) you'd like to send items to: ")

    eth_address_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
    if eth_address_pattern.match(destination_input):
        # If input matches Ethereum address pattern, use it as both recipient address and identifier
        recipient_address = pn.to_web3_address(destination_input)
        selected_recipients = pd.DataFrame([{'address': recipient_address, 'identifier': recipient_address}])
    else:
        # Process the input as wallet ranges if it doesn't match an Ethereum address pattern
        walletlist = pn.parse_number_ranges(destination_input)
        selected_recipients = pn.get_full_wallet_data(walletlist)

    # Load data from the fetch_game_items_data function
    gameItems = pn.fetch_game_items_data()

    # Initialize dictionaries to store item_to_tokenId and soulbound_tokenIds
    item_to_tokenId, soulbound_tokenIds = pn.get_token_id_mapping_and_soulbound_list(gameItems)

    # Parse user input for items to send
    item_ids, item_quantities, item_names = parse_input("Enter a comma-separated list of itemId:quantity,itemId:quantity: ", gameItems, item_to_tokenId)
    print("Item IDs:", item_ids)
    print("Item Quantities:", item_quantities)
    print("Item Names:", item_names)

    # Initialize web3 and contract
    web3 = pn.Web3Singleton.get_web3_Apex()
    game_items_contract = pn.Web3Singleton.get_GameItems()

    for index, row in selected_recipients.iterrows():
        recipient_address = pn.to_web3_address(row['address'])
        recipient_identifier = row['identifier']  # Now you also have an identifier for each recipient

        print(f"Sending from {identifier} ({sender_addr}) to {recipient_identifier}")
        print_token_amount_pairs(item_names, item_quantities)

        # Function call to perform the batch transfer, assuming it's defined elsewhere
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