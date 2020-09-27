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
# from util import app_ts_summ, sel_ts_summ, ecan_ts_data

pd.options.display.max_columns = 10

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = flask.Flask(__name__)
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, server=server)

# app = dash.Dash(__name__, external_stylesheets=external_stylesheets, server=server)
# server = app.server

##########################################
### Parameters

base_url = 'http://127.0.0.1/tethys/data/'

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

# @server.route('/wai-vis')
# def main():
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


    # features = list(set([f['feature'] for f in requested_datasets]))
    # features.sort()
    #
    # parameters = list(set([f['parameter'] for f in requested_datasets]))
    # parameters.sort()
    #
    # methods = list(set([f['method'] for f in requested_datasets]))
    # methods.sort()
    #
    # processing_codes = list(set([f['processing_code'] for f in requested_datasets]))
    # processing_codes.sort()
    #
    # owners = list(set([f['owner'] for f in requested_datasets]))
    # owners.sort()
    #
    # aggregation_statistics = list(set([f['aggregation_statistic'] for f in requested_datasets]))
    # aggregation_statistics.sort()
    #
    # frequency_intervals = list(set([f['frequency_interval'] for f in requested_datasets]))
    # frequency_intervals.sort()
    #
    # utc_offsets = list(set([f['utc_offset'] for f in requested_datasets]))
    # utc_offsets.sort()
    #
    # init_dataset = [d for d in requested_datasets if (d['feature'] == 'waterway') and (d['parameter'] == 'streamflow') and (d['processing_code'] == 'quality_controlled_data')][0]
    #
    # init_dataset_id = init_dataset['dataset_id']

    # dataset_table_cols = {'license': 'Data License', 'precision': 'Data Precision', 'units': 'Units'}

    ### prepare summaries and initial states
    # max_date = pd.Timestamp.now()
    # start_date = max_date - pd.DateOffset(years=1)

    # init_summ = sel_ts_summ(ts_summ, 'River', 'Flow', 'Recorder', 'Primary', 'ECan', str(start_date.date()), str(max_date.date()))
    #
    # new_sites = init_summ.drop_duplicates('ExtSiteID')

    # init_summ_r = requests.post(base_url + 'sampling_sites', params={'dataset_id': init_dataset_id, 'compression': 'zstd'})
    #
    # init_summ = orjson.loads(dc.decompress(init_summ_r.content))
    # init_summ = [s for s in init_summ if (pd.Timestamp(s['stats']['to_date']) > start_date) and (pd.Timestamp(s['stats']['from_date']) < max_date)]
    #
    init_sites = [{'label': s['ref'], 'value': s['ref']} for s in for_site]
    #
    # init_site_id = [s['value'] for s in init_sites if s['label'] == '70105'][0]
    #
    # flow_lon = [l['geometry']['coordinates'][0] for l in init_summ]
    # flow_lat = [l['geometry']['coordinates'][1] for l in init_summ]
    # flow_names = [l['ref'] + '<br>' + l['name'] for l in init_summ]
    #
    # init_table = [{'Site ID': s['ref'], 'Site Name': s['name'], 'Min Value': s['stats']['min'], 'Mean Value': s['stats']['mean'], 'Max Value': s['stats']['max'], 'Start Date': s['stats']['from_date'], 'End Date': s['stats']['to_date'], 'Last Modified Date': s['modified_date']} for s in init_summ]

    # init_ts_r = requests.get(base_url + 'time_series_results', params={'dataset_id': init_dataset_id, 'site_id': init_site_id, 'compression': 'zstd', 'from_date': start_date.round('s').isoformat(), 'to_date': max_date.round('s').isoformat()})
    # dc = zstd.ZstdDecompressor()
    # df1 = pd.DataFrame(orjson.loads(dc.decompress(init_ts_r.content)))

    layout = html.Div(children=[
#     html.Div([
#         html.P(children='Filter datasets (select from top to bottom):'),
#         html.Label('Feature'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in features], value='waterway', id='features'),
#         html.Label('Parameter'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in parameters], value='streamflow', id='parameters'),
#         html.Label('Method'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in methods], value='sensor_recording', id='methods'),
#         html.Label('Processing Code'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in processing_codes], value='quality_controlled_data', id='processing_codes'),
#         html.Label('Data Owner'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in owners], value='ECan', id='owners'),
#         html.Label('Aggregation Statistic'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in aggregation_statistics], value='mean', id='aggregation_statistics'),
#         html.Label('Frequency Interval'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in frequency_intervals], value='1H', id='frequency_intervals'),
#         html.Label('UTC Offset'),
#         dcc.Dropdown(options=[{'label': d, 'value': d} for d in utc_offsets], value='0H', id='utc_offsets'),
#         html.Label('Date Range'),
#         dcc.DatePickerRange(
#             end_date=str(max_date.date()),
#             display_format='DD/MM/YYYY',
#             start_date=str(start_date.date()),
#             id='date_sel'
# #               start_date_placeholder_text='DD/MM/YYYY'
#             ),
#         html.Label('Site IDs'),
#         dcc.Dropdown(options=init_sites, id='sites')
#         # html.Label('Water quality below detection limit method'),
#         # dcc.RadioItems(
#         #     options=[
#         #         {'label': 'Half dtl', 'value': 'half'},
#         #         {'label': 'Trend analysis method', 'value': 'trend'}
#         #     ],
#         #     value='half',
#         #     id='dtl')
#         ],
#     className='two columns', style={'margin': 20}),

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

#         html.A(
#             'Download Dataset Summary Data',
#             id='download-summ',
#             download="dataset_summary.csv",
#             href="",
#             target="_blank",
#             style={'margin': 50}),
#
        # dash_table.DataTable(
        #     id='dataset_table',
        #     columns=[{"name": v, "id": v, 'deletable': True} for k, v in dataset_table_cols.items()],
        #     data=[],
        #     sort_action="native",
        #     sort_mode="multi",
        #     style_cell={
        #         'minWidth': '80px', 'maxWidth': '200px',
        #         'whiteSpace': 'normal'}
            # )

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
        # html.A(
        #     'Download Time Series Data',
        #     id='download-tsdata',
        #     download="tsdata.csv",
        #     href="",
        #     target="_blank",
        #     style={'margin': 50}),
        # dash_table.DataTable(
        #     id='summ_table',
        #     columns=[{"name": i, "id": i, 'deletable': True} for i in init_table[0].keys()],
        #     data=init_table,
        #     sort_action="native",
        #     sort_mode="multi",
        #     style_cell={
        #         'minWidth': '80px', 'maxWidth': '200px',
        #         'whiteSpace': 'normal'
        #     }
        #     )
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


# @app.callback(
#     [Output('parameters', 'options'), Output('methods', 'options'), Output('processing_codes', 'options'), Output('owners', 'options'), Output('aggregation_statistics', 'options'), Output('frequency_intervals', 'options'), Output('utc_offsets', 'options')],
#     [Input('features', 'value')],
#     [State('datasets', 'children')])
# def update_parameters(features, datasets):
#
#     def make_options(val):
#         l1 = [{'label': v, 'value': v} for v in val]
#         return l1
#
#     datasets1 = orjson.loads(datasets)
#     datasets2 = [d for d in datasets1 if d['feature'] == features]
#
#     parameters = list(set([d['parameter'] for d in datasets2]))
#     parameters.sort()
#
#     methods = list(set([d['method'] for d in datasets2]))
#     methods.sort()
#
#     processing_codes = list(set([d['processing_code'] for d in datasets2]))
#     processing_codes.sort()
#
#     owners = list(set([d['owner'] for d in datasets2]))
#     owners.sort()
#
#     aggregation_statistics = list(set([d['aggregation_statistic'] for d in datasets2]))
#     aggregation_statistics.sort()
#
#     frequency_intervals = list(set([d['frequency_interval'] for d in datasets2]))
#     frequency_intervals.sort()
#
#     utc_offsets = list(set([d['utc_offset'] for d in datasets2]))
#     utc_offsets.sort()
#
#     return make_options(parameters), make_options(methods), make_options(processing_codes), make_options(owners), make_options(aggregation_statistics), make_options(frequency_intervals), make_options(utc_offsets)
#
#
# @app.callback(
#     Output('dataset_id', 'children'), [Input('features', 'value'), Input('parameters', 'value'), Input('methods', 'value'), Input('processing_codes', 'value'), Input('owners', 'value'), Input('aggregation_statistics', 'value'), Input('frequency_intervals', 'value'), Input('utc_offsets', 'value')], [State('datasets', 'children')])
# def update_dataset_id(features, parameters, methods, processing_codes, owners, aggregation_statistics, frequency_intervals, utc_offsets, datasets):
#     try:
#         dataset = select_dataset(features, parameters, methods, processing_codes, owners, aggregation_statistics, frequency_intervals, utc_offsets, orjson.loads(datasets))
#         dataset_id = dataset['dataset_id']
#
#         print(features, parameters, methods, processing_codes, owners, aggregation_statistics, frequency_intervals, utc_offsets)
#         return dataset_id
#     except:
#         print('No available dataset_id')
#
#
# @app.callback(
#     Output('sites_summ', 'children'),
#     [Input('dataset_id', 'children'), Input('date_sel', 'start_date'), Input('date_sel', 'end_date')])
# def update_summ_data(dataset_id, start_date, end_date):
#     if dataset_id is None:
#         print('No new sites_summ')
#     else:
#         summ_r = requests.post(base_url + 'sampling_sites', params={'dataset_id': dataset_id, 'compression': 'zstd'})
#
#         dc = zstd.ZstdDecompressor()
#         summ_data1 = orjson.loads(dc.decompress(summ_r.content).decode())
#         summ_data2 = [s for s in summ_data1 if (pd.Timestamp(s['stats']['to_date']) > pd.Timestamp(start_date)) and (pd.Timestamp(s['stats']['from_date']) < pd.Timestamp(end_date))]
#         summ_json = orjson.dumps(summ_data2).decode()
#
#         return summ_json
#
#
# @app.callback(
#     Output('sites', 'options'), [Input('sites_summ', 'children')])
# def update_site_list(sites_summ):
#     if sites_summ is None:
#         print('No sites available')
#         return []
#     else:
#         sites_summ1 = orjson.loads(sites_summ)
#         sites_options = [{'label': s['ref'], 'value': s['site_id']} for s in sites_summ1]
#
#         return sites_options
#
#
# @app.callback(
#         Output('site-map', 'figure'),
#         [Input('sites_summ', 'children')],
#         [State('site-map', 'figure')])
# def update_display_map(sites_summ, figure):
#     if sites_summ is None:
#         print('Clear the sites')
#         data1 = figure['data'][0]
#         if 'hoverinfo' in data1:
#             data1.pop('hoverinfo')
#         data1.update(dict(size=8, color='black', opacity=0))
#         fig = dict(data=[data1], layout=figure['layout'])
#     else:
#         sites_summ1 = orjson.loads(sites_summ)
#
#         lon1 = [l['geometry']['coordinates'][0] for l in sites_summ1]
#         lat1 = [l['geometry']['coordinates'][1] for l in sites_summ1]
#         names1 = [l['ref'] + '<br>' + l['name'] for l in sites_summ1]
#
#         data = [dict(
#             lat = lat1,
#             lon = lon1,
#             text = names1,
#             type = 'scattermapbox',
#             hoverinfo = 'text',
#             marker = dict(size=8, color='black', opacity=1)
#         )]
#
#         fig = dict(data=data, layout=figure['layout'])
#
#     return fig
#
#
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
#
#
# @app.callback(
#     Output('summ_table', 'data'),
#     [Input('sites_summ', 'children'), Input('sites', 'value'), Input('site-map', 'selectedData'), Input('site-map', 'clickData')])
# def update_table(sites_summ, sites, selectedData, clickData):
#     if sites_summ:
#         new_summ = orjson.loads(sites_summ)
#
#         if sites:
#             summ_table = [{'Site ID': s['ref'], 'Site Name': s['name'], 'Min Value': s['stats']['min'], 'Mean Value': s['stats']['mean'], 'Max Value': s['stats']['max'], 'Start Date': s['stats']['from_date'], 'End Date': s['stats']['to_date'], 'Last Modified Date': s['modified_date']} for s in new_summ if s['site_id'] in sites]
#         else:
#             summ_table = [{'Site ID': s['ref'], 'Site Name': s['name'], 'Min Value': s['stats']['min'], 'Mean Value': s['stats']['mean'], 'Max Value': s['stats']['max'], 'Start Date': s['stats']['from_date'], 'End Date': s['stats']['to_date'], 'Last Modified Date': s['modified_date']} for s in new_summ]
#
#         return summ_table
#
#
# @app.callback(
#     Output('ts_data', 'children'),
#     [Input('sites', 'value'), Input('date_sel', 'start_date'), Input('date_sel', 'end_date'), Input('dataset_id', 'children')])
# def get_data(sites, start_date, end_date, dataset_id):
#     if dataset_id:
#         if sites:
#             ts_r = requests.get(base_url + 'time_series_results', params={'dataset_id': dataset_id, 'site_id': sites, 'compression': 'zstd', 'from_date': start_date+'T00:00', 'to_date': end_date+'T00:00'})
#             dc = zstd.ZstdDecompressor()
#             ts1 = dc.decompress(ts_r.content).decode()
#
#             return ts1
#
#
#
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
#
#
# @app.callback(
#     Output('dataset_table', 'data'),
#     [Input('dataset_id', 'children')],
#     [State('datasets', 'children')])
# def update_table(dataset_id, datasets):
#     if dataset_id:
#         dataset_table_cols = {'license': 'Data License', 'precision': 'Data Precision', 'units': 'Units'}
#
#         datasets1 = orjson.loads(datasets)
#
#         dataset1 = [d for d in datasets1 if d['dataset_id'] == dataset_id][0]
#
#         dataset_table1 = {}
#         [dataset_table1.update({v: dataset1[k]}) for k, v in dataset_table_cols.items()]
#
#         return [dataset_table1]
#
#
# @app.callback(
#     Output('download-tsdata', 'href'),
#     [Input('ts_data', 'children')],
#     [State('sites', 'value'), State('dataset_id', 'children')])
# def download_tsdata(ts_data, sites, dataset_id):
#     if dataset_id:
#         if sites:
#             ts_data1 = pd.DataFrame(orjson.loads(ts_data))
#             ts_data1['from_date'] = pd.to_datetime(ts_data1['from_date'])
#
#             csv_string = ts_data1.to_csv(index=False, encoding='utf-8')
#             csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
#             return csv_string


# @app.callback(
#     Output('download-summ', 'href'),
#     [Input('summ_data', 'children')])
# def download_summ(summ_data):
#     new_summ = pd.read_json(summ_data, orient='split')[table_cols]
#
#     csv_string = new_summ.to_csv(index=False, encoding='utf-8')
#     csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
#     return csv_string


# if __name__ == '__main__':
#     app.run_server(debug=True, host='0.0.0.0', port=8080)


@server.route("/waimak-forecast")
def my_dash_app():
    return app.index()




