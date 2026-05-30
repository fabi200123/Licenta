import os
import numpy as np
import SimpleITK as sitk
from skimage.measure import marching_cubes
import plotly.figure_factory as FF
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import base64
from PIL import Image
import scipy.spatial.distance as distance
import plotly.graph_objects as go
from flask import Flask, redirect, request
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from flask_cors import CORS


def timestamp_to_date(timestamp):
    return datetime.now().strftime('%Y-%m-%d')


def get_subdirectories(folder):
    return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]

def resolve_mask_nrrd(scan_folder_path):
    candidates = ["GTV_mask.nrrd", "GTV-1_mask.nrrd"]
    for name in candidates:
        path = os.path.join(scan_folder_path, name)
        if os.path.isfile(path):
            return path

    for entry in os.listdir(scan_folder_path):
        if entry.endswith("_mask.nrrd") or entry.endswith("-mask.nrrd"):
            return os.path.join(scan_folder_path, entry)

    raise FileNotFoundError(f"No mask NRRD found in {scan_folder_path}")

def get_png_files_for_scan(png_root, scan_folder_name):
    direct_folder = os.path.join(png_root, scan_folder_name)
    search_roots = []

    if os.path.isdir(direct_folder):
        search_roots.append(direct_folder)
    elif os.path.isdir(png_root):
        search_roots.extend(
            os.path.join(png_root, entry)
            for entry in os.listdir(png_root)
            if entry.startswith(scan_folder_name) and os.path.isdir(os.path.join(png_root, entry))
        )

    png_files = []
    for root in search_roots:
        for dirpath, _, files in os.walk(root):
            for file_name in files:
                if file_name.lower().endswith(".png"):
                    png_files.append(os.path.join(dirpath, file_name))

    png_files.sort()
    return png_files


def return_fig(images, threshold, step_size):
    p = images.transpose(2, 1, 0)
    data_min, data_max = np.min(p), np.max(p)
    if not (data_min < threshold < data_max):
        print(f"Threshold {threshold} is not between data min {data_min} and max {data_max}.")
        verts, faces, _, _ = marching_cubes(p, step_size=step_size, allow_degenerate=True, method='lewiner')
    else:
        verts, faces, _, _ = marching_cubes(p, threshold, step_size=step_size, allow_degenerate=True, method='lewiner')
    x, y, z = zip(*verts)
    colormap = ['rgb(255, 192, 203)', 'rgb(236, 236, 212)']
    fig = FF.create_trisurf(x=x, y=y, z=z, plot_edges=False, colormap=colormap, simplices=faces,
                            backgroundcolor='rgb(125, 125, 125)', title="3D Visualization of the Nodule")
    fig.layout.scene.xaxis.title = 'Width'
    fig.layout.scene.yaxis.title = 'Height'
    fig.layout.scene.zaxis.title = 'Depth (Slice Number)'
    return fig

def get_folder_paths(cnp):
    static_directory = os.environ.get("STATIC_DATA_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"))
    cnp_directory = os.path.join(static_directory, cnp)
    converted_nrrds_folder = os.path.join(cnp_directory, 'converted_nrrds')
    images_quick_check_folder = os.path.join(cnp_directory, 'images_quick_check')
    return converted_nrrds_folder, images_quick_check_folder

def missing_data_page(cnp, message):
    return f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>CT Visualization</title>
    <style>
      body {{ font-family: sans-serif; margin: 2rem; color: #333; }}
      .box {{ max-width: 720px; padding: 1.5rem; border: 1px solid #ddd; border-radius: 8px; }}
      code {{ background: #f5f5f5; padding: 0.1rem 0.35rem; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <div class="box">
      <h2>No CT visualization available</h2>
      <p>{message}</p>
      <p>Patient CNP: <code>{cnp or 'unknown'}</code></p>
      <p>Upload CT scans from the application using <strong>Add CT</strong>, then reopen this view once processing has completed.</p>
    </div>
  </body>
</html>"""

server = Flask(__name__)
app = dash.Dash(__name__, server=server, prevent_initial_callbacks='initial duplicate', url_base_pathname='/visualize/')


app.layout = html.Div(
    children=[
        # Define the structure and content of your app here
        # ...

        # Example placeholder content
        html.H1("My Dash App"),
        html.P("This is the content of my Dash app."),
    ]
)

# Your Flask route for handling the visualization
@app.server.route('/visualize', methods=['GET'])
def visualize():

    # Initialize the vectors for features
    global nodule_volume
    global nodule_fractal_dimension
    global nodule_area
    global calcification
    global spiculation
    global type_of_nodule

    # Replace with your actual route handling logic
    global subdirectories
    global data_folder
    global png_folder

    cnp = request.args.get('cnp')
    if not cnp:
        return missing_data_page("", "Missing patient CNP."), 400

    data_folder, png_folder = get_folder_paths(cnp)
    if not os.path.isdir(data_folder):
        return missing_data_page(
            cnp,
            "No processed CT scan folder was found for this patient on the visualization storage volume."
        ), 404

    try:
        subdirectories = get_subdirectories(data_folder)
    except FileNotFoundError:
        subdirectories = []

    if not subdirectories:
        return missing_data_page(
            cnp,
            "No converted CT scans were found for this patient yet."
        ), 404

    # Initialize imgs with the first subdirectory images
    if subdirectories:
        initial_selected_folder = subdirectories[0]
        initial_file_struct = None
        for root, _, files in os.walk(os.path.join(png_folder, initial_selected_folder)):
            initial_file_struct = (root, files)
            break
        if initial_file_struct:
            initial_root, initial_images = initial_file_struct
            imgs = [np.array(Image.open(os.path.join(initial_root, img))) for img in initial_images if img.lower().endswith('.png')]

    global initial_fig
    initial_fig = None
    if subdirectories:
        initial_scan_folder = os.path.join(data_folder, subdirectories[0])
        initial_image_nrrd_file = os.path.join(initial_scan_folder, "image.nrrd")
        initial_mask_nrrd_file = resolve_mask_nrrd(initial_scan_folder)

        initial_image = sitk.ReadImage(initial_image_nrrd_file)
        initial_mask = sitk.ReadImage(initial_mask_nrrd_file)

        initial_image_arr = sitk.GetArrayFromImage(initial_image)
        initial_mask_arr = sitk.GetArrayFromImage(initial_mask)

        initial_image_normalized = (initial_image_arr - np.min(initial_image_arr)) / (
                    np.max(initial_image_arr) - np.min(initial_image_arr))
        initial_nodule_arr = initial_image_normalized * initial_mask_arr

        initial_fig = return_fig(initial_nodule_arr, threshold=0.25, step_size=1)

    #    nodule_volume, nodule_fractal_dimension, nodule_area, calcification, spiculation, type_of_nodule = get_all_features(data_folder, subdirectories)
    mongo_connection_string = os.environ.get("MONGO_CONNECTION_STRING")
    if not mongo_connection_string:
        return missing_data_page(cnp, "Visualization database connection is not configured."), 500

    client = MongoClient(mongo_connection_string)

    db = client.get_default_database()
    collection = db.patients
    pacient_cnp = cnp
    doc = collection.find_one({"cnp": pacient_cnp})
    if not doc or not doc.get('Data'):
        return missing_data_page(
            cnp,
            "CT files exist on storage, but nodule analysis data is missing from the patient record."
        ), 404

    # Make sure nodule features are not already initialized
    nodule_volume = []
    nodule_fractal_dimension = []
    nodule_area = []
    calcification = []
    spiculation = []
    type_of_nodule = []

    # Extract the data from the 'Data' field in the document
    for data in doc['Data']:
        nodule_volume.append(data['nodule_volume'])
        nodule_area.append(data['nodule_area'])
        nodule_fractal_dimension.append(data['fractal_dimension'])
        calcification.append(data['calcification'])
        spiculation.append(data['spiculation'])
        type_of_nodule.append(data['type_of_nodule'])
    app.layout = html.Div(
        children=[
            html.Div(
                children=[
                    html.Div(
                        children=[
                            dcc.Graph(id='graph-with-selector', figure=initial_fig),
                        ],
                        style={"display": "inline-block", "vertical-align": "top", "width": "40%"}
                        # Update the style here
                    ),
                    html.Div(
                        children=[
                            dcc.Dropdown(
                                id='feature-dropdown',
                                options=[
                                    {'label': 'Nodule Volume', 'value': 'nodule-volume'},
                                    {'label': 'Fractal Dimension', 'value': 'fractal-dimension'},
                                    {'label': 'Nodule Area', 'value': 'nodule-area'},
                                    {'label': 'Calcification', 'value': 'calcification'},
                                    {'label': 'Spiculation', 'value': 'spiculation'},
                                    {'label': 'Nodule type', 'value': 'nodule-type'},
                                ],
                                value='Nodule Volume'  # The default value
                            ),
                            html.Div(id='info-display', children=[
                                html.P(id='info-text', style={"font-size": "32px"}),
                                dcc.Graph(id='info-graph'),
                            ]),
                        ],
                        style={"display": "inline-block", "vertical-align": "top", "margin-left": "200px"}
                        # Update the style here
                    ),
                ],
                style={"display": "block"}  # Update the style here
            ),
            dcc.Dropdown(
                id='folder-selector',
                options=[{'label': subdir, 'value': i} for i, subdir in enumerate(subdirectories)],
                value=0,  # Set the initial value to -1, representing no selection
                style={"max-width": "600px", "margin": "10px"},
            ),
            html.Div(
                children=[
                    html.Div(
                        children=[
                            dcc.Slider(id='png-slider', min=0, max=0, value=0, step=1),
                            html.Img(id='png-viewer', src=''),
                        ],
                        style={"display": "inline-block", "vertical-align": "top", "width": "30%"}
                        # Update the style here
                    ),
                ],
                style={"display": "block", "margin-top": "20px"}  # Update the style here
            ),
        ]
    )

    return app.index()  # Redirect to the Dash app route


@app.callback(
    [Output('graph-with-selector', 'figure'),
    Output('info-text', 'children', allow_duplicate=True),
    Output('feature-dropdown', 'value'),
    Output('png-slider', 'max'),
    Output('png-viewer', 'src', allow_duplicate=True),
    Output('png-slider', 'value')],
    [Input('folder-selector', 'value')],
)
def update_figure(selected_folder_index):
    updated_fig = initial_fig
    slider_value = 0
    info_display = f""
    if selected_folder_index != -1:
        selected_folder = subdirectories[selected_folder_index]
        scan_folder_path = os.path.join(data_folder, selected_folder)
        image_nrrd_file = os.path.join(scan_folder_path, "image.nrrd")
        mask_nrrd_file = resolve_mask_nrrd(scan_folder_path)

        image = sitk.ReadImage(image_nrrd_file)
        mask = sitk.ReadImage(mask_nrrd_file)
        image_arr = sitk.GetArrayFromImage(image)
        mask_arr = sitk.GetArrayFromImage(mask)

        image_normalized = (image_arr - np.min(image_arr)) / (np.max(image_arr) - np.min(image_arr))
        nodule_arr = image_normalized * mask_arr
        updated_fig = return_fig(nodule_arr, threshold=0.25, step_size=1)

        selected_feature = 'nodule-volume'
        info_display = f"Nodule volume: {nodule_volume[selected_folder_index]: .2f} mm³"
        png_files = get_png_files_for_scan(png_folder, selected_folder)
        if png_files:
            max_slider_value = len(png_files) - 1
            png_file_path = png_files[slider_value]
            with open(png_file_path, "rb") as f:
                image_bytes = f.read()
            encoded_image = base64.b64encode(image_bytes)
            png_src = f"data:image/png;base64,{encoded_image.decode()}"
        else:
            max_slider_value = 0
            png_src = ''

    else:
        updated_fig = return_fig(np.zeros((2, 2, 2)), threshold=0.25, step_size=1)
        info_display = f"None"
        max_slider_value = -1  # Initialize to -1 if no subdirectory is selected
        png_src = ''

    return updated_fig, info_display, selected_feature, max_slider_value, png_src, slider_value


@app.callback(
    Output('png-viewer', 'src'),
    Input('png-slider', 'value'),
    State('folder-selector', 'value'),
    prevent_initial_call='initial_duplicate'  # Add this parameter
)
def update_png_viewer(slider_value, selected_folder_index):
    if selected_folder_index != -1:
        selected_folder = subdirectories[selected_folder_index]
        png_files = get_png_files_for_scan(png_folder, selected_folder)
        if png_files:
            png_file_path = png_files[slider_value]
            with open(png_file_path, "rb") as f:
                image_bytes = f.read()
            encoded_image = base64.b64encode(image_bytes)
            return f"data:image/png;base64,{encoded_image.decode()}"
    return ''

@app.callback(
    [
        Output('info-text', 'children'),
        Output('info-graph', 'figure')
    ],
    [
        Input('folder-selector', 'value'),
        Input('feature-dropdown', 'value')
    ],
    prevent_initial_call=True
)
def update_info_display(selected_folder_index, selected_feature):
    info_text = ''
    feature_data = []
    selected_feature_data = 0
    if selected_feature == 'nodule-volume':
        info_text = f"Nodule volume: {nodule_volume[selected_folder_index]: .2f} mm³"
        feature_data = nodule_volume
        selected_feature_data = nodule_volume[selected_folder_index]
    elif selected_feature == 'fractal-dimension':
        info_text = f"Fractal dimension: {nodule_fractal_dimension[selected_folder_index]:.2f}"
        feature_data = nodule_fractal_dimension
        selected_feature_data = nodule_fractal_dimension[selected_folder_index]
    elif selected_feature == 'nodule-area':
        info_text = f"Nodule area: {nodule_area[selected_folder_index]:.2f} mm²"
        feature_data = nodule_area
        selected_feature_data = nodule_area[selected_folder_index]
    elif selected_feature == 'calcification':
        info_text = f"Calcification: {calcification[selected_folder_index]:.4f}"
        feature_data = calcification
        selected_feature_data = calcification[selected_folder_index]
    elif selected_feature == 'spiculation':
        info_text = f"Spiculation: {spiculation[selected_folder_index]:.4f}"
        feature_data = spiculation
        selected_feature_data = spiculation[selected_folder_index]
    elif selected_feature == 'nodule-type':
        info_text = f"Nodule type: {type_of_nodule[selected_folder_index]}"
        feature_data = type_of_nodule
        selected_feature_data = type_of_nodule[selected_folder_index]

    timestamps = []
    for time_stamp in subdirectories:
        timestamps.append(timestamp_to_date(time_stamp.replace("_1-1", "")))

    # Create a scatter plot of all feature data
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=feature_data,
        mode='lines+markers',
        line=dict(color='gray', dash='dot'),
        marker=dict(size=[30 if x == selected_folder_index else 10 for x in range(len(feature_data))],
                    color=['red' if x == selected_folder_index else 'blue' for x in range(len(feature_data))])
    ))
    fig.update_layout(
        title=selected_feature.capitalize().replace("-", " ") + ' Over Time',
        xaxis_title="CT Scan Date",
        yaxis_title=selected_feature.capitalize().replace("-", " ")
    )

    return info_text, fig


if __name__ == "__main__":
    # Path to your certificate and key files
    server.run(debug=True, host='0.0.0.0', port=3001)

