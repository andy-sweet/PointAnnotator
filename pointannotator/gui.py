import glob
from typing import List

from dask_image.imread import imread
import napari
import numpy as np
from magicgui import magicgui
import pandas as pd

COLOR_CYCLE = [
        '#1f77b4',
        '#ff7f0e',
        '#2ca02c',
        '#d62728',
        '#9467bd',
        '#8c564b',
        '#e377c2',
        '#7f7f7f',
        '#bcbd22',
        '#17becf'
]


def point_annotator(im_path: str, labels: List[str], output_path: str='anno.csv', scorer: str='user'):
    stack = imread(im_path)
    with napari.gui_qt():
        viewer = napari.view_image(stack, contrast_limits=[0, 256], is_pyramid=False)
        properties = {'label': np.empty(0)}
        default_properties = {'label': np.array(labels)}
        points_layer = viewer.add_points(
            properties=properties,
            default_properties=default_properties,
            edge_color='label',
            edge_color_cycle=COLOR_CYCLE,
            symbol='o',
            face_color='transparent',
            edge_width=8,
            size=12,
        )
        points_layer.edge_color_mode = 'cycle'

        # Create the label selection menu
        @magicgui(label={'choices': labels})
        def label_selection(label):
            return label
        label_menu = label_selection.Gui()

        def label_changed(result):
            """Update the Points layer when the label menu selection changes"""
            selected_label = result
            points_layer.current_properties = {'label': np.asarray([selected_label])}

        def update_label_menu(event):
            """Update the label menu when the point selection changes"""
            label_menu.label = points_layer.current_properties['label'][0]

        @viewer.bind_key('.')
        def next_label(event=None):
            """Keybinding to advance to the next label with wraparound"""
            current_properties = points_layer.current_properties
            current_label = current_properties['label'][0]
            ind = list(labels).index(current_label)
            new_ind = (ind + 1) % len(labels)
            new_label = labels[new_ind]
            current_properties['label'] = np.array([new_label])
            points_layer.current_properties = current_properties

        def next_on_click(layer, event):
            """Mouse click binding to advance the label when a point is added"""
            if layer.mode == 'add':
                next_label()

                # by default, napari selects the point that was just added
                # disable that behavior, as the highlight gets in the way
                layer.selected_data = []

        points_layer.mouse_drag_callbacks.append(next_on_click)


        @viewer.bind_key(',')
        def prev_label(event):
            """Keybinding to decrement to the previous label with wraparound"""
            current_properties = points_layer.current_properties
            current_label = current_properties['label'][0]
            ind = list(labels).index(current_label)
            n_labels = len(labels)
            new_ind = ((ind - 1) + n_labels) % n_labels
            new_label = labels[new_ind]
            current_properties['label'] = np.array([new_label])
            points_layer.current_properties = current_properties


        @viewer.bind_key('Control-S')
        def save_points(event):
            """Save the added points to a CSV file"""
            # get the frame indices
            frame_indices = np.unique(points_layer.data[:, 0]).astype(np.int)

            # get the filenames
            all_files = np.asarray(glob.glob(im_path))
            file_names = all_files[frame_indices]

            # create and write dataframe
            header = pd.MultiIndex.from_product(
                [[scorer], labels, ['x', 'y']],
                names=['scorer', 'bodyparts', 'coords']
            )
            df = pd.DataFrame(
                index=file_names,
                columns=header,
            )

            # populate the dataframe
            for label, coord in zip(points_layer.properties['label'], points_layer.data):
                fname = all_files[coord[0].astype(np.int)]
                df.loc[fname][scorer][label]['x'] = coord[2]
                df.loc[fname][scorer][label]['y'] = coord[1]

            # write the dataframe
            df.to_csv(output_path)

        # connect the events and add the label menu widget
        points_layer.events.current_properties.connect(update_label_menu)
        label_menu.label_changed.connect(label_changed)
        viewer.window.add_dock_widget(label_menu)
