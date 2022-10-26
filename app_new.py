import base64
import datetime
import io
import sys
from string import whitespace

from dash import Dash, dash_table, dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import os
from collections import OrderedDict


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

try:
    file = sys.argv[1]
    if not ".csv" in file:
        sys.exit()
except:
    sys.exit("Ooops - Start the script with a csv file as first arg")

#############
# CONSTANTS #
#############

# default value for paging
PAGE_SIZE = 20

df = pd.read_csv(file, index_col=0)

# dictionary that each column assigns a type - for filtering
DTD = dict(df.dtypes)
for k, v in DTD.items():
    if np.issubdtype(v, np.number):
        DTD[k] = "numeric"
    else:
        DTD[k] = "text"

########################
# DASH LAYOUT ELEMENTS #
########################

sidebar = html.Div(
    [
        dbc.Button(
            "show / hide columns",
            id="open-offcanvas-scrollable",
            n_clicks=0,
        ),
        dbc.Offcanvas(
            dbc.Col(
                [
                    dcc.Checklist(
                        df.keys(),
                        df.keys(),
                        id="column-selection",
                        style={"font-size": 20},
                        inputStyle={"margin-left": "20px", "margin-right": "20px"},
                        labelStyle={"display": "block"},
                    ),
                ]
            ),
            id="offcanvas-scrollable",
            scrollable=True,
            title="Show / Hide Columns",
            is_open=False,
        ),
    ]
)

form = dbc.Row(
    [
        dbc.Col(
            [html.H4("Columns", className="card-title"), sidebar],
            width="auto",
        ),
        dbc.Col(
            [
                html.H4("Number of Entries", className="card-title"),
                dbc.Input(
                    id="table-size",
                    type="number",
                    value=PAGE_SIZE,
                    className="mb-3",
                    disabled=True,
                ),
            ],
            width="auto",
        ),
        dbc.Col(
            [
                html.H4("Set Paging Size", className="card-title"),
                dbc.Input(
                    id="page-size",
                    type="number",
                    className="mb-3",
                    value=PAGE_SIZE,
                    # style={"width": "50%"},
                ),
            ],
            width="auto",
        ),
    ]
)

data_table = dash_table.DataTable(
    id="table-sorting-filtering",
    data=df.to_dict(orient="records"),
    columns=[
        {
            "id": i,
            "name": i,
            "type": DTD.get(i, "any"),
            "deletable": True,
            "presentation": "markdown",
        }
        if i == "links"
        else {
            "name": i,
            "id": i,
            "type": DTD.get(i, "any"),
            "deletable": True,
        }
        for i in df.columns
    ],
    page_current=0,
    # row_selectable="single",
    page_size=PAGE_SIZE,
    page_action="custom",
    filter_action="custom",
    filter_query="",
    sort_action="custom",
    sort_mode="multi",
    sort_by=[],
    style_as_list_view=True,
    style_cell={
        # "padding": "5px",
        # "padding-right": "30px",
        "padding-left": "10px",
        "whiteSpace": "pre",
    },
    style_data={"color": "black", "backgroundColor": "white"},
    style_data_conditional=[
        {
            "if": {"row_index": "odd"},
            "backgroundColor": "rgb(220, 220, 220)",
        }
    ],
    style_header={
        "backgroundColor": "rgb(210, 210, 210)",
        "color": "black",
        "fontWeight": "bold",
    },
    css=[
        {"selector": ".show-hide", "rule": "display: none"},
        {"selector": "p", "rule": "margin-bottom: 0; text-align: center"},
    ],
)

#############
# CALLBACKS #
#############


@app.callback(
    Output("offcanvas-scrollable", "is_open"),
    Input("open-offcanvas-scrollable", "n_clicks"),
    State("offcanvas-scrollable", "is_open"),
)
def toggle_offcanvas_scrollable(n1, is_open):
    if n1:
        return not is_open
    return is_open


# Filter Operators
operators = [
    ["ge ", ">="],
    ["le ", "<="],
    ["lt ", "<"],
    ["gt ", ">"],
    ["ne ", "!="],
    ["eq ", "="],
    ["contains "],
    ["datestartswith "],
]


def split_filter_part(filter_part):
    for operator_type in operators:
        for operator in operator_type:
            if operator in filter_part:
                name_part, value_part = filter_part.split(operator, 1)
                name = name_part[name_part.find("{") + 1 : name_part.rfind("}")]

                value_part = value_part.strip()
                v0 = value_part[0]
                if v0 == value_part[-1] and v0 in ("'", '"', "`"):
                    value = value_part[1:-1].replace("\\" + v0, v0)
                else:
                    try:
                        value = float(value_part)
                    except ValueError:
                        value = value_part
                return name, operator_type[0].strip(), value
    return [None] * 3


@app.callback(
    Output("table-sorting-filtering", "hidden_columns"),
    Input("column-selection", "value"),
    State("column-selection", "options"),
)
def hide_cols(col_sel, col_opts):
    set_dif = set(col_opts).symmetric_difference(set(col_sel))
    temp_dif = list(set_dif)
    # cols = df.keys()
    return temp_dif


@app.callback(
    Output("table-sorting-filtering", "data"),
    Output("table-sorting-filtering", "columns"),
    Output("table-size", "value"),
    Output("table-sorting-filtering", "page_size"),
    Input("table-sorting-filtering", "page_current"),
    Input("page-size", "value"),
    Input("table-sorting-filtering", "sort_by"),
    Input("table-sorting-filtering", "filter_query"),
)
def update_table(
    page_current,
    page_size,
    sort_by,
    filter,
):
    filtering_expressions = filter.split(" && ")
    dff = df

    for filter_part in filtering_expressions:
        col_name, operator, filter_value = split_filter_part(filter_part)
        if filter_value:
            if isinstance(filter_value, (int, float)):
                if filter_value.is_integer():
                    filter_value = int(filter_value)
        if operator in ("eq", "ne", "lt", "le", "gt", "ge"):
            # these operators match pandas series operator method names
            dff = dff.loc[getattr(dff[col_name], operator)(filter_value)]
        elif operator == "contains":
            if not np.issubdtype(dff[col_name], np.number):
                filter_value = str(filter_value)
            dff = dff.loc[dff[col_name].str.contains(filter_value)]
        elif operator == "datestartswith":
            # this is a simplification of the front-end filtering logic,
            # only works with complete fields in standard format
            dff = dff.loc[dff[col_name].str.startswith(filter_value)]

    if len(sort_by):
        dff = dff.sort_values(
            [col["column_id"] for col in sort_by],
            ascending=[col["direction"] == "asc" for col in sort_by],
            inplace=False,
        )

    page = page_current
    size = page_size
    columns = [
        {
            "name": i,
            "id": i,
            "type": DTD.get(i, "any"),
            "deletable": True,
            "presentation": "markdown",
        }
        if i == "links"
        else {
            "name": i,
            "id": i,
            "type": DTD.get(i, "any"),
            "deletable": True,
        }
        for i in dff.columns
    ]
    return (
        dff.iloc[page * size : (page + 1) * size].to_dict("records"),
        columns,
        dff.shape[0],
        page_size,
    )


if __name__ == "__main__":
    app.layout = html.Div(
        [
            html.Br(),
            html.H2(f"FILE: {file}"),
            html.Br(),
            form,
            html.Br(),
            data_table,
        ]
    )
    app.run_server(debug=True)
