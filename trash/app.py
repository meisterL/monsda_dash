from dash import Dash, dash_table, html, dcc, Input, Output
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import os
from collections import OrderedDict


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

table_files = os.listdir("Tables")

Pages = [dbc.NavLink("Info", href="/", active="exact")]
DFs = []

for table in table_files:
    Pages.append(dbc.NavLink("Tables/" + table, href=f"/{table}", active="exact"))
    DFs.append(pd.read_csv("Tables/" + table))

PAGE_SIZE = 50

## SIDEBAR
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "16rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}
# the styles for the main content position it to the right of the sidebar and
# add some padding.
CONTENT_STYLE = {
    "margin-left": "18rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}

sidebar = html.Div(
    [
        html.H2("MONSDA", className="display-4"),
        html.Hr(),
        html.P("A simple sidebar layout with navigation links", className="lead"),
        dbc.Nav(
            Pages,
            vertical=True,
            pills=True,
        ),
    ],
    style=SIDEBAR_STYLE,
)


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == "/":
        return html.P("This is the content of the home page!")
    elif pathname == "/page-2":
        return html.P("Oh cool, this is page 2!")
    for table in table_files:
        if pathname == f"/{table}":
            return table_page
    # If the user tries to reach a different page, return a 404 message
    return html.Div(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ],
        className="p-3 bg-light rounded-3",
    )


content = html.Div(id="page-content", style=CONTENT_STYLE)

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

df = DFs[1]

## TABLE
collapse = html.Div(
    [
        dbc.Button(
            "Select Columns",
            id="collapse-button",
            className="mb-3",
            color="primary",
            n_clicks=0,
        ),
        dbc.Collapse(
            dbc.Card(
                [
                    dbc.CardBody("This content is hidden in the collapse"),
                    dcc.Checklist(
                        df.keys(),
                        df.keys(),
                        id="column-selection",
                        inputStyle={"margin-left": "20px"},
                        labelStyle={"display": "block"},
                    ),
                ]
            ),
            id="collapse",
            is_open=False,
        ),
    ]
)


@app.callback(
    Output("collapse", "is_open"),
    [Input("collapse-button", "n_clicks")],
    [State("collapse", "is_open")],
)
def toggle_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


table_page = html.Div(
    [
        collapse,
        html.Br(),
        dash_table.DataTable(
            id="table-sorting-filtering",
            columns=[
                {"name": i, "id": i, "deletable": True} for i in sorted(df.columns)
            ],
            page_current=0,
            page_size=PAGE_SIZE,
            page_action="custom",
            filter_action="custom",
            filter_query="",
            sort_action="custom",
            sort_mode="multi",
            sort_by=[],
            style_as_list_view=True,
            style_cell={
                "padding": "5px",
                "padding-right": "30px",
                "padding-left": "10px",
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
            css=[{"selector": ".show-hide", "rule": "display: none"}],
        ),
    ]
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
)
def hide_cols(col_sel):
    cols = df.keys()
    return cols.difference(col_sel)


@app.callback(
    Output("table-sorting-filtering", "data"),
    Input("table-sorting-filtering", "page_current"),
    Input("table-sorting-filtering", "page_size"),
    Input("table-sorting-filtering", "sort_by"),
    Input("table-sorting-filtering", "filter_query"),
)
def update_table(page_current, page_size, sort_by, filter):
    filtering_expressions = filter.split(" && ")
    dff = df
    for filter_part in filtering_expressions:
        col_name, operator, filter_value = split_filter_part(filter_part)

        if operator in ("eq", "ne", "lt", "le", "gt", "ge"):
            # these operators match pandas series operator method names
            dff = dff.loc[getattr(dff[col_name], operator)(filter_value)]
        elif operator == "contains":
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
    return dff.iloc[page * size : (page + 1) * size].to_dict("records")


if __name__ == "__main__":
    app.run_server(debug=True)
