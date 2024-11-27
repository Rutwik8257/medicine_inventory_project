from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

file_path = 'supply_chain_data.xlsx'
user_data_path = 'user_data.xlsx'

# Ensure user data file exists with the correct columns
def ensure_user_data_file():
    if not os.path.exists(user_data_path):
        user_data_df = pd.DataFrame(columns=['Username', 'Password', 'Access'])
        user_data_df.to_excel(user_data_path, index=False)

# Load user data from Excel
def load_user_data():
    return pd.read_excel(user_data_path)

# Load the inventory from the Excel file
def load_inventory():
    try:
        return pd.read_excel(file_path, sheet_name='Inventory')
    except FileNotFoundError:
        return pd.DataFrame(columns=['Item ID', 'Item Name', 'Quantity', 'Unit Price', 'Expiry Date', 'Quantity Limit'])

# Save inventory back to the file
def save_inventory(inventory):
    with pd.ExcelWriter(file_path) as writer:
        inventory.to_excel(writer, sheet_name='Inventory', index=False)

@app.route('/index')
def index():
    if 'username' in session:
        if session.get('access') == "Yes":
            return render_template('index.html')  # Full access dashboard
        elif session.get('access') == "No":
            return redirect(url_for('user_dashboard'))  # Limited dashboard
    return redirect(url_for('login_page'))

@app.route('/user_dashboard')
def user_dashboard():
    if 'username' in session and session.get('access') == "No":
        return render_template('user_dashboard.html')  # Limited dashboard template
    return redirect(url_for('index'))

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    users = load_user_data()

    user = users[(users['Username'] == username) & (users['Password'] == password)]
    if not user.empty:
        session['username'] = username
        session['access'] = user.iloc[0]['Access']
        return redirect(url_for('index'))
    else:
        return "Invalid username or password."
    
@app.route('/signup', methods=['GET', 'POST'])
def signup_page():  # Ensure the function name matches the endpoint in your code
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_user_data()

        if username in users['Username'].values:
            return "Username already exists."
        else:
            # Add the new user with "No" in the "Access" column
            new_user = pd.DataFrame([[username, password, 'No']], columns=['Username', 'Password', 'Access'])
            updated_users = pd.concat([users, new_user], ignore_index=True)
            updated_users.to_excel(user_data_path, index=False)
            return redirect(url_for('login_page'))  # Ensure this correctly references the 'login_page' endpoint
    return render_template('signup.html')



@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('access', None)
    return redirect(url_for('login_page'))

# Full-access routes for users with "Yes" in Access
@app.route('/add_inventory_form', methods=['GET', 'POST'])
def add_inventory_form():
    if 'username' in session and session.get('access') == "Yes":
        if request.method == 'POST':
            item_id = int(request.form['item_id'])
            item_name = request.form['item_name']
            quantity = int(request.form['quantity'])
            unit_price = float(request.form['unit_price'])
            expiry_date = request.form['expiry_date'] if request.form['expiry_date'] else None
            quantity_limit = request.form['quantity_limit'] if request.form['quantity_limit'] else None

            inventory = load_inventory()

            existing_item = inventory[inventory['Item ID'] == item_id]
            if not existing_item.empty:
                if existing_item['Item Name'].iloc[0] != item_name:
                    return render_template('add_inventory_form.html', item_name_mismatch=True, item_exists=False)

            duplicate = inventory[
                (inventory['Item ID'] == item_id) &
                (inventory['Item Name'] == item_name) &
                (inventory['Expiry Date'] == expiry_date)
            ]

            if not duplicate.empty:
                return render_template('add_inventory_form.html', item_exists=True, item_name_mismatch=False)

            new_item = pd.DataFrame([[item_id, item_name, quantity, unit_price, expiry_date, quantity_limit]],
                                    columns=['Item ID', 'Item Name', 'Quantity', 'Unit Price', 'Expiry Date', 'Quantity Limit'])
            inventory = pd.concat([inventory, new_item], ignore_index=True)
            save_inventory(inventory)
            return redirect(url_for('index'))

        return render_template('add_inventory_form.html', item_exists=False, item_name_mismatch=False)
    return redirect(url_for('index'))

@app.route('/update_inventory_form', methods=['GET', 'POST'])
def update_inventory_form():
    if 'username' in session and session.get('access') == "Yes":
        if request.method == 'POST':
            item_id = request.form['item_id']
            item_name = request.form['item_name']
            expiry_date = request.form['expiry_date']
            action = request.form['action']
            quantity = int(request.form['quantity'])

            inventory = load_inventory()
            if not expiry_date:
                return render_template('update_inventory_form.html', missing_expiry_date=True, item_not_found=False, insufficient_stock=False)

            item_id = int(item_id) if item_id else None

            matching_items = inventory[
                (inventory['Item ID'] == item_id if item_id else True) &
                (inventory['Item Name'].str.lower() == item_name.lower() if item_name else True) &
                (inventory['Expiry Date'] == expiry_date)
            ]

            if matching_items.empty:
                return render_template('update_inventory_form.html', missing_expiry_date=False, item_not_found=True, insufficient_stock=False)

            current_quantity = matching_items.iloc[0]['Quantity']

            if action == 'remove' and quantity > current_quantity:
                return render_template('update_inventory_form.html', missing_expiry_date=False, item_not_found=False, insufficient_stock=True, current_quantity=current_quantity)

            if action == 'add':
                inventory.loc[matching_items.index, 'Quantity'] += quantity
            elif action == 'remove':
                inventory.loc[matching_items.index, 'Quantity'] -= quantity

            save_inventory(inventory)
            return redirect(url_for('index'))

        return render_template('update_inventory_form.html', missing_expiry_date=False, item_not_found=False, insufficient_stock=False)
    return redirect(url_for('index'))

# Routes common to all users
@app.route('/check_inventory_form', methods=['GET', 'POST'])
def check_inventory_form():
    if 'username' in session:
        if request.method == 'POST':
            item_id = request.form.get('item_id')
            item_name = request.form.get('item_name')

            if item_id and item_name:
                return render_template('check_inventory_form.html', error="Provide either Item ID or Item Name, not both.")
            elif not item_id and not item_name:
                return render_template('check_inventory_form.html', error="Provide either Item ID or Item Name.")

            inventory = load_inventory()
            item = inventory[inventory['Item ID'] == int(item_id)] if item_id else inventory[inventory['Item Name'].str.lower() == item_name.lower()]

            if not item.empty:
                return render_template('check_inventory_result.html', items=item.to_dict(orient='records'))
            else:
                return render_template('check_inventory_result.html', items=[])

        return render_template('check_inventory_form.html')
    return redirect(url_for('login_page'))

@app.route('/items_below_limit')
def items_below_limit():
    if 'username' in session:
        inventory = load_inventory()
        items_below_limit = inventory[inventory['Quantity'] < inventory['Quantity Limit']]
        return render_template('items_below_limit.html', items=items_below_limit.to_dict(orient='records'))
    return redirect(url_for('index'))

@app.route('/expired_items')
def expired_items():
    if 'username' in session:
        inventory = load_inventory()
        inventory['Expiry Date'] = pd.to_datetime(inventory['Expiry Date'], errors='coerce')
        expired_items = inventory[inventory['Expiry Date'] < datetime.now()]
        expired_data = expired_items.groupby('Expiry Date')['Quantity'].sum()
        fig = px.pie(values=expired_data.values, names=expired_data.index.strftime('%Y-%m-%d'), title="Expired Items")
        pie_chart_html = fig.to_html(full_html=False)
        return render_template('expired_items.html', items=expired_items.to_dict(orient='records'), pie_chart_html=pie_chart_html)
    return redirect(url_for('login_page'))

@app.route('/delete_inventory_form', methods=['GET', 'POST'])
def delete_inventory_form():
    if 'username' in session and session.get('access') == "Yes":
        if request.method == 'POST':
            item_id = request.form['item_id']
            inventory = load_inventory()

            # Find and delete the item from inventory
            inventory = inventory[inventory['Item ID'] != int(item_id)]
            save_inventory(inventory)
            return redirect(url_for('index'))

        return render_template('delete_inventory_form.html')
    return redirect(url_for('index'))

@app.route('/total_inventory_graph')
def total_inventory_graph():
    if 'username' in session:
        # Load the inventory data
        inventory = load_inventory()

        # Convert 'Expiry Date' to datetime for comparison
        inventory['Expiry Date'] = pd.to_datetime(inventory['Expiry Date'], errors='coerce')

        # Get the current date for expired items check
        current_date = datetime.now()

        # Identify expired items
        expired_items = inventory[inventory['Expiry Date'] < current_date]

        # Group total inventory by Item Name and sum up quantities
        total_stock = inventory.groupby('Item Name')['Quantity'].sum().reset_index()

        # Group expired items by Item Name and sum up expired quantities
        expired_stock = expired_items.groupby('Item Name')['Quantity'].sum().reset_index()

        # Merge total stock and expired stock data
        inventory_summary = pd.merge(total_stock, expired_stock, on='Item Name', how='left')

        # Fill NaN values in expired quantities with 0 (items that don't have expired stock)
        inventory_summary['Quantity_y'] = inventory_summary['Quantity_y'].fillna(0)

        # Rename the columns for clarity
        inventory_summary.rename(columns={'Quantity_x': 'Total Quantity', 'Quantity_y': 'Expired Quantity'}, inplace=True)

        # Calculate the percentage of expired items for each item
        inventory_summary['Expired Percentage'] = (inventory_summary['Expired Quantity'] / inventory_summary['Total Quantity']) * 100

        # Prepare a new column for hover text
        inventory_summary['Hover Text'] = (
            'Item: ' + inventory_summary['Item Name'] + 
            '<br>Total Stock: ' + inventory_summary['Total Quantity'].astype(str) +
            '<br>Expired Quantity: ' + inventory_summary['Expired Quantity'].astype(str) +
            '<br>Expired Percentage: ' + inventory_summary['Expired Percentage'].round(2).astype(str) + '%'
        )

        # Create a pie chart using Plotly
        fig = px.pie(inventory_summary, 
                     names='Item Name', 
                     values='Total Quantity', 
                     title="Total Inventory with Expired Percentage")

        # Update the hover template to use the prepared hover text
        fig.update_traces(hovertemplate='%{customdata}', customdata=inventory_summary['Hover Text'])

        # Generate the pie chart HTML
        graph_html = fig.to_html(full_html=False)

        return render_template('total_inventory_graph.html', graph_html=graph_html)

    return redirect(url_for('login_page'))



# Ensure the user data file exists on startup
if __name__ == "__main__":
    ensure_user_data_file()
    app.run(debug=True)
