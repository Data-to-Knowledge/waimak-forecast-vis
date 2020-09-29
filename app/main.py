# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
import plotly.graph_objs as go
import pandas as pd
import numpy as np
import urllib
import requests
import zstandard as zstd
import orjson
import flask
import copy
from time import sleep
# from util import app_ts_summ, sel_ts_summ, ecan_ts_data

pd.options.display.max_columns = 10

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = flask.Flask(__name__)
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, server=server,  url_base_pathname = '/')

# app = dash.Dash(__name__, external_stylesheets=external_stylesheets, server=server)
# server = app.server

##########################################
### Parameters

# base_url = 'http://127.0.0.1/tethys/data/'
base_url = 'http://web-service:8000/tethys/data/'

precip_sites_ref = ['219910', '320010', '219510']
for_sites_ref = ['66401', '66402']
init_for_site_ref = '66401'
all_sites_ref = precip_sites_ref + for_sites_ref

ts_plot_height = 700
map_height = 500

lat1 = -43.42
lon1 = 172.34
zoom1 = 9

mapbox_access_token = "pk.eyJ1IjoibXVsbGVua2FtcDEiLCJhIjoiY2pudXE0bXlmMDc3cTNxbnZ0em4xN2M1ZCJ9.sIOtya_qe9RwkYXj5Du1yg"

#########################################
### Functions

# @server.route('/waimak-forecast')
# def vis():

def process_data_for_fig(datasets, site, simulation_date):
    """

    """
    # Parameters
    sw_forecast_codes = {'high_flow_YR_ECMWF_9km_forecast': 'ECMWF-Yr.no', 'high_flow_wrf_nz8kmN-UKMO': 'UKMO-MetService', 'high_flow_wrf_nz8kmN-ECMWF': 'ECMWF-MetService', 'high_flow_wrf_nz8kmN-NCEP': 'NCEP-MetService'}
    precip_forecast_code = 'YR_ECMWF_9km_forecast'
    ds_site_map = {'66401': 'streamflow', '66402': 'gage_height'}
    param_map = {'streamflow': 'Flow (m^3/s)', 'gage_height': 'Water Level (m)'}

    sim_date = pd.Timestamp(simulation_date)
    start_date = sim_date - pd.DateOffset(days=2)
    end_date = sim_date + pd.DateOffset(days=4)

    plot_data = []

    # Select datasets and sites
    meas_precip_ds = [ds for ds in datasets if (ds['parameter'] == 'precipitation') and (ds['processing_code'] == 'raw_data')][0]
    meas_precip_ds_id = meas_precip_ds['dataset_id']

    precip_sites_d = requests.post(base_url + 'sampling_sites', params={'dataset_id': meas_precip_ds_id}).json()

    precip_site_ids = [k['site_id'] for k in precip_sites_d if k['ref'] in precip_sites_ref]

    for_precip_ds = [ds for ds in datasets if (ds['parameter'] == 'precipitation') and (ds['processing_code'] == precip_forecast_code)][0]
    for_precip_ds_id = for_precip_ds['dataset_id']

    parameter = ds_site_map[site]
    meas_sw_ds = [ds for ds in datasets if (ds['parameter'] == parameter) and (ds['processing_code'] == 'raw_data')][0]
    meas_sw_ds_id = meas_sw_ds['dataset_id']

    sites_d = requests.post(base_url + 'sampling_sites', params={'dataset_id': meas_sw_ds_id}).json()
    ds_site = [s for s in sites_d if s['ref'] == site][0]
    ds_site_id = ds_site['site_id']

    ## Precip data
    meas_precip_list = []
    for_precip_list = []

    for s_id in precip_site_ids:
        meas_ts_r = requests.get(base_url + 'time_series_results', params={'dataset_id': meas_precip_ds_id, 'site_id': s_id, 'compression': 'zstd', 'from_date': start_date, 'to_date': end_date})
        dc = zstd.ZstdDecompressor()
        meas_ts1 = pd.DataFrame(orjson.loads(dc.decompress(meas_ts_r.content)))
        meas_ts1['from_date'] = pd.to_datetime(meas_ts1['from_date'])
        meas_precip_list.append(meas_ts1)

        for_ts_r = requests.get(base_url + 'time_series_results', params={'dataset_id': for_precip_ds_id, 'site_id': s_id, 'compression': 'zstd', 'from_date': start_date, 'to_date': end_date})
        dc = zstd.ZstdDecompressor()
        for_ts1 = pd.DataFrame(orjson.loads(dc.decompress(for_ts_r.content)))
        for_ts1['from_date'] = pd.to_datetime(for_ts1['from_date'])
        for_precip_list.append(for_ts1)

    meas_precip_df1 = pd.concat(meas_precip_list)
    meas_precip_df2 = meas_precip_df1.groupby('from_date').result.mean().reset_index()
    meas_precip_max = meas_precip_df2.from_date.max()

    for_precip_df1 = pd.concat(for_precip_list)
    for_precip_df2 = for_precip_df1.groupby('from_date').result.mean()
    for_precip_df3 = for_precip_df2.loc[meas_precip_max:].iloc[1:].reset_index()

    x1 = meas_precip_df2.from_date + pd.DateOffset(hours=12)
    y1 = meas_precip_df2.result

    set1 = go.Bar(
            x=x1,
            y=y1,
            # showlegend=False,
            name='Measured Precip',
            # line={'dash':'dash'},
            yaxis="y2",
            opacity=0.5
            )

    plot_data.append(set1)

    x1 = for_precip_df3.from_date + pd.DateOffset(hours=12)
    y1 = for_precip_df3.result

    set1 = go.Bar(
            x=x1,
            y=y1,
            # showlegend=False,
            name='YR.no Precip Forecast',
            # line={'dash':'dash'},
            yaxis="y2",
            opacity=0.5
            )

    plot_data.append(set1)

    ## SW data
    # Get measured data
    meas_ts_r = requests.get(base_url + 'time_series_results', params={'dataset_id': meas_sw_ds_id, 'site_id': ds_site_id, 'compression': 'zstd', 'from_date': start_date, 'to_date': end_date})
    dc = zstd.ZstdDecompressor()
    meas_ts1 = pd.DataFrame(orjson.loads(dc.decompress(meas_ts_r.content)))
    meas_ts1['from_date'] = pd.to_datetime(meas_ts1['from_date'])
    meas_ts1_max = meas_ts1.from_date.max()

    x1 = meas_ts1.from_date + pd.DateOffset(hours=12)
    y1 = meas_ts1.result

    set1 = go.Scatter(
            x=x1,
            y=y1,
            # showlegend=False,
            name='Measured Flow',
            line={'color': 'blue'},
            line_shape= 'spline',
            opacity=0.8
            )

    plot_data.append(set1)

    # Get forecasts
    for code in sw_forecast_codes:
        for_sw_ds = [ds for ds in datasets if (ds['parameter'] == parameter) and (ds['processing_code'] == code)][0]
        for_sw_ds_id = for_sw_ds['dataset_id']

        for_ts_r = requests.get(base_url + 'time_series_simulation', params={'dataset_id': for_sw_ds_id, 'site_id': ds_site_id, 'compression': 'zstd', 'from_simulation_date': simulation_date, 'to_simulation_date': simulation_date})
        dc = zstd.ZstdDecompressor()
        for_json = orjson.loads(dc.decompress(for_ts_r.content))[0]

        x1 = pd.to_datetime(for_json['from_date']) + pd.DateOffset(hours=12)
        y1 = for_json['result']

        set1 = go.Scatter(
                x=x1,
                y=y1,
                # showlegend=False,
                name=sw_forecast_codes[code],
                line={'dash':'dot'},
                line_shape= 'spline',
                opacity=0.8
                )

        plot_data.append(set1)

    # Create layout
    layout = dict(title = ds_site['ref'] + '<br>' + ds_site['name'], paper_bgcolor = '#F4F4F8', plot_bgcolor = '#F4F4F8', xaxis = dict(title="Date (NZST)", range = [start_date, end_date]), showlegend=True, height=ts_plot_height, yaxis=dict(title=param_map[parameter], titlefont=dict(color="#1f77b4"), tickfont=dict(color="#1f77b4")), yaxis2=dict(title="Precip (mm)", titlefont=dict(color="#ff7f0e"), tickfont=dict(color="#ff7f0e"), anchor="x", overlaying="y", side="right"))

    fig = dict(data=plot_data, layout=layout)

    return fig

###############################################
### App layout

map_layout = dict(mapbox = dict(layers = [], accesstoken = mapbox_access_token, style = 'outdoors', center=dict(lat=lat1, lon=lon1), zoom=zoom1), margin = dict(r=0, l=0, t=0, b=0), autosize=True, hovermode='closest', height=map_height, showlegend=False)

def serve_layout():

    dc = zstd.ZstdDecompressor()

    datasets = requests.get(base_url + 'datasets').json()

    ## Site data
    meas_sw_ds = [ds for ds in datasets if (ds['parameter'] in ['streamflow', 'gage_height']) and (ds['processing_code'] == 'raw_data')]

    sites_dict = {}

    for ds in meas_sw_ds:
        sites_r = requests.post(base_url + 'sampling_sites', params={'dataset_id': ds['dataset_id'], 'compression': 'zstd'})

        sites1 = orjson.loads(dc.decompress(sites_r.content))

        sites2 = [s for s in sites1 if s['ref'] in for_sites_ref]

        sites_dict.update({s['site_id']: s for s in sites2})


    sites3 = [{'label': s['ref'], 'value': k} for k, s in sites_dict.items()]

    for_site = [s for k, s in sites_dict.items() if s['ref'] in for_sites_ref]

    for_lon = [f['geometry']['coordinates'][0] for f in for_site]
    for_lat = [f['geometry']['coordinates'][1] for f in for_site]
    for_name = [f['ref'] + '<br>' + f['name'] for f in for_site]

    # precip_sites = [s for k, s in sites_dict.items() if s['ref'] in precip_sites_ref]
    #
    # precip_lon = [l['geometry']['coordinates'][0] for l in precip_sites]
    # precip_lat = [l['geometry']['coordinates'][1] for l in precip_sites]
    # precip_names = [l['ref'] + '<br>' + l['name'] for l in precip_sites]

    ## Get simulation dates and assign initial start and end dates
    for_dataset1 = [ds for ds in datasets if (ds['parameter'] == 'streamflow') and (ds['processing_code'] == 'high_flow_YR_ECMWF_9km_forecast')][0]
    for_site1 = [s for s in for_site if s['ref'] == init_for_site_ref][0]

    # Get simulation dates
    sims_r = requests.get(base_url + 'time_series_simulation_dates', params={'dataset_id': for_dataset1['dataset_id'], 'site_id': for_site1['site_id']})
    sims_dates1 = pd.to_datetime(orjson.loads(sims_r.content))

    first_sim_date = sims_dates1.min()
    last_sim_date = sims_dates1.max()

    ## Create fig
    fig = process_data_for_fig(datasets, init_for_site_ref, last_sim_date)

    ## Process dates
    sims_dates2 = (sims_dates1.astype(int) / 10**9).astype(int).tolist()
    # sims_dates2.reverse()

    # sims_dates3 = sims_dates2[::12]
    # sims_dates3.reverse()
    #
    # sims_dates4 = sims_dates3[-10:]

    # sim_date_dict = {k: (pd.Timestamp(k, unit='s') + pd.DateOffset(hours=12)).strftime('%Y-%m-%d %H:%M') for k in sims_dates2}
    sim_date_dict = [{'value': k, 'label': (pd.Timestamp(k, unit='s') + pd.DateOffset(hours=12)).strftime('%Y-%m-%d %H:%M')} for k in sims_dates2]

    # min_date = sims_dates4[0]
    max_date = sims_dates2[-1]


    init_sites = [{'label': s['ref'], 'value': s['ref']} for s in for_site]

    layout = html.Div(children=[
    html.Div([
        html.P('Select a site for the forecast:', style={'display': 'inline-block'}),
        dcc.Graph(
                id = 'site-map',
                style={'height': map_height},
                figure=dict(
                    data = [
                            # dict(lat = precip_lat,
                            # lon = precip_lon,
                            # text = precip_names,
                            # type = 'scattermapbox',
                            # hoverinfo = 'text',
                            # marker = dict(
                            #         size=8,
                            #         color='black',
                            #         opacity=1
                            #         )
                            #     ),
                            dict(lat = for_lat,
                            lon = for_lon,
                            text = for_name,
                            type = 'scattermapbox',
                            hoverinfo = 'text',
                            marker = dict(
                                    size=12,
                                    color='black',
                                    opacity=1
                                    )
                                ),
                            dict(lat = for_lat,
                            lon = for_lon,
                            text = for_name,
                            type = 'scattermapbox',
                            hoverinfo = 'text',
                            marker = dict(
                                    size=8,
                                    color='red',
                                    opacity=1
                                    )
                                )
                            ],
                        layout=map_layout),
                config={"displaylogo": False}),
        html.Label('Site IDs'),
        dcc.Dropdown(options=init_sites, id='sites', value=init_sites[0]['value'], clearable=False),
        html.Label('Simulation dates'),
        dcc.Dropdown(options=sim_date_dict, value=max_date, id='sim_dates', clearable=False),

    ], className='four columns', style={'margin': 20}),
#
    html.Div([

# 		html.P('Select Dataset for time series plot:', style={'display': 'inline-block'}),
# 		dcc.Dropdown(options=[{'value:': 5, 'label': init_dataset}], value=5, id='sel_dataset'),
        dcc.Graph(
            id = 'selected-data',
            figure = fig,
            config={"displaylogo": False}
            ),
        # dcc.Slider(
        #     id='date-slider',
        #     min=min_date,
        #     max=max_date,
        #     step=None,
        #     marks=sim_date_dict,
        #     value=max_date
        #     )
        dcc.Markdown('''

            This dashboard visualises the flood forecast model output for the Waimakariri River flows at the Old Highway Bridge and water levels at the Gorge. The inputs are measured precipitation at three upstream stations (i.e. Arthur's Pass, Bulls Creek, and Kanuka Hills) and forcasted precipitation by the New Zealand MetService and the Norwegian Meteorological Institute (YR.no). YR.no only provides downscaled forecasts using the [ECMWF](https://www.ecmwf.int/) and MetService provides downscales forecasts using [ECMWF](https://www.ecmwf.int/), [UKMO](https://www.metoffice.gov.uk/), and [NCEP](https://www.ncep.noaa.gov/). The measured precipitation show in the plot is a mean of the three mentioned stations.

            ''')

    ], className='seven columns', style={'margin': 10, 'height': 900}),
    # html.Div(id='ts_data', style={'display': 'none'}),
    html.Div(id='datasets', style={'display': 'none'}, children=orjson.dumps(datasets).decode())
    # html.Div(id='dataset_id', style={'display': 'none'}, children=init_dataset_id),
    # html.Div(id='sites_summ', style={'display': 'none'}, children=orjson.dumps(init_summ).decode())
#     dcc.Graph(id='map-layout', style={'display': 'none'}, figure=dict(data=[], layout=map_layout))
], style={'margin':0})

    return layout


app.layout = serve_layout

########################################
### Callbacks

@app.callback(
        Output('sites', 'value'),
        [Input('site-map', 'selectedData'), Input('site-map', 'clickData')],
        [State('sites', 'value')])
def update_sites_values(selectedData, clickData, site):
    # print(clickData)
    # print(selectedData)
    if selectedData:
        site1_index = selectedData['points'][0]['pointIndex']
        sites1 = [s['text'].split('<br>')[0] for s in selectedData['points']][0]
    elif clickData:
        site1_index = clickData['points'][0]['pointIndex']
        sites1 = [clickData['points'][0]['text'].split('<br>')[0]][0]
    else:
        sites1 = site
        # site1_index = None
    # print(sites1)
    # if site1_index:
    #     site1_id = orjson.loads(sites_summ)[site1_index]['site_id']
    # else:
    #     site1_id = ''

    # print(sites1_id)

    return sites1

@app.callback(
    Output('selected-data', 'figure'),
    [Input('sites', 'value'), Input('sim_dates', 'value')],
    [State('datasets', 'children')])
def display_data(site, sim_date, datasets):
    """

    """
    datasets1 = orjson.loads(datasets)

    sim_date1 = pd.Timestamp(sim_date, unit='s')

    fig = process_data_for_fig(datasets1, site, sim_date1)

    return fig


if __name__ == '__main__':
    server.run(debug=True, host='0.0.0.0', port=8080)


# @server.route("/waimak-forecast")
# def my_dash_app():
#     return app.index()
