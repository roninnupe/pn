from flask import Flask, render_template, redirect
import requests
import pytz
import datetime

app = Flask(__name__)

# API endpoint and query setup
URL_PIRATE_NATION_GRAPH_API = "https://subgraph.satsuma-prod.com/208eb2825ebd/proofofplay/pn-nova/api"
query = """
{
  components(where: { id: "0xb1a97b88926ecd188a41a19c0b2529eba3500bb7d9eef2a6db9bee950373446d" }) {
    entities(first: 1000) {
      worldEntity {
        components {
          fields(where: { name_in: ["merge_timestamp", "owner", "value"] }) {
            name
            value
          }
          id
        }
        id
      }
    }
  }
}
"""

# List of owners to filter by
owner_list = [
    "0x69d62b87d953009308ad4a1f538102e27ab78df5",
    "0x1b5a932411b6d6730050dd729853ca0795548aba",
    "0x5df5fec1b36198ca86b237d34ed80b0615748308",
    "0x19fb405c721190f1d343f83486095df742ece536",
    "0x7358f92797b44921854341d23cc3d3b2148a0da2",
    "0xab8bf6afbb471eecc1b6195e05e828259cb0985f",
    "0x700d32a393451cd2f66378c783de695e3a5cf123",
    "0x2704a4434338ce547e4634c129f9bc982e410122",
    "0xceea12724db5f64a5f08875dca2574a3c95535f8"
]

# Function to get data from the Pirate Nation graph
def get_data(query):
    response = requests.post(URL_PIRATE_NATION_GRAPH_API, json={'query': query})
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Fetch the data
data = get_data(query)

# Function to filter data by owner
def filter_by_owner(data, owner_list):
    filtered_entities = []
    if data:
        for entity in data['data']['components'][0]['entities']:
            for component in entity['worldEntity']['components']:
                for field in component['fields']:
                    if field['name'] == 'owner' and field['value'] in owner_list:
                        filtered_entities.append(entity)
                        break  # Stop checking other fields to avoid duplicates
    return filtered_entities

# Apply the filter
filtered_data = filter_by_owner(data, owner_list)

def check_free_status(entities):
    results = []
    now = datetime.datetime.now(pytz.utc)  # Current time in UTC
    threshold = datetime.timedelta(hours=23)  # 23 hours
    past_datetime = datetime.datetime(1, 1, 1, 0, 0, 0, tzinfo=pytz.utc)  # Past datetime for sorting "Free" entities
    base_url = "https://piratenation.game/account/"  # Base URL for the owner's account

    for entity in entities:
        owner = None  # Reset owner for each entity
        for component in entity['worldEntity']['components']:
            for field in component['fields']:
                if field['name'] == 'owner':
                    owner = field['value']  # Capture owner value
                    break  # Break after finding the owner
            if owner:
                break  # Break the loop if owner is found

        if not owner:
            continue  # Skip this entity if no owner is found

        for component in entity['worldEntity']['components']:
            merge_time = None  # Reset merge_time for each component
            for field in component['fields']:
                if field['name'] == 'merge_timestamp':
                    merge_time = datetime.datetime.fromtimestamp(int(field['value']), pytz.utc)
                    break  # Break after finding merge_timestamp

            if merge_time:  # Process only if merge_time is found
                diff = now - merge_time
                if diff > threshold:
                    status = "Free"
                    free_time_local = None
                    free_time = past_datetime  # Assign past datetime for "Free" entities
                else:
                    free_time = merge_time + threshold
                    free_time_local = free_time.astimezone(pytz.timezone('America/New_York'))
                    status = "Free at " + free_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')

                owner_url = base_url + owner  # Concatenate the base URL with the owner's address

                results.append({
                    'entity_id': entity['worldEntity']['id'],
                    'component_id': component['id'],
                    'owner': owner,  # Include owner in the result
                    'owner_url': owner_url,  # Include owner URL in the result
                    'status': status,
                    'free_time_local': free_time_local,
                    'free_time_sortable': free_time
                })

    # Sort the results in ascending order based on free_time_sortable
    # "Free" entities with past_datetime will naturally come first
    results.sort(key=lambda x: x['free_time_sortable'])

    for result in results:
        del result['free_time_sortable']  # Clean up before returning

    return results

results = check_free_status(filtered_data)
for result in results:
    print(result)

@app.route('/')
def index():
    data = get_data(query)  # Use your existing get_data function
    filtered_data = filter_by_owner(data, owner_list)  # Use your existing filter_by_owner function
    results = check_free_status(filtered_data)  # Use your updated check_free_status function

    if results:
        # Check if the first result is free and redirect
        first_result = results[0]
        if first_result['status'] == 'Free':
            return redirect(first_result['owner_url'])
        else:
            # If no shipwrights are free, render an HTML template with the results
            return render_template('shipwrights.html', results=results)
    else:
        return "Error fetching data"

if __name__ == '__main__':
    app.run(debug=True)







