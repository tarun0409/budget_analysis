import random
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.figure as mpl_figure
import numpy as np
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for
import matplotlib
matplotlib.use('Agg')  # Set the backend to Agg

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        save_ca = 'save_ca' in request.form
        if file:
            file.save(file.filename)
            analysis_result = perform_operations(file.filename, save_ca)
            return redirect(url_for('analysis', result=analysis_result))
    return render_template('upload.html')


@app.route('/analysis')
def analysis():
    result = request.args.get('result')
    expenditure = json.loads(result)
    categories = list()
    budget = list()
    expense = list()
    for key in expenditure.keys():
        categories.append(key)
        budget.append(expenditure[key]['budget'])
        expense.append(expenditure[key]['expenditure'])
    chart_path = get_bar_chart(categories, budget, expense)
    chart_path = "../"+chart_path
    chart_path_with_query = chart_path + '?v=' + str(random.randint(0, 999999))
    table_html = get_budget_table(expenditure)
    return render_template('analysis.html', chart_path=chart_path_with_query, table_html=table_html)


def get_budget_table(expenditure):
    table_html = '<table>'
    table_html += '<tr><th>Category</th><th>Expenditure</th><th>Budget</th><th>Remaining</th><th>Overrun</th></tr>'
    for category, values in expenditure.items():
        expense_str = '{:.2f}'.format(values["expenditure"])
        budget_str = '{:.2f}'.format(values["budget"])
        remaining_str = '{:.2f}'.format(values["remaining"])
        overrun_str = '{:.2f}'.format(values["overrun"])+"%"
        table_html += '<tr><td>' + category + '</td><td>' + \
            expense_str + '</td><td>' + budget_str + '</td><td>' + \
            remaining_str + '</td><td>' + overrun_str + '</td></tr>'
    table_html += '</table>'
    return table_html


def get_bar_chart(categories, budget, expenses):
    bar_width = 0.35
    index = np.arange(len(categories))

    fig = mpl_figure.Figure()
    canvas = FigureCanvas(fig)  # Create a canvas for the figure

    ax = fig.subplots()

    ax.bar(index, budget, bar_width, label='Budget')
    ax.bar(index + bar_width, expenses, bar_width, label='Expenditure')

    ax.set_xlabel('Categories')
    ax.set_ylabel('Amounts')
    ax.set_title('Analysis Results')
    ax.set_xticks(index + bar_width / 2)
    # Rotate x-axis labels by 45 degrees
    ax.set_xticklabels(categories, rotation=90)
    ax.legend()

    chart_path = 'static/chart.png'
    canvas.print_figure(chart_path, bbox_inches='tight')
    return chart_path


def get_budget():
    with open('budget.json', 'r') as file:
        budget_data = json.load(file)
    for key in budget_data.keys():
        val = budget_data[key]
        budget_data[key] = dict()
        budget_data[key]['budget'] = val
        budget_data[key]['expenditure'] = 0
    return budget_data


def get_category_amortisations():
    with open('category_amortisation.json', 'r') as file:
        return json.load(file)


def add_expenditure(budget, category, expense):
    category_split = category.split(':')
    if category_split[0] in budget:
        budget[category_split[0]]['expenditure'] += expense
    if category in budget:
        budget[category]['expenditure'] += expense
    budget['Total']['expenditure'] += expense
    return budget


def compute_expenditure(budget, transactions, ca):

    amortised_categories = set()
    # all transactions
    for index, row in transactions.iterrows():
        category = row['Category']
        expense = -1*row['Amount']
        if not pd.isnull(row['Category']):
            if category in ca:
                ca[category]['debt'] += expense
                if category not in amortised_categories:
                    ca[category]['remaining'] += ca[category]['value']
                amortised_categories.add(category)
                continue
            budget = add_expenditure(budget, category, expense)

    # category amortisation transactions
    for category in ca.keys():
        if ca[category]['remaining'] == 0:
            continue
        expense = ca[category]['debt']/ca[category]['remaining']
        budget = add_expenditure(budget, category, expense)
        ca[category]['debt'] -= expense
        ca[category]['remaining'] -= 1

    return budget, ca


def compute_budget_metrics(expenditure):
    for category in expenditure:
        budget = expenditure[category]['budget']
        expense = expenditure[category]['expenditure']
        remaining = budget - expense
        overrun = ((expense-budget)/budget)*100
        expenditure[category]['remaining'] = remaining
        expenditure[category]['overrun'] = overrun
    return expenditure


def perform_operations(filename, save_ca):
    df = pd.read_csv(filename)
    df = df[~(df['Description'].isnull() |
              df['Description'].str.startswith("Transfer"))]
    df = df[df['Amount'] < 0]
    budget = get_budget()
    ca = get_category_amortisations()
    expenditure, ca = compute_expenditure(budget, df, ca)
    if save_ca:
        with open('category_amortisation.json', 'w') as f:
            json.dump(ca, f)
    expenditure = compute_budget_metrics(expenditure)
    ejson = json.dumps(expenditure)
    cajson = json.dumps(ca)
    print(ejson)
    return ejson


if __name__ == '__main__':
    app.run()
