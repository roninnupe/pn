import pn_helper as pn
import traceback
from web3 import Web3, HTTPProvider

web3 = pn.Web3Singleton.get_web3_Nova()
quest_contract = pn.Web3Singleton.get_QuestSystem()

# Executed a quest
def start_quest(address, private_key, pirate_id, quest_data):

    # 1. Convert the graph ID to token ID & Contract
    token_contract, token_id = pn.graph_id_to_address_and_tokenId(pirate_id)

    # 2. Fetch comprehensive quest data
    quests_data = pn.fetch_quest_data()

    # 3. Extract input details for the specified quest ID
    quest_inputs = None
    for q in quests_data['data']['quests']:
        if q['id'] == quest_data['id']:
            quest_inputs = q['inputs']
            break

    if not quest_inputs:
        print(f"Error: No quest inputs found for quest ID: {quest_data['id']}")
        return None, "Failed due to missing quest inputs"

    # Token type mapping
    token_type_mapping = {'ERC721': 2,'ERC20': 1}

    # 4. Construct the input tuples for the quest
    quest_inputs_list = []

    # 5. Append required game items for the quest
    for input_data in quest_inputs:
        token_type_str = input_data['tokenPointer']['tokenType']
        token_type_int = token_type_mapping.get(token_type_str, 0)  # Default to 0 if not found

        # Check if this is the pirate data and replace the placeholder token ID
        if token_type_int == 2 and int(input_data['tokenPointer']['tokenId']) == 0:
            input_data['tokenPointer']['tokenId'] = str(token_id)

        quest_inputs_list.append((
            token_type_int,
            Web3.to_checksum_address(input_data['tokenPointer']['tokenContract']['address']),
            int(input_data['tokenPointer']['tokenId']),
            int(input_data['tokenPointer']['amount'])
        ))

    # 6. Construct the quest_params_data using the input list
    quest_params_data = (
        int(quest_data['id']),  # questId
        # Code to replace the Pirate NFT contract address with whatever the NFT token address we get it, to support the starter pirates
        [
            (
                quest_input[0], 
                Web3.to_checksum_address(token_contract) if quest_input[1].lower() == pn._contract_PirateNFT_addr.lower() else quest_input[1], 
                quest_input[2], 
                quest_input[3]
            ) 
            for quest_input in quest_inputs_list
        ]
    )

    # 7. Create and attempt transaction
    try:
        txn = quest_contract.functions.startQuest(quest_params_data).build_transaction({
            'chainId': 42170,
            'gas': 2500000,
            'gasPrice': web3.eth.gas_price,
            'nonce': web3.eth.get_transaction_count(address),
        })

        signed_txn = web3.eth.account.sign_transaction(txn, private_key=private_key)
        txn_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        txn_reciept = web3.eth.wait_for_transaction_receipt(txn_hash)

        return txn_hash.hex(), pn.get_status_message(txn_reciept)        
    except Exception as e:
        
        # Print the error type and traceback
        print(f"Error type: {type(e).__name__}")
        traceback.print_exc()  # This prints the traceback
        print(f"Error with transaction: {e}")
    
    return None, "failed due to error"