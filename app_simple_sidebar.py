import base64
import datetime
import io
from string import whitespace

from dash import Dash, dash_table, dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import os
from collections import OrderedDict

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


def create_dataTypeDict(df):
    DTD = dict(df.dtypes)
    for k, v in DTD.items():
        if np.issubdtype(v, np.number):
            DTD[k] = "numeric"
        else:
            DTD[k] = "text"
    return DTD


def create_offcanvas(df):
    return html.Div(
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


@app.callback(
    Output("offcanvas-scrollable", "is_open"),
    Input("open-offcanvas-scrollable", "n_clicks"),
    State("offcanvas-scrollable", "is_open"),
)
def toggle_offcanvas_scrollable(n1, is_open):
    if n1:
        return not is_open
    return is_open


def create_form(PAGE_SIZE, offcanvas):
    return dbc.Row(
        [
            dbc.Col(
                [html.H4("Columns", className="card-title"), offcanvas],
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


def create_data_table(df, dataTypeDict):
    return dash_table.DataTable(
        id="table-sorting-filtering",
        data=df.to_dict(orient="records"),
        columns=[
            {
                "id": i,
                "name": i,
                "type": dataTypeDict.get(i, "any"),
                "deletable": True,
                "presentation": "markdown",
            }
            if i == "links"
            else {
                "name": i,
                "id": i,
                "type": dataTypeDict.get(i, "any"),
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

                # word operators need spaces after them in the filter string,
                # but we don't want these later
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


def parse_contents(contents, filename, date):
    content_type, content_string = contents.split(",")

    decoded = base64.b64decode(content_string)
    try:
        if "csv" in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        elif "xls" in filename:
            # Assume that the user uploaded an excel file
            df = pd.read_excel(io.BytesIO(decoded))
    except Exception as e:
        print(e)
        return html.Div(["There was an error processing this file."])

    return df


@app.callback(
    Output("table-sorting-filtering", "data"),
    Output("table-sorting-filtering", "columns"),
    Output("table-size", "value"),
    Output("table-sorting-filtering", "page_size"),
    Output("column-selection", "options"),
    Output("column-selection", "value"),
    Input("table-sorting-filtering", "page_current"),
    Input("page-size", "value"),
    Input("table-sorting-filtering", "sort_by"),
    Input("table-sorting-filtering", "filter_query"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    State("upload-data", "last_modified"),
)
def update_table(
    page_current,
    page_size,
    sort_by,
    filter,
    list_of_contents,
    list_of_names,
    list_of_dates,
):
    filtering_expressions = filter.split(" && ")
    if list_of_contents:
        dff = parse_contents(list_of_contents, list_of_names, list_of_dates)
        DTD = create_dataTypeDict(dff)
    else:
        dff = df
        DTD = create_dataTypeDict(dff)

    for filter_part in filtering_expressions:
        col_name, operator, filter_value = split_filter_part(filter_part)
        if filter_value:
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
        dff.size,
        page_size,
        dff.keys(),
        dff.keys(),
    )


def create_app_layout(form, data_table):
    return html.Div(
        [
            dcc.Upload(
                id="upload-data",
                children=html.Div([html.A("SELECT FILE (CSV or XLS)")]),
                style={
                    "width": "98%",
                    "height": "60px",
                    "lineHeight": "60px",
                    "borderWidth": "1px",
                    "borderStyle": "dashed",
                    "borderRadius": "5px",
                    "textAlign": "center",
                    "margin": "10px",
                    "font-weight": "bold",
                },
                multiple=False,
            ),
            html.Br(),
            form,
            html.Br(),
            data_table,
        ]
    )


def build_app(PAGE_SIZE, df):
    dataTypeDict = create_dataTypeDict(df)
    offcanvas = create_offcanvas(df)
    form = create_form(PAGE_SIZE, offcanvas)
    data_table = create_data_table(df, dataTypeDict)
    return create_app_layout(form, data_table)


if __name__ == "__main__":

    PAGE_SIZE = 50
    df = pd.read_csv("Tables/BBB_test.csv")
    # df = pd.read_csv(
    # "https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv"
    # )
    app.layout = build_app(PAGE_SIZE, df)
    app.run_server(debug=True)


# df = pd.read_csv("Tables/220915_ALL_1_clean_2.csv")

# table_files = os.listdir("Tables")
# for col in df.columns:
#     try:
#         df = df.assign(values=df[col].str.split(",")).explode("values")
#         print("split: " + col)
#     except:
#         print("nope: " + col)
