import os
import numpy as np
import SimpleITK as sitk
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from PIL import Image
from radiomics import featureextractor
import SimpleITK as sitk
import scipy.spatial.distance as distance
import numpy as np
from .FractalDimension import fractal_dimension
import matplotlib.pyplot as plt

def calculate_nodule_volume(nodule_arr, image):
    non_zero_voxels = np.count_nonzero(nodule_arr)
    spacing = image.GetSpacing()
    voxel_volume = spacing[0] * spacing[1] * spacing[2]
    nodule_volume = non_zero_voxels * voxel_volume
    return nodule_volume

def calculate_fractal_dimension(nodule_arr):

    # Transform nodule_arr into a binary array
    nodule_arr = (nodule_arr > 0)

    # Compute the fractal dimension using the module's function
    fractalDimension = fractal_dimension(nodule_arr)

    return fractalDimension

def compute_nodule_area_multi_slice(nodule_mask, voxel_spacing):
    total_area = 0
    for slice_mask in nodule_mask:
        total_area += np.sum(slice_mask) * voxel_spacing[0] * voxel_spacing[1]
    return total_area

def compute_nodule_area(mask_arr, voxel_spacing):
    return compute_nodule_area_multi_slice(mask_arr, voxel_spacing)

def calculate_max_dimension(mask, voxel_spacing):
    coords = np.argwhere(mask > 0)
    min_coords = np.min(coords, axis=0)
    max_coords = np.max(coords, axis=0)

    dimensions_voxels = max_coords - min_coords + 1
    dimensions_mm = dimensions_voxels * voxel_spacing

    return np.max(dimensions_mm)

def calculate_max_distance(mask_arr, voxel_spacing):
    return calculate_max_dimension(mask_arr, voxel_spacing)