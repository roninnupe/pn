from itertools import cycle
import random
import argparse
import time
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address

_currency_dict = {}

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


def main():

    global _currency_dict

    args = parse_arguments()

    sender_range_input = input("Input the wallets you'd like to collect items from from: ")
    walletlist = pn.parse_number_ranges(sender_range_input)
    selected_senders = pn.get_full_wallet_data(walletlist)

    # Get the recipient address from the file (will default with no input if only one recipient in file)
    recipient_range_input = input("Input the wallets you'd like to send items to: ")
    walletlist = pn.parse_number_ranges(recipient_range_input)
    selected_recipients = pn.get_full_wallet_data(walletlist)

    leave_behind_min = args.leave_behind_min
    leave_behind_max = args.leave_behind_max

    #PGLD is shown in a long uint256 form and we use this to manuever between human readable display form and code form
    X_PGLD_LONG = 10**18
    min_move = args.min_move * X_PGLD_LONG

    # Now you can use these variables in your script as needed.
    print("Leave Behind Min:", leave_behind_min)
    print("Leave Behind Max:", leave_behind_max)
    print("Min Move Amount:", args.min_move)
    print(f"{pn.C_GREEN}----------------------------------------------------------------------------------------------------------------------------------------{pn.C_END}")
    
    # get the data frame of senders
    df_senders = selected_senders
    # get the addresses list of those senders to pull the currency values in one shot
    addresses_list = df_senders['address'].tolist()    
    _currency_dict = pn.get_currency_dictionary(addresses_list)
    
     # Set the recipient address(es)    
    recipients = selected_recipients['address'].tolist()

    recipient_cycle = cycle(recipients)   

    # Initialize web3 stuff
    web3 = pn.Web3Singleton.get_web3_Apex()
    PGLD_contract = pn.Web3Singleton.get_PGLDToken()

    for index, row in df_senders.iterrows():

        # grab the current wallet in the data to potentially be transferred
        wallet_name = row['identifier']
        sender_address = row['address'].lower()
        private_key = row['key']

        # Pull the initial PGLD out of the dictionary
        PGLD_initial = int(_currency_dict.get(sender_address))

        if PGLD_initial > 0:
            
            PGLD_to_move = PGLD_initial

            #generate a random amount of gold to leave behind and adjust pgld to move
            leave_behind = 0.0000001
            if leave_behind_max > 0:
                leave_behind = random.randint(leave_behind_min, leave_behind_max) * X_PGLD_LONG
                PGLD_to_move = PGLD_initial - leave_behind

                print(f"{pn.C_CYAN}{wallet_name}{pn.C_END} - We found {pn.C_YELLOW}{PGLD_initial / X_PGLD_LONG} gold {pn.C_END}and are required to leave behind at least ~ {leave_behind / X_PGLD_LONG} gold")
            else:
                print(f"{pn.C_CYAN}{wallet_name}{pn.C_END} - We found {pn.C_YELLOW}{PGLD_initial / X_PGLD_LONG} gold {pn.C_END}")                    

            #we must have a positve value for PGLD to try to leaveBehind
            if PGLD_to_move >= min_move:

                #grab the recipeint for this cycle
                current_recipient = next(recipient_cycle)

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
            else:
                print(f"{pn.C_MAGENTA}= No gold to move{pn.C_END}")
                print(f"{pn.C_GREEN}----------------------------------------------------------------------------------------------------------------------------------------{pn.C_END}")                  

#ransfer_PGLD(web3, PGLD_contract, current_recipient, sender_address, private_key, sender_address, pgld)  
def transfer_PGLD(web3, contract, sender, private_key, recipient, pgld_amount):
    sender_address = to_checksum_address(sender.lower())
    recipient_address = to_checksum_address(recipient.lower())

    # Get the latest block to retrieve baseFeePerGas
    latest_block = web3.eth.get_block('latest')
    base_fee = latest_block['baseFeePerGas']
    max_priority_fee = web3.to_wei(2, 'gwei')  # Set your max priority fee (miner tip)

    # Calculate maxFeePerGas (baseFee + maxPriorityFee)
    max_fee = base_fee + max_priority_fee

    # Build a transaction dictionary using EIP-1559 parameters
    txn_dict = {
        'from': sender_address,
        'to': contract.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(sender_address),
        'maxPriorityFeePerGas': max_priority_fee,
        'maxFeePerGas': max_fee,
        'data': contract.encodeABI(fn_name='transfer', args=[recipient_address, pgld_amount]),
        'chainId': web3.eth.chain_id  # Ensure the correct chain ID for Arbitrum Nova
    }

    try:
        # Estimate the gas for this specific transaction
        txn_dict['gas'] = web3.eth.estimate_gas(txn_dict)

        # Sign the transaction using your private key
        signed_txn = web3.eth.account.sign_transaction(txn_dict, private_key=private_key)

        # Send the transaction
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print('Transaction hash:', txn_hash.hex())  # This will give you the transaction hash

        # Wait for the transaction to be mined, and get the transaction receipt
        txn_receipt = web3.eth.wait_for_transaction_receipt(txn_hash)

        print(f"Transfer completed from {sender} to {recipient}")

    except Exception as e:
        print("  **Error with transferring PGLD transaction:", e)

    print("----------------------------------------------------------------------------------------------------------------------------------------")



if __name__ == "__main__":
    main()    
