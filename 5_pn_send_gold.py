from itertools import cycle
import random
import argparse
import time
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address

def parse_arguments():
    parser = argparse.ArgumentParser(description='Move PGLD from a list of wallets found in the sender_csv to the receiver_address. Optionally specify an operator which is a wallet authorized to move the gold, otherwise it will assume the receiver_address is the operator. You may also specify a range (leaveBehindMin and leaveBehindMax) to leave behind a random amount of gold between those two values.')

    parser.add_argument('--min', type=int, default=100, help='Minimum amount of gold to leave behind (optional, default: 100)')
    parser.add_argument('--max', type=int, default=1000, help='Maximum amount of gold to leave behind (optional, default: 1000)')
    parser.add_argument('--automate', action='store_true', help='Automate the process')

    return parser.parse_args()

def main():
    args = parse_arguments()

    sender_range_input = input("Input the wallets you'd like to send items from: ")
    walletlist = pn.parse_number_ranges(sender_range_input)
    selected_senders = pn.get_full_wallet_data(walletlist)
    sender_cycle = cycle(selected_senders.iterrows())

    file_path = pn.select_file(directory_path="addresses/", prefix="addresses_", file_extension=".txt")
    recipients = pn.read_addresses(file_path)

    min_move = args.min
    max_move = args.max

    print("min_move:", min_move)
    print("max_move", max_move)
    print(f"{pn.C_GREEN}----------------------------------------------------------------------------------------------------------------------------------------{pn.C_END}")

    X_PGLD_LONG = 10**18
    min_move = min_move * X_PGLD_LONG
    max_move = max_move * X_PGLD_LONG

    # Initialize web3 stuff
    web3 = pn.Web3Singleton.get_web3_Apex()
    PGLD_contract = pn.Web3Singleton.get_PGLDToken()

    for current_recipient in recipients:
        index, row = next(sender_cycle)

        wallet_name = row['identifier']
        sender_address = row['address'].lower()
        private_key = row['key']

        PGLD_to_move = random.randint(min_move, max_move)

        # Round PGLD_to_move to the nearest whole number
        PGLD_to_move = round(PGLD_to_move / X_PGLD_LONG) * X_PGLD_LONG

        print(f"\n   We plan to{pn.C_GREEN} TRANSFER{pn.C_YELLOW} {PGLD_to_move / X_PGLD_LONG} gold{pn.C_END} to: {current_recipient}\n")
        if args.automate:
            transfer_PGLD(web3, PGLD_contract, sender_address, private_key, current_recipient, PGLD_to_move)
            random_delay = random.uniform(0.5, 1.0)
            print(f"\n\n...sleeping for {random_delay} seconds...\n\n")
            time.sleep(random_delay)
        else:
            user_input = input(f"Press {pn.C_GREEN}'enter'{pn.C_END} to proceed or {pn.C_RED}'s'{pn.C_END} to skip: ")
            if user_input.lower() == 's':
                print("Skipping...")
            else:
                transfer_PGLD(web3, PGLD_contract, sender_address, private_key, current_recipient, PGLD_to_move)

def transfer_PGLD(web3, contract, sender, private_key, recipient, pgld_amount):
    sender_address = to_checksum_address(sender.lower())
    recipient_address = to_checksum_address(recipient.lower())

    latest_block = web3.eth.get_block('latest')
    base_fee = latest_block['baseFeePerGas']
    max_priority_fee = web3.to_wei(2, 'gwei')

    max_fee = base_fee + max_priority_fee

    txn_dict = {
        'from': sender_address,
        'to': contract.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(sender_address),
        'maxPriorityFeePerGas': max_priority_fee,
        'maxFeePerGas': max_fee,
        'data': contract.encodeABI(fn_name='transfer', args=[recipient_address, pgld_amount]),
        'chainId': web3.eth.chain_id
    }

    try:
        txn_dict['gas'] = web3.eth.estimate_gas(txn_dict)
        signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print('Transaction hash:', txn_hash.hex())
        txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)
        print(f"Transfer completed from {sender} to {recipient}")

    except Exception as e:
        print("  **Error with transferring PGLD transaction:", e)

    print("----------------------------------------------------------------------------------------------------------------------------------------")

if __name__ == "__main__":
    main()