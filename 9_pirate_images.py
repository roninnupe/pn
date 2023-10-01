from flask import Flask, render_template
import pandas as pd
import pn_helper as pn
import argparse

app = Flask(__name__)

parser = argparse.ArgumentParser()
parser.add_argument('--character_type', type=str, help='Filter by Character Type (case-insensitive)')
parser.add_argument('--background', type=str, help='Filter by Background (case-insensitive)')
parser.add_argument('--affinity', type=str, help='Filter by Affinity (case-insensitive)')

excel_file = pn.select_xlsx_file()
user_name = excel_file.split('_')[1].split('.')[0]

data = pd.read_excel(excel_file)

def transform_url(url):
    if url.startswith('ipfs://'):
        return 'https://ipfs.io/ipfs/' + url[7:]
    else:
        return url

data['imageUrl'] = data['imageUrl'].apply(transform_url)

image_data = data.to_dict(orient='records')

@app.route('/')
def index():
    args = parser.parse_args()
    character_type = args.character_type.lower() if args.character_type else None
    background = args.background.lower() if args.background else None
    affinity = args.affinity.lower() if args.affinity else None

    if character_type or background or affinity:
        # Filter the data based on specified filters
        filtered_data = data
        if character_type:
            filtered_data = filtered_data[filtered_data['Character Type'].str.lower().str.startswith(character_type)]
        if affinity:
            filtered_data = filtered_data[filtered_data['Affinity'].str.lower().str.startswith(affinity)]    
          
        if background:
            filtered_data = filtered_data.dropna(subset=['Background'])
            filtered_data = filtered_data[filtered_data['Background'].str.lower().str.startswith(background)]
        
        filtered_image_data = filtered_data.to_dict(orient='records')
    else:
        filtered_image_data = image_data

    html_file_name = pn.add_inventory_data_path(f"{user_name}.html")
    print(html_file_name)

    html_content = render_template('index.html', image_data=filtered_image_data)

    with open(html_file_name, 'w', encoding='utf-8') as file:
        file.write(html_content)

    return html_content

if __name__ == '__main__':
    app.run(port=8080)
