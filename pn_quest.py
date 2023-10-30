import pn_helper as pn
import traceback
from web3 import Web3, HTTPProvider

web3 = pn.Web3Singleton.get_web3_Nova()
quest_contract = pn.Web3Singleton.get_QuestSystem()


class QuestCommand:
    def __init__(self, quest_name=None, quest_id=None, pirate_entity_id=None,
                 times_to_execute=None, energy_threshold=None, quest_data=None):
        """
        Create a QuestCommand instance.

        Parameters:
            quest_name (str): The name of the quest.
            quest_id (int): The ID of the quest.
            pirate_entity_id (int): The entity ID of the pirate executing the quest.
            times_to_execute (int): The number of times to attempt the quest.
            energy_threshold (float): The energy threshold required to execute the quest.
            quest_data (pandas.DataFrame): The DataFrame to store quest execution data.
        """
        self.quest_name = quest_name
        self.quest_id = quest_id
        self.pirate_entity_id = pirate_entity_id
        self.times_to_execute = times_to_execute
        self.energy_threshold = energy_threshold
        self.quest_data = quest_data

    @classmethod
    def empty(cls):
        """Create an empty QuestCommand instance."""
        return cls()


def get_quests_for_pirate(pirate_entity_id):
    pirate_contract_addr, pirate_token_id = pirate_entity_id.split('-')
    pirate_token_id = int(pirate_token_id)

    pirate_command_mappings_df = pn._pirate_command_mappings.get_mappings_df()

    # Set the appropriate generation to make sure we look up the proper pirate
    generation = 1 if pirate_contract_addr != pn._contract_PirateNFT_addr else 0

    matching_row = pirate_command_mappings_df[(pirate_command_mappings_df['tokenId'] == pirate_token_id) & (pirate_command_mappings_df['Gen'] == generation)]

    if not matching_row.empty:
        # Format is: quest_name:times_to_execute:energy_threshold,times_to_execute:energy_threshold,...
        quest_command_str = matching_row.iloc[0]['Quest']
        if isinstance(quest_command_str, str):
            quest_commands = []  # List to store QuestCommand instances

            # Split the quest_command_str by commas to get sets of commands
            command_sets = quest_command_str.split(',')

            for command_set in command_sets:
                # Split each set by colons to extract quest name, times to execute, and energy threshold
                parts = command_set.split(':')
                if len(parts) == 3:
                    quest_name, times_to_execute, energy_threshold = parts
                    times_to_execute = int(times_to_execute)
                    energy_threshold = float(energy_threshold)

                    # Create a QuestCommand instance and append it to the list
                    quest_command = QuestCommand(
                        quest_name=quest_name,
                        times_to_execute=times_to_execute,
                        pirate_entity_id=pirate_entity_id,
                        energy_threshold=energy_threshold
                    )
                    quest_commands.append(quest_command)

            return quest_commands  # Return the list of QuestCommand instances

    return None  # Token ID and generation not found in the DataFrame or quest_command_str is not a string


# Executed a quest
def start_quest(address, private_key, pirate_id, quest_data):

    # 1. Convert the graph ID to token ID & Contract
    token_contract, token_id = pn.graph_id_to_address_and_tokenId(pirate_id)

    # 2. Fetch comprehensive quest data
    all_quests_data = pn.fetch_quest_data()

    # 3. Extract input details for the specified quest ID
    quest_inputs = None
    for q in all_quests_data['data']['quests']:
        if q['id'] == quest_data['id']:
            quest_inputs = q['inputs']
            break

    if not quest_inputs:
        print(f"Error: No quest inputs found for quest ID: {quest_data['id']}")
        return None, "Failed due to missing quest inputs"

    # Token type mapping
    token_type_mapping = {'ERC1155':3, 'ERC721': 2,'ERC20': 1}

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