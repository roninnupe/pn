import argparse
import pandas as pd
import pn_helper as pn
from eth_utils import to_checksum_address

# The query used to get all bounties from the PN Grpah
bounty_query = """
    query GetComponentEntities{
      components(where: { id: "0x3ceb3cd6a633684f7095ec8b1842842250978ee3f4f137603421db15b59d137f"}) {
        id
        entities(first: 1000){
          id
          fields {
            name
            value
            worldEntity {
              id
            }
          }
        }
      }
    }
    """

class BountyMappings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BountyMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        if not self.__initialized:
            self.__initialized = True
            self.df = pd.read_csv(pn.data_path("bounty_group_mappings.csv"))

    def get_mappings_df(self):
        self.initialize()
        return self.df
    
_bounty_mappings = BountyMappings()

def get_group_id_by_bounty_name(target_bounty_name):

    try:
        bounty_mappings_df = _bounty_mappings.get_mappings_df()

        # Filter the DataFrame for the specified bounty_name
        result = bounty_mappings_df[bounty_mappings_df['bounty_name'] == target_bounty_name]

        # Check if any rows match the specified bounty_name
        if not result.empty:
            # Get the group_id from the first matching row (assuming unique bounty names)
            group_id = result.iloc[0]['group_id']
            return group_id
        else:
            return None  # No matching bounty_name found
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

class PirateBountyMappings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PirateBountyMappings, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def initialize(self):
        if not self.__initialized:
            self.__initialized = True
            self.df = pd.read_csv(pn.data_path("pn_pirates.csv"))

    def get_mappings_df(self):
        self.initialize()
        return self.df
    
_pirate_bounty_mappings = PirateBountyMappings()

def get_bounty_for_token_id(token_id):
    pirate_bounty_df = _pirate_bounty_mappings.get_mappings_df()

    matching_row = pirate_bounty_df[pirate_bounty_df['tokenId'] == token_id]
    
    if not matching_row.empty:
        return matching_row.iloc[0]['Bounty']
    else:
        return None  # Token ID not found in the DataFrame

# return the bounty hex from the bounty data, using the group_id specified, and fits the proper number of pirates
def get_bounty_hex(data, group_id, num_of_pirates):

    # Initialize a list to store matching entities
    matching_entities = []

    # Iterate through components
    for component in data['data']['components']:
        for entity in component['entities']:
            entity_group_id = None
            lower_bound = None
            upper_bound = None
            for field in entity['fields']:
                if field['name'] == 'group_id':
                    entity_group_id = field['value']
                elif field['name'] == 'lower_bound':
                    lower_bound = int(field['value'])
                elif field['name'] == 'upper_bound':
                    upper_bound = int(field['value'])

            if entity_group_id == group_id and lower_bound is not None and upper_bound is not None:
                if lower_bound <= num_of_pirates <= upper_bound:
                    matching_entities.append(entity)

    if matching_entities:
        first_entity_id = matching_entities[0]['id']
        hex_value = first_entity_id.split('-')[1]
        return hex_value
    else:
        return None


def parse_arguments():
    parser = argparse.ArgumentParser(description="Example Argument Parser")

    parser.add_argument("--skip_end_bounties", dest="end", action='store_false', default=True,
                        help="Flag to skip the endBounties")

    parser.add_argument("--skip_start_bounties", dest="start", action="store_false", default=True,
                        help="Flag to skip startBounty")

    args = parser.parse_args()
    return args


class TokenIdExceedsMaxValue(Exception):
    def __init__(self, token_id):
        self.token_id = token_id
        super().__init__(f"Token ID {token_id} exceeds the maximum value")


# Return Pirates as Entities from an address
def get_pirate_entities(address, skip_level_30):

    query = pn.make_pirate_query(address)
    json_data = pn.get_data(query)

    pirate_entities = []

    for account in json_data['data']['accounts']:
        for nft in account['nfts']:
            id_value = nft['id']
            name_value = nft['name']

            # Extract level value
            level_value = None

            for trait in nft['traits']:
                if trait['metadata']['name'] == 'level':
                    level_value = int(trait['value'])
                    break            

            print(f"{name_value} present")

            if level_value == 30 and skip_level_30:
                print(f"Skipping {name_value} because it's level 30!!!!!!!!!!!!!!!!")
            else:
                pirate_entities.append(pn.graph_id_to_entity(id_value))

    return pirate_entities


def main():
    # pull arguments out for start and end
    args = parse_arguments()
    print("endBounty:", args.end)
    print("startBounty:", args.start)
    print()

    # Load data from addresses.csv
    df_addressses = pd.read_csv(pn.data_path("addresses.csv"))

    # Display available bounties to the user only if we have start flag set
    if args.start:
        default_group_id = get_default_bounty_group_id()
        print(f"default_group_id: {default_group_id}")

    # Initialize web3 with the PN
    web3 = pn.Web3Singleton.get_web3_Nova()
    bounty_contract = pn.Web3Singleton.get_BountySystem()

    ended_bounties = 0
    started_bounties = 0

    # Load the JSON data from the file
    bounty_data = pn.get_data(bounty_query)

    print("---------------------------------------------------------------------------")
    for index, row in df_addressses.iterrows():
        wallet = row['wallet']
        address = row['address']
        private_key = row['key']

        print(f"Executing Bounties on {wallet} - {address}")

        # read the activeBounties for the address
        function_name = 'activeBountyIdsForAccount'
        function_args = [address]
        result = bounty_contract.functions[function_name](*function_args).call()

        print("Active Bounty IDs: ", result)

        # handle ending of bounties if we have the end flag set
        if args.end:
            for active_bounty_id in result:
                ended_bounties += end_bounty(web3, bounty_contract, address, private_key, active_bounty_id)        


        # if we don't have start bounties set then continue and skip all the remaining code below
        if not args.start:
            continue

        # load up all the pirate IDs per address
        pirate_ids = pn.get_pirate_ids(address)

        print(f"Wallet {wallet} has the following pirates: {pirate_ids}")
        input()

        bounties_to_execute = {} # initialize a dictionary of bounties and pirates we want to execute

        # Loop through the pirate_ids and load up bounties_to_execute
        for pirate_id in pirate_ids:
            bounty_name = get_bounty_for_token_id(pirate_id)
            bounty_group_id = get_group_id_by_bounty_name(bounty_name)
            
            # use the default group_id if we don't find one, and only if we have specified a default group_id
            if bounty_group_id is None:
                if default_group_id is None:
                    continue
                else: 
                    bounty_group_id = default_group_id
            
            # Check if the bounty_group_id is already in the dictionary, if not, create an empty list
            if bounty_group_id not in bounties_to_execute:
                bounties_to_execute[bounty_group_id] = []

            # Append the pirate_id to the list associated with the bounty_group_id
            bounties_to_execute[bounty_group_id].append(pn.pirate_token_id_to_entity(pirate_id))

            print(f"Pirate ID: {pirate_id}, Bounty Name: {bounty_name}, Group ID: {bounty_group_id}")

        # Now loop over bounties to execute and execute them
        for group_id, entity_ids in bounties_to_execute.items():   
        # if no pirates to send, don't continue on with the remaining logic in this part of the loop
            num_of_pirates = len(entity_ids)
            if num_of_pirates == 0: 
                print("---------------------------------------------------------------------------")
                continue

            hex_value = get_bounty_hex(bounty_data, group_id, num_of_pirates)
            
            # Convert hexadecimal string to base 10 integer
            # FYI, This is the bounty ID for the user-selected bounty_name
            bounty_id = int(hex_value, 16)   

            started_bounties += start_bounty(web3, bounty_contract, address, private_key, bounty_id, entity_ids) 
            print("---------------------------------------------------------------------------")

    print(f"claimed {ended_bounties} bounties and started {started_bounties} bounties")

#Prompts the user to choose a bounty, and returns the respective group id
def get_default_bounty_group_id():

    print("Available bounties:")
    
    bounty_mappings_df = _bounty_mappings.get_mappings_df()
    
    for index, row in bounty_mappings_df.iterrows():
        print(f"{index + 1}. {row['bounty_name']}")

    # Get user input for the bounty they are interested in
    selected_index = int(input("Please enter the number corresponding to the default bounty you're interested in: ")) - 1

    # Validate user input
    if selected_index < 0 or selected_index >= len(bounty_mappings_df):
       return None
    
    # Find the corresponding hex value for the selected bounty_name
    selected_bounty_name = bounty_mappings_df.iloc[selected_index]['bounty_name']
    group_id = bounty_mappings_df.iloc[selected_index]['group_id']
    return group_id


def start_bounty(web3, contract_to_write, address, private_key, bounty_id, pirates):
    print(f"Attempting to send {pirates}\n  on bounty_id: {bounty_id}")
    txn_dict = {
        'from': address,
        'to': contract_to_write.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(address),
        'gasPrice': web3.eth.gas_price,
        'data': contract_to_write.encodeABI(fn_name='startBounty', args=[bounty_id, pirates])
    }

    try:
        pn.send_web3_transaction(web3, private_key, txn_dict)
        print(f'Done startBounty from: {address}')
        return 1
    except Exception as e:
        print("  **Error sending startBounty transaction:", e)
        return 0


def end_bounty(web3, contract_to_write, address, private_key, bounty_id):
    print(f"Attempting to end active_bounty_id: {bounty_id}")
    txn_dict = {
        'from': address,
        'to': contract_to_write.address,
        'value': 0,
        'nonce': web3.eth.get_transaction_count(address),
        'gasPrice': web3.eth.gas_price,
        'data': contract_to_write.encodeABI(fn_name='endBounty', args=[bounty_id])
    }

    try:
        # Estimate the gas for this specific transaction
        pn.send_web3_transaction(web3, private_key, txn_dict)
        print(f'Done endBounty from: {address}')
        return 1
    except Exception as e:
        print("  **Error sending endBounty transaction:", e)
        return 0


if __name__ == "__main__":
    main()