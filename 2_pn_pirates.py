import time
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import pytz

start_time = time.time() 

# Step 1: Read data from a CSV file and create a dictionary mapping token IDs to rarity ranks.
df = pd.read_csv('../pn data/rarity_scores_final.csv')
df.tokenId = df.tokenId.astype(str)  # Ensure all token IDs are strings.
tokenId_rarity_dict = dict(zip(df.tokenId, df.RarityRank))

# Step 2: Read addresses from a text file and create a dictionary mapping addresses to IDs.
with open('../pn data/addresses.txt', 'r') as file:
    addresses = file.read().splitlines()
addresses = [address.lower().strip() for address in addresses]
address_id_dict = {address: i+1 for i, address in enumerate(addresses)}
formatted_output = ', '.join(f'"{address}"' for address in addresses)

# XP required for each level
total_xp_to_level_up = [0, 0, 25, 50, 100, 200, 400, 700, 1100, 1600, 2100, 2600, 3100, 3600, 4100, 5100, 6100, 7100, 8100, 9100, 10100, 11600, 13100, 14600, 16100, 18100, 20100, 22100, 24100, 26100, 28100, 0]

expertise_id_mapping = {
    "1": "Attack",
    "2": "Evasion",
    "3": "Speed",
    "4": "Accuracy",
    "5": "Health"
}

# GraphQL Query
query = f"""
{{
    accounts(where: {{address_in: [{formatted_output}]}} ) {{
        address
        nfts(first: 1000, where: {{nftType: "pirate"}}) {{
            tokenId
            claimedMilestones {{
                milestoneIndex
            }}
            lastTransfer
            traits {{
                value
                metadata {{
                    name
                }}
            }}
        }}
    }}
}}
"""

data = requests.post("https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api", json={'query': query}).json()

# Maps expertise IDs to their respective names
def map_expertise(nft, expertise_id_mapping):
    for trait in nft['traits']:
        if trait['metadata']['name'] == 'expertise_id':
            trait['metadata']['name'] = 'Expertise'
            trait['value'] = expertise_id_mapping[trait['value']]

# Add Rarity Rank to the traits
def add_rarity_rank(tokenId_rarity_dict, nft):
    tokenId_str = str(nft['tokenId'])  # Convert tokenId to a string before accessing the dictionary.
    rarity_rank = tokenId_rarity_dict.get(tokenId_str, 'No data')
    nft['traits'].append({'metadata': {'name': 'Rarity Rank'}, 'value': rarity_rank})

# Calculate the next claim date and add related traits
def add_next_claim_date(nft):
    max_milestone_index = max([milestone['milestoneIndex'] for milestone in nft['claimedMilestones']], default=-1)
    next_milestone_index = max_milestone_index + 1
    if next_milestone_index == 0:
        next_claim_date = int(nft['lastTransfer']) + 7 * 24 * 60 * 60
    elif next_milestone_index in [1, 2]:
        next_claim_date = int(nft['lastTransfer']) + next_milestone_index * 30 * 24 * 60 * 60
    elif next_milestone_index in [3, 4, 5]:
        next_claim_date = int(nft['lastTransfer']) + 3 * 30 * 24 * 60 * 60
    elif next_milestone_index == 6:
        next_claim_date = int(nft['lastTransfer']) + 135 * 24 * 60 * 60
    else:
        next_claim_date = "All claimed"
    if next_claim_date != "All claimed":
        next_claim_date = datetime.fromtimestamp(next_claim_date, pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S')
    nft['traits'].append({'metadata': {'name': 'Next Claim Date'}, 'value': next_claim_date})
    nft['traits'].append({'metadata': {'name': 'ClaimedChests'}, 'value': max_milestone_index+1})    

# Calculate the upgradable level and add related traits
def calculate_upgradable_level(total_xp_to_level_up, nft):
    xp = next((int(trait['value']) for trait in nft['traits'] if trait['metadata']['name'] == 'xp'), 0)
    currentLevel = next((int(trait['value']) for trait in nft['traits'] if trait['metadata']['name'] == 'level'), 0)
    upgradableLevel = next((i for i, xp_required in enumerate(total_xp_to_level_up) if xp < xp_required), len(total_xp_to_level_up))
    if currentLevel == upgradableLevel - 1:
        upgradableLevel = 0
        if currentLevel < 30:
            nft['traits'].append({'metadata': {'name': 'to next'}, 'value': total_xp_to_level_up[currentLevel+1]-xp})
        else:
            upgradableLevel -= 1
            if upgradableLevel < 31:
                nft['traits'].append({'metadata': {'name': 'to next'}, 'value': total_xp_to_level_up[upgradableLevel+1]-xp})
                nft['traits'].append({'metadata': {'name': 'potential'}, 'value': upgradableLevel})    


data_to_export = []

if 'data' in data and 'accounts' in data['data']:
    accounts = data['data']['accounts']

    # Iterate over each account
    for account in accounts:
        address = account['address']
        nfts = account['nfts']

        # Check if 'nfts' is not empty
        if nfts:
            for nft in nfts:
                nft['address'] = address
                map_expertise(nft, expertise_id_mapping)
                add_rarity_rank(tokenId_rarity_dict, nft)
                add_next_claim_date(nft)
                calculate_upgradable_level(total_xp_to_level_up, nft)

                row = {'address': nft['address'], 'tokenId': nft['tokenId'], 'lastTransfer': nft['lastTransfer']}
                for trait in nft['traits']:
                    row[trait['metadata']['name']] = trait['value']
                data_to_export.append(row)
        else:
            print(f"No NFTs found for account: {address}")
else:
    print("Invalid or empty response.")


# Add WalletID to each row
for row in data_to_export:
    row["#"] = address_id_dict[row["address"]]

# Sort data_to_export by 'WalletID'
data_to_export_sorted = sorted(data_to_export, key=lambda x: x['#'])


# Define the desired column order
column_order = [
    "#",
    "address",
    "tokenId",
    "Character Type",
    "level",
    "potential",
    "xp",
    "to next",    
    "Elemental Affinity",
    "Expertise",
    "Background",
    "Headwear",
    #"Rarity Rank",
    "Dice Roll 1",
    "Dice Roll 2",
    #"lastTransfer",
    "ClaimedChests",
    "Next Claim Date",
    #"affinity_id",
    "Skin",
    "Star Sign",
    "Eyes",
    "Earring",
    "Coat",
    "Eye Covering",
]

# Load the Excel file
file_name = '../pn data/pn_pirates.xlsx'
xlWriter = pd.ExcelWriter(file_name,
                        engine='xlsxwriter',
                        engine_kwargs={'options': {'strings_to_numbers': True}})

# Create the DataFrame and reorder the columns
df_to_export = pd.DataFrame(data_to_export_sorted)
df_to_export = df_to_export.reindex(columns=column_order)
df_to_export = df_to_export.rename(columns={'xp': ' xp ', 'Elemental Affinity': 'Affinity', 'Dice Roll 1': 'D1 ', 'Dice Roll 2': 'D2 '})

df_to_export['level'] = pd.to_numeric(df_to_export['level'], errors='coerce')

# Calculate the average of the "level" column
average_level = df_to_export['level'].mean()
average_level_rounded = round(average_level, 2)
num_rows_used = df_to_export['level'].count()

print("------------------------------------------------------")
print(f"The average level of {num_rows_used} pirates analyzed is {average_level_rounded:.2f}")
print("------------------------------------------------------")

# Export to Excel
df_to_export.to_excel(xlWriter, index=False)

# Get the xlsxwriter workbook and worksheet objects
workbook = xlWriter.book
worksheet = xlWriter.sheets['Sheet1']

# Freeze the first row (row 1, column 0)
worksheet.freeze_panes(1, 0)
worksheet.add_table(0, 0, df_to_export.shape[0], df_to_export.shape[1] - 1, {'columns': [{'header': col} for col in df_to_export.columns]})

# Autofit column width to fit the content
for i, col in enumerate(df_to_export.columns):
    column_len = max(df_to_export[col].astype(str).str.len().max(), len(col) + 2)  # Get the length of the longest content in the column or column name
    worksheet.set_column(i, i, column_len)  # Set the column width to fit

#worksheet.write(df_to_export.shape[0] + 1, 2, average_level) 

xlWriter._save()

end_time = time.time()
execution_time = end_time - start_time
print(f"Created {file_name} in {execution_time:.2f} seconds")    